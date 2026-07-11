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
# 📡 AMeDAS 自動取得ロジック (Ver.90より復元)
# ==========================================
def fetch_amedas_latest():
    """気象庁JSONから最新のアメダスデータを取得・保存"""
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
# 🖊️ SCW データ管理ロジック (Ver.92より継承)
# ==========================================
def load_scw_data():
    if not os.path.exists(SCW_DATA_FILE): return []
    try:
        with open(SCW_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def save_scw_data(publish_time, target_time, location, clock_dir, speed, confidence, memo):
    current_data = load_scw_data()
    
    # 正規化（u, vベクトル変換）
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
# 🚀 メイン UI
# ==========================================
st.set_page_config(page_title="Birdman Wind Ops", page_icon="🦅", layout="wide")
st.markdown("# 🦅 Birdman Wind Ops <small>Ver.93</small>", unsafe_allow_html=True)

# サイドバー：全体共有設定
with st.sidebar:
    st.header("🌐 Global Settings")
    current_run = st.selectbox("対象フライト", [f"{i}走目" for i in range(1, 21)])
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

# --- タブ1: 現在状況 (AMeDAS表示復元) ---
with tab1:
    col_map, col_data = st.columns([2, 1])
    amedas_latest = load_amedas()
    
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
            st.warning("アメダスデータがまだ取得されていません。サイドバーから更新してください。")

# --- タブ2: 予報比較 ---
with tab2:
    st.subheader("予報モデル比較 (開発中)")
    st.info("Phase 2 で実装予定: MSM予報データと実測のズレを視覚化します。")

# --- タブ3: SCW入力 (Ver.92より継承) ---
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

# --- タブ4: 実測報告 ---
with tab4:
    st.subheader("🚩 現地実測報告")
    st.info("Phase 3 にて、以前作成した滑走路用の直感的な風向・風速入力UIをここに完全移植します。")

# --- タブ5: 発進判定 ---
with tab5:
    st.subheader("🚀 発進・経路判断 (開発中)")
