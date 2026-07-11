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
# 役割ごとにファイルを分離
DB_AMEDAS = os.path.join(BASE_DIR, "ops_amedas.json")
DB_FORECAST = os.path.join(BASE_DIR, "ops_forecast.json") # MSM/SCW兼用
DB_REPORT = os.path.join(BASE_DIR, "ops_report.json")
DB_JUDGE = os.path.join(BASE_DIR, "ops_judge.json")

# 琵琶湖観測地点
STATIONS = {
    "60131": {"name": "彦根", "lat": 35.2750, "lon": 136.2467},
    "60026": {"name": "長浜", "lat": 35.3850, "lon": 136.2650},
    "60111": {"name": "今津", "lat": 35.4117, "lon": 136.0350},
    "60191": {"name": "南小松", "lat": 35.2400, "lon": 135.9633}
}

# ==========================================
# 🛠️ 共通エンジン (u, v ベクトル正規化)
# ==========================================
def clock_to_uv(clock_dir, speed):
    if speed <= 0: return 0.0, 0.0
    rad = math.radians((clock_dir * 30) % 360)
    return round(-speed * math.sin(rad), 2), round(-speed * math.cos(rad), 2)

def calculate_crosswind(u, v, runway_deg):
    speed = math.sqrt(u**2 + v**2)
    if speed < 0.1: return 0.0
    wind_from_deg = (math.degrees(math.atan2(-u, -v)) + 360) % 360
    rel_angle = math.radians(wind_from_deg - runway_deg)
    return round(speed * math.sin(rel_angle), 2)

# ==========================================
# 💾 データ入出力 (堅牢化)
# ==========================================
def load_db(path, default=[]):
    if not os.path.exists(path): return default
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except: return default

def save_db(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ==========================================
# 📡 AMeDAS 自動取得エンジン
# ==========================================
def fetch_amedas():
    try:
        t_url = "https://www.jma.go.jp/bosai/amedas/data/latest_time.txt"
        t_str = requests.get(t_url, timeout=5).text.strip()
        t_key = datetime.fromisoformat(t_str).strftime("%Y%m%d%H%M%S")
        url = f"https://www.jma.go.jp/bosai/amedas/data/map/{t_key}.json"
        all_d = requests.get(url, timeout=5).json()
        ext = {"observed": t_str, "stations": {}}
        for sid, info in STATIONS.items():
            if sid in all_d:
                s = all_d[sid]; spd = s.get("wind", [0])[0]; dr = s.get("wndDir", [0])[0]
                ang = (dr - 1) * 22.5 if dr > 0 else 0
                u = -spd * math.sin(math.radians(ang)); v = -spd * math.cos(math.radians(ang))
                ext["stations"][sid] = {"name": info["name"], "speed": spd, "u": u, "v": v, "lat": info["lat"], "lon": info["lon"]}
        save_db(DB_AMEDAS, ext); return True
    except: return False

# ==========================================
# 🚀 UI メイン
# ==========================================
st.set_page_config(page_title="Birdman Wind Ops", page_icon="🦅", layout="wide")
st.markdown("# 🦅 Birdman Wind Ops <small>Ver.100 Final</small>", unsafe_allow_html=True)

with st.sidebar:
    st.header("🌐 Global Settings")
    current_run = st.selectbox("対象フライト", [f"{i}走目" for i in range(1, 21)])
    runway_heading = st.number_input("プラットホーム方位 (deg)", value=270, help="西=270")
    launch_limit = st.number_input("横風限界 (m/s)", value=3.0, step=0.1)
    st.write("---")
    if st.button("📡 AMeDAS実況を更新", use_container_width=True):
        if fetch_amedas(): st.success("更新成功")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🧭 現在状況", "📊 予報比較", "🖊️ 予報入力", "🚩 実測報告", "🚀 発進判定"])

# --- タブ1: 現在状況 (ダッシュボード) ---
with tab1:
    amedas = load_db(DB_AMEDAS, None); reps = load_db(DB_REPORT, [])
    col_l, col_r = st.columns([2, 1])
    with col_l:
        st.subheader("琵琶湖 統合風況マップ")
        fig, ax = plt.subplots(figsize=(8, 6)); ax.set_facecolor('#E3F2FD')
        # AMeDAS描画
        if amedas:
            for sid, s in amedas["stations"].items():
                ax.quiver(s["lon"], s["lat"], s["u"], s["v"], color='blue', scale=25)
                ax.text(s["lon"], s["lat"]-0.01, f"{s['name']}\n{s['speed']}m", ha='center', fontsize=9)
        # 現地実測描画 (最新1件)
        if reps:
            lr = reps[-1]; ax.quiver(136.24, 35.27, lr["u"], lr["v"], color='red', scale=25)
            ax.text(136.24, 35.25, "現地報告", color='red', fontweight='bold', ha='center')
        ax.set_xlim(135.8, 136.5); ax.set_ylim(35.0, 35.5); st.pyplot(fig)

    with col_r:
        st.subheader("横風判定")
        actual = reps[-1] if reps else (amedas["stations"].get("60131") if amedas else None)
        if actual:
            cw = calculate_crosswind(actual["u"], actual["v"], runway_heading); cw_pct = (abs(cw)/launch_limit)*100
            st.metric("実測風速", f"{actual['speed']} m/s")
            st.metric("横風成分", f"{abs(cw)} m/s", delta="左から" if cw > 0 else "右から", delta_color="inverse")
            if cw_pct > 100: st.error(f"❌ STAY ({cw_pct:.1f}%)")
            elif cw_pct > 80: st.warning(f"⚠️ CAUTION ({cw_pct:.1f}%)")
            else: st.success(f"✅ GO ({cw_pct:.1f}%)")
        else: st.info("データ未取得")

# --- タブ3: 予報入力 (MSM/SCW手入力) ---
with tab3:
    st.subheader("🖊️ MSM/SCW 予報値入力")
    with st.form("fore_form"):
        c1, c2 = st.columns(2)
        with c1: 
            src = st.selectbox("予報元", ["SCW(LFM)", "MSM(広域)"])
            t_t = st.selectbox("対象時刻", [f"{h:02d}:{m:02d}" for h in range(4, 20) for m in [0, 30]])
        with c2:
            clock = st.selectbox("風向(時)", range(1, 13), index=11)
            spd = st.number_input("風速(m/s)", step=0.1)
        if st.form_submit_button("予報を記録"):
            u, v = clock_to_uv(clock, spd); db = load_db(DB_FORECAST)
            db.append({"time": t_t, "src": src, "speed": spd, "u": u, "v": v})
            save_db(DB_FORECAST, db); st.success("記録完了"); st.rerun()

# --- タブ4: 実測報告 ---
with tab4:
    st.subheader(f"🚩 現場実測報告 【{current_run}】")
    if "rep_clock" not in st.session_state: st.session_state["rep_clock"] = 12
    c1, c2 = st.columns(2)
    with c1: loc = st.selectbox("場所", ["プラットホーム", "風見船A", "風見船B"])
    with c2: obs_t = st.time_input("時刻")
    st.write("風向き (時)")
    btn_cols = st.columns(5)
    for i, h in enumerate([10, 11, 12, 1, 2]):
        if btn_cols[i].button(f"{h}時", type="primary" if st.session_state["rep_clock"]==h else "secondary", key=f"r_{h}", use_container_width=True):
            st.session_state["rep_clock"] = h; st.rerun()
    spd = st.number_input("平均風速", step=0.1, key="r_spd")
    if st.button("報告を送信", type="primary", use_container_width=True):
        u, v = clock_to_uv(st.session_state["rep_clock"], spd); db = load_db(DB_REPORT)
        db.append({"time": obs_t.strftime("%H:%M"), "loc": loc, "speed": spd, "u": u, "v": v, "run": current_run})
        save_db(DB_REPORT, db); st.success("送信完了"); st.rerun()

# --- タブ5: 発進判定 ---
with tab5:
    st.subheader("🚀 判定ログ")
    with st.form("j_form"):
        res = st.radio("判定", ["🔴 STAY", "🟡 CAUTION", "🟢 GO"], horizontal=True)
        txt = st.text_area("理由")
        if st.form_submit_button("判定記録"):
            db = load_db(DB_JUDGE)
            db.append({"time": datetime.now().strftime("%H:%M"), "run": current_run, "res": res, "txt": txt})
            save_db(DB_JUDGE, db); st.rerun()
    for h in reversed(load_db(DB_JUDGE)):
        st.write(f"**[{h['time']}] {h['res']}** ({h['run']})"); st.caption(h['txt']); st.divider()

# --- タブ2: 予報比較 ---
with tab2:
    st.subheader("📊 比較タイムライン")
    f_db = load_db(DB_FORECAST); r_db = load_db(DB_REPORT)
    combined = []
    for f in f_db: combined.append({"時刻": f["time"], "ソース": f["src"], "風速": f["speed"]})
    for r in r_db: combined.append({"時刻": r["time"], "ソース": "実測報告", "風速": r["speed"]})
    if combined: st.dataframe(pd.DataFrame(combined).sort_values("時刻"), use_container_width=True)
