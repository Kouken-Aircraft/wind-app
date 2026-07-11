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
MSM_DATA_FILE = os.path.join(BASE_DIR, "ops_msm_data.json")
JUDGE_DATA_FILE = os.path.join(BASE_DIR, "ops_judge_data.json")

AMEDAS_STATIONS = {
    "60131": {"name": "彦根", "lat": 35.2750, "lon": 136.2467},
    "60026": {"name": "長浜", "lat": 35.3850, "lon": 136.2650},
    "60111": {"name": "今津", "lat": 35.4117, "lon": 136.0350}
}
DIR_16_NAMES = ["無風", "北北東", "北東", "東北東", "東", "東南東", "南東", "南南東", "南", "南南西", "南西", "西南西", "西", "西北西", "北西", "北北西", "北"]

# ==========================================
# 🛠️ ユーティリティ (安全第一)
# ==========================================
def load_data_safe(path, default=[]):
    if not os.path.exists(path): return default
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except: return default

def save_data_safe(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except: pass

def clock_to_uv(clock_dir, speed):
    if speed <= 0: return 0.0, 0.0
    rad = math.radians((clock_dir * 30) % 360)
    return round(-speed * math.sin(rad), 2), round(-speed * math.cos(rad), 2)

def calculate_crosswind(u, v, runway_deg):
    speed = math.sqrt(u**2 + v**2)
    if speed < 0.1: return 0.0
    wind_from_deg = (math.degrees(math.atan2(-u, -v)) + 360) % 360
    relative_angle = math.radians(wind_from_deg - runway_deg)
    return round(speed * math.sin(relative_angle), 2)

# ==========================================
# 📡 AMeDAS 自動取得
# ==========================================
def fetch_amedas():
    try:
        time_url = "https://www.jma.go.jp/bosai/amedas/data/latest_time.txt"
        t_str = requests.get(time_url, timeout=5).text.strip()
        t_key = datetime.fromisoformat(t_str).strftime("%Y%m%d%H%M%S")
        all_data = requests.get(f"https://www.jma.go.jp/bosai/amedas/data/map/{t_key}.json", timeout=5).json()
        ext = {"observed": t_str, "stations": {}}
        for sid, info in AMEDAS_STATIONS.items():
            if sid in all_data:
                s = all_data[sid]; spd = s.get("wind", [0])[0]; dr = s.get("wndDir", [0])[0]
                ang = (dr - 1) * 22.5 if dr > 0 else 0
                u = -spd * math.sin(math.radians(ang)); v = -spd * math.cos(math.radians(ang))
                ext["stations"][sid] = {"name": info["name"], "speed": spd, "dir": dr, "u": u, "v": v}
        save_data_safe(DATA_FILE_AMEDAS, ext); return True
    except: return False

# ==========================================
# 🚀 メイン UI
# ==========================================
st.set_page_config(page_title="Birdman Wind Ops", page_icon="🦅", layout="wide")
st.markdown("# 🦅 Birdman Wind Ops <small>Ver.98</small>", unsafe_allow_html=True)

with st.sidebar:
    st.header("🌐 Global Settings")
    current_run = st.selectbox("対象フライト", [f"{i}走目" for i in range(1, 21)])
    runway_heading = st.number_input("離陸方位 (deg)", value=270, help="西=270, 北=0")
    launch_limit = st.number_input("横風限界 (m/s)", value=3.0, step=0.1)
    
    st.write("---")
    if st.button("📡 最新データ一括更新", use_container_width=True):
        if fetch_amedas(): st.success("更新成功")
        else: st.error("AMeDAS取得失敗")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🧭 現在状況", "📊 予報比較", "🖊️ SCW入力", "🚩 実測報告", "🚀 発進判定"])

# --- タブ1: 現在状況 ---
with tab1:
    amedas = load_data_safe(DATA_FILE_AMEDAS, None)
    reports = load_data_safe(REPORT_DATA_FILE, [])
    
    col_main, col_sub = st.columns([2, 1])
    with col_main:
        st.subheader("現在の風況（機体相対）")
        # 代表地点の選定（現場実測を最優先、なければ彦根）
        actual = reports[-1] if reports else (amedas["stations"].get("60131") if amedas else None)
        
        if actual:
            u = actual.get("u", 0.0); v = actual.get("v", 0.0); spd = actual.get("speed", 0.0)
            cw = calculate_crosswind(u, v, runway_heading)
            cw_pct = (abs(cw) / launch_limit) * 100
            
            m1, m2, m3 = st.columns(3)
            m1.metric("風速 (m/s)", f"{spd}")
            m2.metric("横風成分 (m/s)", f"{abs(cw)}", delta="左から" if cw > 0 else "右から")
            m3.metric("限界到達度", f"{cw_pct:.1f} %")
            
            # 安全判定
            if cw_pct > 100: st.error(f"🚨 横風限界超過 ({cw_pct:.1f}%)")
            elif cw_pct > 80: st.warning(f"⚠️ 限界接近 ({cw_pct:.1f}%)")
            else: st.success(f"✅ 発進可能 ({cw_pct:.1f}%)")
            
            # 簡易マップ表示
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.set_facecolor('#E3F2FD')
            for sid, info in AMEDAS_STATIONS.items():
                ax.plot(info["lon"], info["lat"], 'o', color='#1A237E')
                if amedas and sid in amedas["stations"]:
                    s = amedas["stations"][sid]
                    ax.text(info["lon"], info["lat"]-0.01, f"{s['name']}\n{s['speed']}m/s", ha='center', fontsize=8)
            st.pyplot(fig)
        else:
            st.info("データがありません。サイドバーから更新してください。")

# --- タブ3: SCW入力 (Phase 3 堅牢版) ---
with tab3:
    st.subheader("🖊️ SCW 要約値入力")
    with st.form("scw_form"):
        col1, col2 = st.columns(2)
        with col1:
            t_t = st.selectbox("対象時刻", [f"{h:02d}:{m:02d}" for h in range(4, 20) for m in [0, 30]])
            loc = st.selectbox("地点", ["彦根沖", "今津沖", "長浜沖", "南小松沖"])
        with col2:
            clock = st.selectbox("風向(時)", range(1, 13), index=11)
            spd = st.number_input("風速(m/s)", step=0.1)
        if st.form_submit_button("予報を登録"):
            u, v = clock_to_uv(clock, spd)
            data = load_data_safe(SCW_DATA_FILE, [])
            data.append({"time": t_t, "location": loc, "speed": spd, "u": u, "v": v})
            save_data_safe(SCW_DATA_FILE, data); st.rerun()

# --- タブ4: 実測報告 (Phase 3 堅牢版) ---
with tab4:
    st.subheader(f"🚩 現地実測報告 【{current_run}】")
    if "rep_clock" not in st.session_state: st.session_state["rep_clock"] = 12
    col1, col2 = st.columns(2)
    with col1: loc = st.selectbox("観測地点", ["プラットホーム", "風見船A", "風見船B"])
    with col2: obs_t = st.time_input("観測時刻")
    
    st.write("風向き (時)")
    btn_cols = st.columns(5)
    for i, h in enumerate([10, 11, 12, 1, 2]):
        if btn_cols[i].button(f"{h}時", type="primary" if st.session_state["rep_clock"] == h else "secondary", use_container_width=True):
            st.session_state["rep_clock"] = h; st.rerun()
    
    spd = st.number_input("平均風速 (m/s)", step=0.1, key="rep_spd")
    if st.button("実測を送信", type="primary", use_container_width=True):
        u, v = clock_to_uv(st.session_state["rep_clock"], spd)
        data = load_data_safe(REPORT_DATA_FILE, [])
        data.append({"time": obs_t.strftime("%H:%M"), "location": loc, "speed": spd, "u": u, "v": v, "run": current_run})
        save_data_safe(REPORT_DATA_FILE, data); st.success("報告完了"); time.sleep(1); st.rerun()

# --- タブ5: 発進判定 ---
with tab5:
    st.subheader("🚀 発進判定ログ")
    with st.form("judge_form"):
        status = st.radio("判定", ["🔴 STAY", "🟡 CAUTION", "🟢 GO"], horizontal=True)
        reason = st.text_area("理由")
        if st.form_submit_button("判定記録"):
            data = load_data_safe(JUDGE_DATA_FILE, [])
            data.append({"time": datetime.now().strftime("%H:%M"), "run": current_run, "status": status, "reason": reason})
            save_data_safe(JUDGE_DATA_FILE, data); st.rerun()
    
    hist = load_data_safe(JUDGE_DATA_FILE, [])
    for h in reversed(hist):
        st.write(f"**[{h.get('time')}] {h.get('status')}** ({h.get('run')})")
        st.caption(h.get('reason'))
        st.divider()

# --- タブ2: 予報比較 (安定版) ---
with tab2:
    st.subheader("📊 予報比較タイムライン")
    scw = load_data_safe(SCW_DATA_FILE, [])
    reps = load_data_safe(REPORT_DATA_FILE, [])
    msm = load_data_safe(MSM_DATA_FILE, []) # MSMが取得済みの時のみ表示
    
    combined = []
    for s in scw: combined.append({"時刻": s.get("time"), "ソース": "SCW予報", "風速": s.get("speed"), "地点": s.get("location")})
    for r in reps: combined.append({"時刻": r.get("time"), "ソース": "実測報告", "風速": r.get("speed"), "地点": r.get("location")})
    for m in msm: combined.append({"時刻": m.get("time"), "ソース": "MSM(予)", "風速": m.get("speed"), "地点": m.get("location")})
    
    if combined:
        st.dataframe(pd.DataFrame(combined).sort_values("時刻"), use_container_width=True)
    else:
        st.info("データがありません。")
