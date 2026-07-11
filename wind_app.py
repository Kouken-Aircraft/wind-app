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
# ⚙️ 設定・パス
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE_AMEDAS = os.path.join(BASE_DIR, "ops_amedas.json")
SCW_DATA_FILE = os.path.join(BASE_DIR, "ops_scw_data.json")
REPORT_DATA_FILE = os.path.join(BASE_DIR, "ops_report_data.json")
MSM_DATA_FILE = os.path.join(BASE_DIR, "ops_msm_data.json") # 🌟【新規】MSM予報DB

# 地点定義
AMEDAS_STATIONS = {
    "60131": {"name": "彦根", "lat": 35.2750, "lon": 136.2467},
    "60026": {"name": "長浜", "lat": 35.3850, "lon": 136.2650},
    "60111": {"name": "今津", "lat": 35.4117, "lon": 136.0350}
}
DIR_16_NAMES = ["無風", "北北東", "北東", "東北東", "東", "東南東", "南東", "南南東", "南", "南南西", "南西", "西南西", "西", "西北西", "北西", "北北西", "北"]

# ==========================================
# 🛠️ 数学・変換ユーティリティ
# ==========================================
def clock_to_uv(clock_dir, speed):
    """時計方向(1-12)を気象学的なu, v成分に変換"""
    if speed == 0: return 0.0, 0.0
    # 12時=北(180度から吹く), 3時=東(270度から吹く)
    angle_deg = (clock_dir * 30) % 360
    # 数学的な角度へ(北0, 東90...)
    rad = math.radians(angle_deg)
    u = -speed * math.sin(rad)
    v = -speed * math.cos(rad)
    return round(u, 2), round(v, 2)

def amedas_dir_to_uv(dir_idx, speed):
    """アメダス16方位(0-16)をu, vに変換"""
    if dir_idx == 0 or speed == 0: return 0.0, 0.0
    angle_deg = (dir_idx - 1) * 22.5
    rad = math.radians(angle_deg)
    u = -speed * math.sin(rad)
    v = -speed * math.cos(rad)
    return round(u, 2), round(v, 2)

# ==========================================
# 📡 AMeDAS / 🖊️ SCW / 🚩 Report / 🌊 MSM 管理
# ==========================================
def fetch_amedas_latest():
    try:
        time_url = "https://www.jma.go.jp/bosai/amedas/data/latest_time.txt"
        latest_time_str = requests.get(time_url).text.strip()
        time_key = datetime.fromisoformat(latest_time_str).strftime("%Y%m%d%H%M%S")
        data_url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_key}.json"
        all_data = requests.get(data_url).json()
        
        extracted = {"observed": latest_time_str, "stations": {}}
        for st_id, info in AMEDAS_STATIONS.items():
            if st_id in all_data:
                s = all_data[st_id]
                spd = s.get("wind", [0.0])[0]
                dr = s.get("wndDir", [0])[0]
                u, v = amedas_dir_to_uv(dr, spd)
                extracted["stations"][st_id] = {
                    "name": info["name"], "speed": spd, "dir": dr, "u": u, "v": v
                }
        with open(DATA_FILE_AMEDAS, "w", encoding="utf-8") as f:
            json.dump(extracted, f, ensure_ascii=False, indent=2)
        return True
    except: return False

def load_data(path):
    if not os.path.exists(path): return [] if "data" in path else None
    with open(path, "r", encoding="utf-8") as f: return json.load(f)

def save_scw_data(pub, target, loc, clock, speed, conf, memo):
    data = load_data(SCW_DATA_FILE)
    u, v = clock_to_uv(clock, speed)
    data.append({
        "time": target, "location": loc, "speed": speed, "u": u, "v": v, 
        "conf": conf, "memo": memo, "pub": pub, "type": "FORECAST_SCW"
    })
    with open(SCW_DATA_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)

def save_report_data(run, loc, obs_time, clock, speed, max_spd, method, memo):
    data = load_data(REPORT_DATA_FILE)
    u, v = clock_to_uv(clock, speed)
    data.append({
        "time": obs_time, "location": loc, "speed": speed, "u": u, "v": v, 
        "max_speed": max_spd, "method": method, "memo": memo, "run": run, "type": "ACTUAL_REPORT"
    })
    with open(REPORT_DATA_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)

# ==========================================
# 🚀 メイン UI
# ==========================================
st.set_page_config(page_title="Birdman Wind Ops", page_icon="🦅", layout="wide")
st.markdown("# 🦅 Birdman Wind Ops <small>Ver.95</small>", unsafe_allow_html=True)

with st.sidebar:
    st.header("🌐 Global Settings")
    current_run = st.selectbox("対象フライト", [f"{i}走目" for i in range(1, 21)])
    launch_limit = st.number_input("横風限界 (m/s)", value=3.0, step=0.5)
    if st.button("📡 アメダス強制更新", use_container_width=True):
        if fetch_amedas_latest(): st.success("更新完了")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🧭 現在状況", "📊 予報比較", "🖊️ SCW入力", "🚩 実測報告", "🚀 発進判定"])

# --- タブ2: 予報比較 (Phase 2実装) ---
with tab2:
    st.subheader("📊 予報 vs 実況 統合タイムライン")
    st.caption("SCW予報値とAMeDAS/実測値を同じ時刻軸で比較し、悪化の「前倒し」を検出します。")

    # データの統合処理
    amedas = load_data(DATA_FILE_AMEDAS)
    scw = load_data(SCW_DATA_FILE)
    reports = load_data(REPORT_DATA_FILE)
    
    compare_list = []
    
    # SCW予報をリストに追加
    for item in scw:
        compare_list.append({
            "時刻": item["time"], "地点": item["location"], "ソース": "予報(SCW)",
            "風速": item["speed"], "u": item["u"], "v": item["v"], "信頼度": item["conf"]
        })
        
    # 最新アメダスを追加
    if amedas:
        obs_hhmm = datetime.fromisoformat(amedas["observed"]).strftime("%H:%M")
        for st_id, s in amedas["stations"].items():
            compare_list.append({
                "時刻": obs_hhmm, "地点": s["name"], "ソース": "実況(AMeDAS)",
                "風速": s["speed"], "u": s["u"], "v": s["v"], "信頼度": "高"
            })
            
    # 実測報告を追加
    for r in reports:
        if r["run"] == current_run:
            compare_list.append({
                "時刻": r["time"], "地点": r["location"], "ソース": "現場(実測)",
                "風速": r["speed"], "u": r["u"], "v": r["v"], "信頼度": "最高"
            })

    if compare_list:
        df_comp = pd.DataFrame(compare_list).sort_values("時刻")
        
        # 特定地点の比較表示 (例: 彦根周辺)
        target_loc = st.selectbox("比較対象地点", ["彦根", "プラットホーム", "今津", "長浜"])
        df_target = df_comp[df_comp["地点"].str.contains(target_loc)]
        
        if not df_target.empty:
            st.table(df_target)
            
            # ズレの解析
            forecast_now = df_target[df_target["ソース"].str.contains("予報")]
            actual_now = df_target[df_target["ソース"].str.contains("実況|現場")]
            
            if not forecast_now.empty and not actual_now.empty:
                f_val = forecast_now.iloc[-1]
                a_val = actual_now.iloc[-1]
                diff = a_val["風速"] - f_val["風速"]
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if diff > 0.5:
                        st.warning(f"⚠️ **悪化の兆候:** 予報より {diff:.1f}m/s 風が強まっています（前倒しの可能性）")
                    elif diff < -0.5:
                        st.info(f"✅ **予報より穏やか:** 予報より {abs(diff):.1f}m/s 弱いです")
                    else:
                        st.success("🎯 **予報通り:** 現在の風はモデル予測の範囲内です")
                with col_b:
                    # 風向のズレ(簡易)
                    st.metric("実測風速", f"{a_val['風速']} m/s", delta=f"{diff:.1f} vs 予報")
        else:
            st.info(f"{target_loc} に関する予報と実況の同時刻データがまだありません。")
    else:
        st.info("比較するためのデータ（SCW入力や実測）を先に登録してください。")

# --- タブ1: 現在状況 ---
with tab1:
    amedas_latest = load_data(DATA_FILE_AMEDAS)
    col_map, col_list = st.columns([2, 1])
    with col_map:
        st.subheader("琵琶湖広域風況マップ")
        # マップ描画ロジック (Ver.94継承)
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.set_facecolor('#E3F2FD')
        for st_id, info in AMEDAS_STATIONS.items():
            ax.plot(info["lon"], info["lat"], 'o', color='#1A237E')
            if amedas_latest and st_id in amedas_latest["stations"]:
                s = amedas_latest["stations"][st_id]
                ax.text(info["lon"], info["lat"]-0.01, f"{s['name']}\n{s['speed']}m/s", fontsize=10, fontweight='bold', ha='center')
        st.pyplot(fig)
    with col_list:
        st.subheader("最新の概況")
        if amedas_latest: st.write(f"アメダス観測: {amedas_latest['observed']}")
        # タブ4からの最新報告を1件表示
        reps = load_data(REPORT_DATA_FILE)
        if reps:
            lr = reps[-1]
            st.info(f"🚩 **現地最新 ({lr['time']})**\n\n{lr['location']} : {lr['speed']}m/s")

# --- タブ3: SCW入力 (Ver.94継承) ---
with tab3:
    st.markdown("## 🖊️ SCW 要約値入力")
    with st.form("scw_form"):
        p_t = st.time_input("発表時刻")
        t_t = st.selectbox("対象時刻", [f"{h}:{m:02d}" for h in range(4, 20) for m in [0, 30]])
        loc = st.selectbox("地点", ["彦根沖", "今津沖", "長浜沖", "南小松沖"])
        clock = st.selectbox("風向(時)", range(1, 13), index=11)
        spd = st.number_input("風速(m/s)", step=0.1)
        conf = st.selectbox("信頼度", ["高", "中", "低"])
        memo = st.text_input("備考")
        if st.form_submit_button("記録・正規化"):
            save_scw_data(p_t.strftime("%H:%M"), t_t, loc, clock, spd, conf, memo)
            st.rerun()

# --- タブ4: 実測報告 (Ver.94継承) ---
with tab4:
    st.subheader(f"🚩 現地実測報告 【{current_run}】")
    # (Ver.94の時計ボタンUI、入力ロジックをここに保持)
    loc = st.selectbox("地点", ["プラットホーム", "風見船A", "風見船B"])
    clock = st.radio("風向 (時)", [10, 11, 12, 1, 2], horizontal=True)
    spd = st.number_input("平均風速", step=0.1)
    if st.button("送信"):
        save_report_data(current_run, loc, datetime.now().strftime("%H:%M"), clock, spd, 0, "手速計", "")
        st.rerun()

# --- タブ5: 発進判定 ---
with tab5:
    st.subheader("🚀 発進判定メモ")
    st.info("Phase 4 で実装: 誰が、いつ、どのデータを見てGO/STAYを決めたかの履歴を残します。")
