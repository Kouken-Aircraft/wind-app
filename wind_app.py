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
JUDGE_DATA_FILE = os.path.join(BASE_DIR, "ops_judge_data.json")

# アメダス地点定義
AMEDAS_STATIONS = {
    "60131": {"name": "彦根", "lat": 35.2750, "lon": 136.2467},
    "60026": {"name": "長浜", "lat": 35.3850, "lon": 136.2650},
    "60111": {"name": "今津", "lat": 35.4117, "lon": 136.0350},
    "60191": {"name": "南小松", "lat": 35.2400, "lon": 135.9633}
}

# ==========================================
# 🛠️ 数学・ベクトル計算
# ==========================================
def clock_to_uv(clock_dir, speed):
    if speed <= 0: return 0.0, 0.0
    rad = math.radians((clock_dir * 30) % 360)
    u = -speed * math.sin(rad)
    v = -speed * math.cos(rad)
    return round(u, 2), round(v, 2)

def calculate_crosswind(u, v, runway_deg):
    speed = math.sqrt(u**2 + v**2)
    if speed < 0.1: return 0.0
    wind_from_deg = (math.degrees(math.atan2(-u, -v)) + 360) % 360
    relative_angle = math.radians(wind_from_deg - runway_deg)
    return round(speed * math.sin(relative_angle), 2)

# ==========================================
# 💾 データ管理
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

def fetch_amedas():
    try:
        time_url = "https://www.jma.go.jp/bosai/amedas/data/latest_time.txt"
        t_str = requests.get(time_url, timeout=5).text.strip()
        t_key = datetime.fromisoformat(t_str).strftime("%Y%m%d%H%M%S")
        all_data = requests.get(f"https://www.jma.go.jp/bosai/amedas/data/map/{t_key}.json", timeout=5).json()
        ext = {"observed": t_str, "stations": {}}
        for sid, info in AMEDAS_STATIONS.items():
            if sid in all_data:
                s = all_data[sid]
                spd = s.get("wind", [0])[0]
                dr = s.get("wndDir", [0])[0]
                ang = (dr - 1) * 22.5 if dr > 0 else 0
                u = -spd * math.sin(math.radians(ang))
                v = -spd * math.cos(math.radians(ang))
                ext["stations"][sid] = {"name": info["name"], "speed": spd, "u": u, "v": v, "lat": info["lat"], "lon": info["lon"]}
        save_data_safe(DATA_FILE_AMEDAS, ext)
        return True
    except: return False

# ==========================================
# 🚀 UI本体
# ==========================================
st.set_page_config(page_title="Birdman Wind Ops", page_icon="🦅", layout="wide")
st.markdown("# 🦅 Birdman Wind Ops <small>Ver.99</small>", unsafe_allow_html=True)

with st.sidebar:
    st.header("🌐 全体設定")
    current_run = st.selectbox("対象フライト", [f"{i}走目" for i in range(1, 21)])
    runway_heading = st.number_input("プラットホーム方位 (deg)", value=270, help="西=270, 北=0")
    launch_limit = st.number_input("横風限界 (m/s)", value=3.0, step=0.1)
    if st.button("📡 アメダス最新データ取得", use_container_width=True):
        if fetch_amedas(): st.success("AMeDAS更新成功")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🧭 現在状況", "📊 予報比較", "🖊️ SCW予報入力", "🚩 現地報告", "🚀 発進判定"])

# --- タブ1: 現在状況 (メインダッシュボード) ---
with tab1:
    amedas = load_data_safe(DATA_FILE_AMEDAS, None)
    reports = load_data_safe(REPORT_DATA_FILE, [])
    
    col_l, col_r = st.columns([2, 1])
    
    with col_l:
        st.subheader("琵琶湖 統合風況マップ")
        fig, ax = plt.subplots(figsize=(10, 8))
        ax.set_facecolor('#E3F2FD') # 琵琶湖の色
        
        # マップ範囲
        ax.set_xlim(135.8, 136.4); ax.set_ylim(35.0, 35.5)
        
        # AMeDASプロット
        if amedas:
            for sid, s in amedas["stations"].items():
                u, v = s.get("u", 0), s.get("v", 0)
                ax.quiver(s["lon"], s["lat"], u, v, color='blue', scale=20, width=0.01)
                ax.text(s["lon"], s["lat"]-0.01, f"{s['name']}\n{s.get('speed')}m/s", ha='center', fontsize=9)
        
        # 現地報告プロット (最新のもの)
        if reports:
            lr = reports[-1]
            # 簡略化のためプラットホーム付近に描画
            ax.quiver(136.24, 35.27, lr.get("u", 0), lr.get("v", 0), color='red', scale=20, width=0.015)
            ax.text(136.24, 35.25, f"現地報告\n{lr.get('speed')}m/s", color='red', fontweight='bold', ha='center')
            
        ax.set_xlabel("経度"); ax.set_ylabel("緯度")
        st.pyplot(fig)

    with col_r:
        st.subheader("発進可否判定")
        actual = reports[-1] if reports else (amedas["stations"].get("60131") if amedas else None)
        if actual:
            cw = calculate_crosswind(actual.get("u", 0), actual.get("v", 0), runway_heading)
            cw_pct = (abs(cw) / launch_limit) * 100
            st.metric("風速", f"{actual.get('speed', 0)} m/s")
            st.metric("横風成分", f"{abs(cw)} m/s", delta="左から" if cw > 0 else "右から", delta_color="inverse")
            
            if cw_pct > 100: st.error(f"❌ STAY: 限界超過 ({cw_pct:.1f}%)")
            elif cw_pct > 80: st.warning(f"⚠️ CAUTION: 限界接近 ({cw_pct:.1f}%)")
            else: st.success(f"✅ GO: 安定 ({cw_pct:.1f}%)")
        else:
            st.info("観測データ待ち...")

# --- タブ3: SCW予報入力 ---
with tab3:
    st.subheader("🖊️ SCW 要約値入力")
    with st.form("scw_form"):
        col1, col2 = st.columns(2)
        with col1:
            t_t = st.selectbox("予報対象時刻", [f"{h:02d}:{m:02d}" for h in range(4, 20) for m in [0, 30]])
            loc = st.selectbox("対象地点", ["彦根沖", "今津沖", "長浜沖", "南小松沖"])
        with col2:
            clock = st.selectbox("風向 (時)", range(1, 13), index=11)
            spd = st.number_input("風速 (m/s)", step=0.1)
        if st.form_submit_button("予報データを登録"):
            u, v = clock_to_uv(clock, spd)
            data = load_data_safe(SCW_DATA_FILE, [])
            data.append({"time": t_t, "location": loc, "speed": spd, "u": u, "v": v})
            save_data_safe(SCW_DATA_FILE, data); st.rerun()

# --- タブ4: 現地報告 (実測) ---
with tab4:
    st.subheader(f"🚩 現場実測報告 【{current_run}】")
    if "rep_clock" not in st.session_state: st.session_state["rep_clock"] = 12
    c1, c2 = st.columns(2)
    with c1: loc = st.selectbox("報告元", ["プラットホーム", "風見船A", "風見船B"])
    with c2: obs_t = st.time_input("観測時刻")
    
    st.write("風向き (時)")
    btn_cols = st.columns(5)
    for i, h in enumerate([10, 11, 12, 1, 2]):
        if btn_cols[i].button(f"{h}時", type="primary" if st.session_state["rep_clock"] == h else "secondary", key=f"btn_{h}", use_container_width=True):
            st.session_state["rep_clock"] = h; st.rerun()
    
    spd = st.number_input("平均風速 (m/s)", step=0.1, key="rep_spd")
    if st.button("実測を送信", type="primary", use_container_width=True):
        u, v = clock_to_uv(st.session_state["rep_clock"], spd)
        data = load_data_safe(REPORT_DATA_FILE, [])
        data.append({"time": obs_t.strftime("%H:%M"), "location": loc, "speed": spd, "u": u, "v": v, "run": current_run})
        save_data_safe(REPORT_DATA_FILE, data); st.success("報告完了"); st.rerun()

# --- タブ5: 発進判定 ---
with tab5:
    st.subheader("🚀 判定記録ログ")
    with st.form("j_form"):
        res = st.radio("最終判定", ["🔴 STAY", "🟡 CAUTION", "🟢 GO"], horizontal=True)
        txt = st.text_area("理由・指示")
        if st.form_submit_button("判定を記録"):
            data = load_data_safe(JUDGE_DATA_FILE, [])
            data.append({"time": datetime.now().strftime("%H:%M"), "run": current_run, "res": res, "txt": txt})
            save_data_safe(JUDGE_DATA_FILE, data); st.rerun()
    
    for h in reversed(load_data_safe(JUDGE_DATA_FILE, [])):
        st.write(f"**[{h['time']}] {h['res']}** ({h['run']})")
        st.caption(h['txt']); st.divider()

# --- タブ2: 予報比較 ---
with tab2:
    st.subheader("📊 予報比較タイムライン")
    combined = []
    for s in load_data_safe(SCW_DATA_FILE, []): combined.append({"時刻": s["time"], "ソース": "予報(SCW)", "風速": s["speed"], "地点": s["location"]})
    for r in load_data_safe(REPORT_DATA_FILE, []): combined.append({"時刻": r["time"], "ソース": "実測報告", "風速": r["speed"], "地点": r["location"]})
    if combined: st.dataframe(pd.DataFrame(combined).sort_values("時刻"), use_container_width=True)
