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
JUDGE_DATA_FILE = os.path.join(BASE_DIR, "ops_judge_data.json") # 🌟【新規】判定履歴

AMEDAS_STATIONS = {
    "60131": {"name": "彦根", "lat": 35.2750, "lon": 136.2467},
    "60026": {"name": "長浜", "lat": 35.3850, "lon": 136.2650},
    "60111": {"name": "今津", "lat": 35.4117, "lon": 136.0350}
}

# ==========================================
# 🛠️ 計算ユーティリティ (Phase 4 核心)
# ==========================================
def clock_to_uv(clock_dir, speed):
    if speed == 0: return 0.0, 0.0
    angle_deg = (clock_dir * 30) % 360
    rad = math.radians(angle_deg)
    u = -speed * math.sin(rad)
    v = -speed * math.cos(rad)
    return round(u, 2), round(v, 2)

def calculate_crosswind(u, v, runway_deg):
    """u, vベクトルから指定方位(runway_deg)に対する横風成分を計算"""
    # 風速と風向(deg)に戻す
    speed = math.sqrt(u**2 + v**2)
    if speed < 0.1: return 0.0
    
    wind_from_deg = (math.degrees(math.atan2(-u, -v)) + 360) % 360
    # 相対角度 (機首方位に対して風がどこから吹いているか)
    relative_angle = math.radians(wind_from_deg - runway_deg)
    # 横風成分 = speed * sin(相対角度)
    cross_wind = speed * math.sin(relative_angle)
    return round(cross_wind, 2)

# ==========================================
# 💾 データ管理
# ==========================================
def load_data(path):
    if not os.path.exists(path): return [] if "data" in path else None
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except: return [] if "data" in path else None

def save_data(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
                # 16方位からu, vへ
                angle = (dr - 1) * 22.5 if dr > 0 else 0
                u = -spd * math.sin(math.radians(angle)) if dr > 0 else 0
                v = -spd * math.cos(math.radians(angle)) if dr > 0 else 0
                extracted["stations"][st_id] = {
                    "name": info["name"], "speed": spd, "u": round(u,2), "v": round(v,2)
                }
        save_data(DATA_FILE_AMEDAS, extracted)
        return True
    except: return False

# ==========================================
# 🚀 メイン UI
# ==========================================
st.set_page_config(page_title="Birdman Wind Ops", page_icon="🦅", layout="wide")
st.markdown("# 🦅 Birdman Wind Ops <small>Ver.96</small>", unsafe_allow_html=True)

with st.sidebar:
    st.header("🌐 Global Settings")
    current_run = st.selectbox("対象フライト", [f"{i}走目" for i in range(1, 21)])
    runway_heading = st.number_input("離陸方位 (機首向き deg)", value=270, help="プラットホームが向いている方位（西=270）")
    launch_limit = st.number_input("横風限界 (m/s)", value=3.0, step=0.1)
    
    st.write("---")
    if st.button("📡 アメダス強制更新", use_container_width=True):
        if fetch_amedas_latest(): st.success("更新完了")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🧭 現在状況", "📊 予報比較", "🖊️ SCW入力", "🚩 実測報告", "🚀 発進判定"])

# --- タブ1: 現在状況 ---
with tab1:
    amedas = load_data(DATA_FILE_AMEDAS)
    reports = load_data(REPORT_DATA_FILE)
    
    col_main, col_sub = st.columns([2, 1])
    
    with col_main:
        st.subheader("現在の風況（機体相対）")
        # 地図の代わりに、機体に対する風の当たり方を可視化（簡易版）
        latest_actual = None
        if reports:
            latest_actual = reports[-1]
        elif amedas:
            # 彦根のデータを代表値とする
            latest_actual = amedas["stations"].get("60131")

        if latest_actual:
            # 🌟バグ対策: キーが存在しない場合はgetでデフォルト値0を入れる
            u = latest_actual.get("u", 0.0)
            v = latest_actual.get("v", 0.0)
            spd = latest_actual.get("speed", 0.0)
            
            cw = calculate_crosswind(u, v, runway_heading)
            cw_percent = (abs(cw) / launch_limit) * 100
            
            # メトリック表示
            m1, m2, m3 = st.columns(3)
            m1.metric("実測風速", f"{spd} m/s")
            m2.metric("横風成分", f"{abs(cw)} m/s", delta="左から" if cw > 0 else "右から")
            m3.metric("限界到達度", f"{cw_percent:.1f} %")
            
            if cw_percent > 100:
                st.error(f"🚨 横風限界を超えています ({cw_percent:.1f}%)")
            elif cw_percent > 80:
                st.warning(f"⚠️ 横風限界に接近中 ({cw_percent:.1f}%)")
            else:
                st.success(f"✅ 発進可能範囲内です ({cw_percent:.1f}%)")
        else:
            st.info("データがありません。アメダス更新または実測報告を行ってください。")

    with col_sub:
        st.subheader("最新の観測値")
        if amedas:
            for sid, s in amedas["stations"].items():
                st.write(f"📍 {s['name']}: {s.get('speed',0)}m/s")
        if reports:
            lr = reports[-1]
            st.info(f"🚩 **現地 ({lr.get('time')})**\n\n{lr.get('location')}: {lr.get('speed')}m/s")

# --- タブ2: 予報比較 ---
with tab2:
    st.subheader("📊 予報 vs 実況 タイムライン")
    scw = load_data(SCW_DATA_FILE)
    amedas = load_data(DATA_FILE_AMEDAS)
    reports = load_data(REPORT_DATA_FILE)
    
    rows = []
    # 🌟バグ対策: キーエラーを回避するために .get() を徹底
    for item in scw:
        rows.append({"時刻": item.get("time"), "地点": item.get("location"), "種別": "予報(SCW)", "風速": item.get("speed",0.0), "u": item.get("u",0.0), "v": item.get("v",0.0)})
    
    if amedas:
        obs_time = datetime.fromisoformat(amedas["observed"]).strftime("%H:%M")
        for sid, s in amedas["stations"].items():
            rows.append({"時刻": obs_time, "地点": s.get("name"), "種別": "実況(AMeDAS)", "風速": s.get("speed",0.0), "u": s.get("u",0.0), "v": s.get("v",0.0)})
            
    for r in reports:
        if r.get("run") == current_run:
            rows.append({"時刻": r.get("time"), "地点": r.get("location"), "種別": "現地実測", "風速": r.get("speed",0.0), "u": r.get("u",0.0), "v": r.get("v",0.0)})
    
    if rows:
        df = pd.DataFrame(rows).sort_values("時刻")
        st.dataframe(df, use_container_width=True)
    else:
        st.info("比較データがありません。")

# --- タブ3: SCW入力 ---
with tab3:
    st.markdown("## 🖊️ SCW 要約値入力")
    with st.form("scw_form"):
        col1, col2 = st.columns(2)
        with col1:
            t_t = st.selectbox("対象時刻", [f"{h}:{m:02d}" for h in range(4, 20) for m in [0, 30]])
            loc = st.selectbox("地点", ["彦根沖", "今津沖", "長浜沖", "南小松沖"])
        with col2:
            clock = st.selectbox("風向(時)", range(1, 13), index=11)
            spd = st.number_input("風速(m/s)", step=0.1)
        if st.form_submit_button("予報を登録"):
            u, v = clock_to_uv(clock, spd)
            data = load_data(SCW_DATA_FILE)
            data.append({"time": t_t, "location": loc, "speed": spd, "u": u, "v": v, "pub": "", "conf": "中", "memo": ""})
            save_data(SCW_DATA_FILE, data)
            st.rerun()

# --- タブ4: 実測報告 ---
with tab4:
    st.subheader(f"🚩 現地実測報告 【{current_run}】")
    if "rep_clock" not in st.session_state: st.session_state["rep_clock"] = 12
    
    c1, c2 = st.columns(2)
    with c1: loc = st.selectbox("観測地点", ["プラットホーム", "風見船A", "風見船B"])
    with c2: obs_t = st.time_input("観測時刻", value=datetime.now())

    st.write("風向き (時)")
    cols = st.columns(5)
    for i, h in enumerate([10, 11, 12, 1, 2]):
        if cols[i].button(f"{h}時", type="primary" if st.session_state["rep_clock"] == h else "secondary", use_container_width=True):
            st.session_state["rep_clock"] = h
            st.rerun()
            
    spd = st.number_input("平均風速 (m/s)", step=0.1)
    if st.button("実測を送信", type="primary", use_container_width=True):
        u, v = clock_to_uv(st.session_state["rep_clock"], spd)
        data = load_data(REPORT_DATA_FILE)
        data.append({"time": obs_t.strftime("%H:%M"), "location": loc, "speed": spd, "u": u, "v": v, "run": current_run})
        save_data(REPORT_DATA_FILE, data)
        st.success("報告完了")

# --- タブ5: 発進判定 ---
with tab5:
    st.subheader("🚀 発進判定ログ")
    with st.form("judge_form"):
        status = st.radio("判定", ["🔴 STAY (待機)", "🟡 CAUTION (注意)", "🟢 GO (発進)"], horizontal=True)
        reason = st.text_area("判断理由 (例: 横風成分が限界の80%に達した、予報より悪化が早い等)")
        if st.form_submit_button("判定を記録する"):
            data = load_data(JUDGE_DATA_FILE)
            data.append({
                "time": datetime.now(timezone(timedelta(hours=9))).strftime("%H:%M"),
                "run": current_run,
                "status": status,
                "reason": reason
            })
            save_data(JUDGE_DATA_FILE, data)
            st.rerun()
    
    st.write("---")
    st.markdown("### 📜 判定履歴")
    history = load_data(JUDGE_DATA_FILE)
    if history:
        for h in reversed(history):
            st.write(f"**[{h['time']}] {h['run']}** : {h['status']}")
            st.caption(h['reason'])
            st.divider()
