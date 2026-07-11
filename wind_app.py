import streamlit as st
import json
import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import math
import matplotlib.pyplot as plt
import numpy as np

# ==========================================
# ⚙️ 基本設定・定数
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE_AMEDAS = os.path.join(BASE_DIR, "ops_amedas.json")
SCW_DATA_FILE = os.path.join(BASE_DIR, "ops_scw_data.json")
REPORT_DATA_FILE = os.path.join(BASE_DIR, "ops_report_data.json") # 🌟【新規】実測報告用DB
CONFIG_FILE = os.path.join(BASE_DIR, "ops_config.json")

# 琵琶湖周辺のアメダス地点定義
AMEDAS_STATIONS = {
    "60131": {"name": "彦根", "lat": 35.2750, "lon": 136.2467},
    "60026": {"name": "長浜", "lat": 35.3850, "lon": 136.2650},
    "60066": {"name": "米原", "lat": 35.3150, "lon": 136.2867},
    "60191": {"name": "南小松", "lat": 35.2400, "lon": 135.9633},
    "60216": {"name": "大津", "lat": 35.0150, "lon": 135.8750},
    "60111": {"name": "今津", "lat": 35.4117, "lon": 136.0350}
}
DIR_16_NAMES = ["無風", "北北東", "北東", "東北東", "東", "東南東", "南東", "南南東", "南", "南南西", "南西", "西南西", "西", "西北西", "北西", "北北西", "北"]

# SCW入力用の選択肢
SCW_LOCATIONS = ["彦根沖", "長浜沖", "今津沖", "南小松沖", "その他"]
SCW_CONFIDENCE = ["高 (High)", "中 (Mid)", "低 (Low)"]
CLOCK_LABELS = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

# ==========================================
# 📡 AMeDAS 自動取得ロジック (Ver.93から継承)
# ==========================================
def fetch_amedas_latest():
    try:
        time_url = "https://www.jma.go.jp/bosai/amedas/data/latest_time.txt"
        latest_time_str = requests.get(time_url).text.strip()
        dt = datetime.fromisoformat(latest_time_str)
        time_key = dt.strftime("%Y%m%d%H%M%S")
        
        data_url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_key}.json"
        all_data = requests.get(data_url).json()
        
        extracted = {"observed": latest_time_str, "stations": {}}
        for st_id, info in AMEDAS_STATIONS.items():
            if st_id in all_data:
                s_data = all_data[st_id]
                extracted["stations"][st_id] = {
                    "name": info["name"],
                    "wind_speed": s_data.get("wind", [None])[0],
                    "wind_dir": s_data.get("wndDir", [None])[0],
                    "temp": s_data.get("temp", [None])[0]
                }
        
        with open(DATA_FILE_AMEDAS, "w", encoding="utf-8") as f:
            json.dump(extracted, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"アメダス取得エラー: {e}")
        return False

def load_amedas():
    if not os.path.exists(DATA_FILE_AMEDAS): return None
    try:
        with open(DATA_FILE_AMEDAS, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return None

def draw_ops_map(amedas_data, reports):
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.set_facecolor('#E3F2FD') 
    ax.set_title("Lake Biwa Wind Overview", fontsize=15)
    
    for st_id, info in AMEDAS_STATIONS.items():
        ax.plot(info["lon"], info["lat"], 'o', color='#1A237E', markersize=10)
        ax.text(info["lon"]+0.01, info["lat"], info["name"], fontsize=12)
        
        if amedas_data and st_id in amedas_data["stations"]:
            s = amedas_data["stations"][st_id]
            if s["wind_speed"] is not None:
                ax.text(info["lon"]+0.01, info["lat"]-0.015, f"{s['wind_speed']}m/s", color='red', fontweight='bold')

    ax.grid(True, linestyle='--', alpha=0.5)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    return fig

# ==========================================
# 🖊️ SCW データ管理ロジック (Ver.93から継承)
# ==========================================
def load_scw_data():
    if not os.path.exists(SCW_DATA_FILE): return []
    try:
        with open(SCW_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def save_scw_data(publish_time, target_time, location, clock_dir, speed, confidence, memo):
    current_data = load_scw_data()
    angle_rad = math.radians(90 - (clock_dir * 30))
    u_comp = -speed * math.sin(angle_rad)
    v_comp = -speed * math.cos(angle_rad)

    new_entry = {
        "id": str(time.time()),
        "publish_time": publish_time,
        "target_time": target_time,
        "location": location,
        "clock_dir": clock_dir,
        "speed": speed,
        "u": round(u_comp, 2),
        "v": round(v_comp, 2),
        "confidence": confidence,
        "memo": memo,
        "updated_at": datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S')
    }
    current_data.append(new_entry)
    try:
        with open(SCW_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"保存エラー: {e}")

# ==========================================
# 🚩 実測報告 データ管理ロジック (🌟新規実装)
# ==========================================
def load_report_data():
    if not os.path.exists(REPORT_DATA_FILE): return []
    try:
        with open(REPORT_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def save_report_data(run_name, location, obs_time, clock_dir, speed, max_speed, method, memo):
    current_data = load_report_data()
    # 正規化（u, vベクトル変換）
    angle_rad = math.radians(90 - (clock_dir * 30))
    u_comp = -speed * math.sin(angle_rad)
    v_comp = -speed * math.cos(angle_rad)

    new_entry = {
        "id": str(time.time()),
        "run_name": run_name,
        "location": location,
        "obs_time": obs_time,
        "clock_dir": clock_dir,
        "speed": speed,
        "max_speed": max_speed,
        "u": round(u_comp, 2),
        "v": round(v_comp, 2),
        "method": method,
        "memo": memo,
        "updated_at": datetime.now(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S')
    }
    current_data.append(new_entry)
    try:
        with open(REPORT_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"保存エラー: {e}")

# ==========================================
# 🚀 メイン UI
# ==========================================
st.set_page_config(page_title="Birdman Wind Ops", page_icon="🦅", layout="wide")
st.markdown("# 🦅 Birdman Wind Ops <small>Ver.94</small>", unsafe_allow_html=True)

# サイドバー：全体共有設定
with st.sidebar:
    st.header("🌐 Global Settings")
    RUNS = [f"{i}走目" for i in range(1, 21)]
    current_run = st.selectbox("対象フライト", RUNS)
    launch_limit = st.number_input("横風限界 (m/s)", value=3.0, step=0.5)
    
    st.write("---")
    if st.button("📡 アメダス強制更新", use_container_width=True):
        if fetch_amedas_latest():
            st.success("更新完了")
            time.sleep(1)
            st.rerun()

# 5つのタブ構成
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🧭 現在状況", 
    "📊 予報比較", 
    "🖊️ SCW入力", 
    "🚩 実測報告", 
    "🚀 発進判定"
])

# --- タブ1: 現在状況 ---
with tab1:
    col_map, col_data = st.columns([2, 1])
    amedas_latest = load_amedas()
    saved_reports = load_report_data()
    
    with col_map:
        st.subheader("琵琶湖広域風況マップ")
        if amedas_latest:
            st.caption(f"AMeDAS 観測時刻: {amedas_latest['observed']}")
        fig = draw_ops_map(amedas_latest, None)
        st.pyplot(fig)
        
    with col_data:
        st.subheader("最新観測値一覧")
        if amedas_latest:
            df_list = []
            for st_id, s in amedas_latest["stations"].items():
                d_name = DIR_16_NAMES[s["wind_dir"]] if s["wind_dir"] is not None else "-"
                df_list.append({
                    "地点": s["name"],
                    "風速": f"{s['wind_speed']} m/s" if s["wind_speed"] is not None else "欠測",
                    "風向": d_name
                })
            st.table(pd.DataFrame(df_list))
        else:
            st.warning("アメダスデータが取得されていません。サイドバーから更新してください。")
            
        # 🌟【連携】タブ4で入力された実測報告の最新のものをサマリー表示
        st.subheader("最新の現地実測報告")
        if saved_reports:
            latest_rep = saved_reports[-1]
            st.info(f"📍 **{latest_rep['location']}** ({latest_rep['obs_time']})\n\n🧭 **{latest_rep['clock_dir']}時の方向** 平均 **{latest_rep['speed']}m/s**")
        else:
            st.caption("報告はまだありません。")

# --- タブ2: 予報比較 ---
with tab2:
    st.subheader("予報モデル比較 (開発中)")
    st.info("Phase 2 で実装予定: MSM予報データと実測のズレを視覚化します。")

# --- タブ3: SCW入力 ---
with tab3:
    st.markdown("## 🖊️ SCW (LFM) 要約値入力")
    st.caption("局地モデルの風速・風向分布を目視確認し、要約値を手入力します。")
    
    with st.form("scw_input_form"):
        col1, col2 = st.columns(2)
        with col1:
            publish_time = st.time_input("予報発表時刻 (例: 13:40更新)")
            target_time = st.selectbox("対象時刻", ["14:30", "15:00", "15:30", "16:00", "16:30"])
            location = st.selectbox("対象地点", SCW_LOCATIONS)
        with col2:
            clock_dir = st.selectbox("風向 (時計)", CLOCK_LABELS, index=0, format_func=lambda x: f"{x}時の方向")
            speed = st.number_input("風速 (m/s)", min_value=0.0, max_value=20.0, step=0.1, value=1.0)
            confidence = st.selectbox("信頼度", SCW_CONFIDENCE)
            
        memo = st.text_input("メモ・コメント (強化時刻や前倒しの兆候など)")
        submitted = st.form_submit_button("💾 SCWデータを記録・正規化する", type="primary", use_container_width=True)
        if submitted:
            save_scw_data(publish_time.strftime('%H:%M'), target_time, location, clock_dir, speed, confidence, memo)
            st.success(f"{location} の {target_time} 予測データを登録しました！")

    st.write("---")
    st.markdown("### 📋 登録済みのSCWデータ")
    saved_scw = load_scw_data()
    if saved_scw:
        for item in reversed(saved_scw[-5:]):
            st.markdown(f"**{item['target_time']}** | 📍 {item['location']} | 🧭 {item['clock_dir']}時 {item['speed']}m/s | 信頼度: {item['confidence']}")
            if item['memo']:
                st.caption(f"📝 {item['memo']}")
            st.divider()
    else:
        st.info("まだ登録されたデータはありません。")

# --- タブ4: 実測報告 (🌟新規実装) ---
with tab4:
    st.markdown(f"## 🚩 現地実測報告 【{current_run}】")
    st.caption("風見船やプラットホーム上のスタッフからの実測を報告し、ベクトルデータとして記録します。")
    
    # 時計ボタンのUI状態管理
    if "rep_clock" not in st.session_state:
        st.session_state["rep_clock"] = 12
    if "rep_loc" not in st.session_state:
        st.session_state["rep_loc"] = "プラットホーム"

    col_l, col_r = st.columns(2)
    with col_l:
        rep_loc = st.selectbox("観測地点", ["プラットホーム", "風見船A", "風見船B", "対岸", "その他"], 
                               index=["プラットホーム", "風見船A", "風見船B", "対岸", "その他"].index(st.session_state["rep_loc"]))
        st.session_state["rep_loc"] = rep_loc
    with col_r:
        obs_time = st.time_input("観測時刻", value=datetime.now(timezone(timedelta(hours=9))))

    # 以前洗練させた前方特化の時計ボタンUIを完全移植！
    st.write("### ① 風向き (時計)")
    main_clocks = [10, 11, 12, 1, 2]
    cols_main = st.columns(5)
    for i, hour in enumerate(main_clocks):
        with cols_main[i]:
            btn_type = "primary" if st.session_state.get("rep_clock") == hour else "secondary"
            if st.button(f"{hour}時", key=f"rep_clk_{hour}", type=btn_type, use_container_width=True):
                st.session_state["rep_clock"] = hour
                st.rerun()

    with st.expander("🔽 その他の方向 (3〜9時)"):
        other_clocks = [3, 4, 5, 6, 7, 8, 9]
        cols_o1 = st.columns(4)
        for i, hour in enumerate(other_clocks[:4]):
            with cols_o1[i]:
                btn_type = "primary" if st.session_state.get("rep_clock") == hour else "secondary"
                if st.button(f"{hour}時", key=f"rep_clk_{hour}", type=btn_type, use_container_width=True):
                    st.session_state["rep_clock"] = hour
                    st.rerun()
                    
        cols_o2 = st.columns(3)
        for i, hour in enumerate(other_clocks[4:]):
            with cols_o2[i]:
                btn_type = "primary" if st.session_state.get("rep_clock") == hour else "secondary"
                if st.button(f"{hour}時", key=f"rep_clk_{hour}", type=btn_type, use_container_width=True):
                    st.session_state["rep_clock"] = hour
                    st.rerun()

    st.write("### ② 観測詳細 ＆ 送信")
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        speed = st.number_input("平均風速 (m/s)", min_value=0.0, max_value=20.0, step=0.1, value=0.0)
    with col_s2:
        max_speed = st.number_input("最大瞬間風速 (m/s) ※任意", min_value=0.0, max_value=30.0, step=0.1, value=0.0)
    with col_s3:
        method = st.selectbox("観測方法", ["手持ち風速計", "旗・吹き流し", "体感"])
        
    memo = st.text_input("メモ・コメント (波・突風・危険兆候など)")

    if st.button("📤 実測データを記録・正規化する", type="primary", use_container_width=True):
        save_report_data(current_run, rep_loc, obs_time.strftime('%H:%M'), st.session_state["rep_clock"], speed, max_speed, method, memo)
        st.success(f"{rep_loc} ({st.session_state['rep_clock']}時の方向 {speed}m/s) の実測データを送信しました！")

    st.write("---")
    st.markdown("### 📋 最近の報告履歴")
    if saved_reports:
        # 今選んでいる走目のデータだけを抽出して表示
        run_reports = [r for r in saved_reports if r.get("run_name") == current_run]
        if run_reports:
            for item in reversed(run_reports[-5:]):
                st.markdown(f"**{item['obs_time']}** | 📍 {item['location']} | 🧭 {item['clock_dir']}時 平均{item['speed']}m/s (最大{item['max_speed']}m/s) | {item['method']}")
                if item['memo']:
                    st.caption(f"📝 {item['memo']}")
                st.divider()
        else:
            st.info(f"【{current_run}】の実測報告はまだありません。")
    else:
        st.info("まだ登録されたデータはありません。")

# --- タブ5: 発進判定 ---
with tab5:
    st.subheader("🚀 発進・経路判断 (開発中)")
