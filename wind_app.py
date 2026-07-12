import streamlit as st
import json
import os
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
DB_AMEDAS = os.path.join(BASE_DIR, "ops_amedas.json")
DB_AMEDAS_HIST = os.path.join(BASE_DIR, "ops_amedas_hist.json")
DB_FORECAST = os.path.join(BASE_DIR, "ops_forecast.json")
DB_REPORT = os.path.join(BASE_DIR, "ops_report.json")
DB_JUDGE = os.path.join(BASE_DIR, "ops_judge.json")

# AMeDAS 観測地点
STATIONS = {
    "60131": {"name": "Hikone", "lat": 35.2750, "lon": 136.2467},
    "60026": {"name": "Nagahama", "lat": 35.3850, "lon": 136.2650},
    "60111": {"name": "Imazu", "lat": 35.4117, "lon": 136.0350},
    "60191": {"name": "M-Komatsu", "lat": 35.2400, "lon": 135.9633}
}

# 🌟 文字化け防止のため、座標キーをすべて英語化
OFFSHORE_COORDS = {
    "Hikone-Off": {"lat": 35.28, "lon": 136.20},
    "Nagahama-Off": {"lat": 35.35, "lon": 136.22},
    "Imazu-Off": {"lat": 35.38, "lon": 136.08},
    "M-Komatsu-Off": {"lat": 35.25, "lon": 136.00},
    "Platform": {"lat": 35.2750, "lon": 136.2467},
    "Boat-A": {"lat": 35.35, "lon": 136.18},
    "Boat-B": {"lat": 35.20, "lon": 136.18},
    "Custom": {"lat": 35.27, "lon": 136.22}
}

# ==========================================
# 🛠️ 共通計算エンジン
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

def get_wind_trend(sid):
    hist = load_db(DB_AMEDAS_HIST, [])
    if len(hist) < 2: return "No Data ➔", 0.0
    current_spd = hist[-1]["stations"].get(sid, {}).get("speed", 0.0)
    old_spd = hist[0]["stations"].get(sid, {}).get("speed", 0.0)
    diff = round(current_spd - old_spd, 1)
    if diff > 0.5: return f"Rising ↗", diff
    elif diff < -0.5: return f"Falling ↘", diff
    else: return f"Stable ➔", diff

# ==========================================
# 💾 データ入出力
# ==========================================
def load_db(path, default=None):
    if default is None: default = []
    if not os.path.exists(path): return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = json.load(f)
            return content if content is not None else default
    except: return default

def save_db(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except: pass

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
                s = all_d[sid]
                spd = s.get("wind", [0])[0]
                dr = s.get("wndDir", [0])[0]
                ang = (dr - 1) * 22.5 if dr > 0 else 0
                u = -spd * math.sin(math.radians(ang))
                v = -spd * math.cos(math.radians(ang))
                ext["stations"][sid] = {"name": info["name"], "speed": spd, "u": u, "v": v}
        
        save_db(DB_AMEDAS, ext)
        hist = load_db(DB_AMEDAS_HIST, [])
        if not any(h.get("observed") == t_str for h in hist):
            hist.append({"observed": t_str, "stations": ext["stations"]})
        if len(hist) > 6: hist = hist[-6:]
        save_db(DB_AMEDAS_HIST, hist)
        return True
    except: return False

# ==========================================
# 🚀 UI メイン
# ==========================================
st.set_page_config(page_title="Birdman Wind Ops", page_icon="🦅", layout="wide")
st.markdown("# 🦅 Birdman Wind Ops <small>Ver.110 (Anti-Mojibake)</small>", unsafe_allow_html=True)

with st.sidebar:
    st.header("🌐 全体設定")
    current_run = st.selectbox("対象フライト", [f"{i}走目" for i in range(1, 21)])
    runway_heading = st.number_input("プラットホーム方位 (deg)", value=270)
    launch_limit = st.number_input("横風限界 (m/s)", value=3.0, step=0.1)
    st.write("---")
    
    if st.button("📡 AMeDAS実況を更新", use_container_width=True):
        if fetch_amedas(): st.success("AMeDAS Update Success")
        else: st.error("Fetch Failed")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🧭 現在状況", "📊 予報比較", "🖊️ 予報入力", "🚩 実測報告", "🚀 発進判定"])

# --- タブ1: 現在状況 ---
with tab1:
    amedas = load_db(DB_AMEDAS, None)
    reps = load_db(DB_REPORT, [])
    forecasts = load_db(DB_FORECAST, [])
    
    col_l, col_r = st.columns([2, 1])
    
    with col_l:
        st.subheader("琵琶湖 統合風況マップ")
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.set_facecolor('#E3F2FD')
        ax.set_title("Lake Biwa Wind Map (m/s)", fontsize=16)

        # ① AMeDAS実況 (青)
        if amedas and "stations" in amedas:
            for sid, s in amedas["stations"].items():
                pos = STATIONS.get(sid)
                if pos:
                    u, v = s.get("u", 0.0), s.get("v", 0.0)
                    ax.quiver(pos["lon"], pos["lat"], u, v, color='blue', scale=25)
                    ax.text(pos["lon"], pos["lat"]-0.012, f"{pos['name']}\n{s.get('speed', 0)}", 
                            ha='center', fontsize=10, fontweight='bold')
        
        # ② 実測報告 (赤)
        if reps:
            lr = reps[-1]
            rep_pos = OFFSHORE_COORDS.get(lr.get("loc", "Platform"))
            if rep_pos is None: rep_pos = OFFSHORE_COORDS["Platform"]
            ax.quiver(rep_pos["lon"], rep_pos["lat"], lr.get("u", 0.0), lr.get("v", 0.0), color='red', scale=25)
            ax.text(rep_pos["lon"], rep_pos["lat"]-0.012, f"REPORT({lr.get('loc')})\n{lr.get('speed')}", 
                    color='red', fontweight='bold', ha='center', fontsize=10)

        # ③ SCW/MSM予報 (緑)
        if forecasts:
            latest_fore = forecasts[-1]
            fore_pos = OFFSHORE_COORDS.get(latest_fore.get("loc_name", "Hikone-Off"))
            if fore_pos is None: fore_pos = OFFSHORE_COORDS["Hikone-Off"]
            ax.quiver(fore_pos["lon"], fore_pos["lat"], latest_fore.get("u", 0.0), latest_fore.get("v", 0.0), color='green', scale=25)
            ax.text(fore_pos["lon"], fore_pos["lat"] - 0.012, f"{latest_fore.get('src')}({latest_fore.get('target_time')})\n{latest_fore.get('speed')}", 
                    color='green', fontweight='bold', ha='center', fontsize=10)
        
        # ④ PH離陸方位 (黒)
        ph_lon, ph_lat = OFFSHORE_COORDS["Platform"]["lon"], OFFSHORE_COORDS["Platform"]["lat"]
        r_rad = math.radians(runway_heading)
        ru, rv = 0.04 * math.sin(r_rad), 0.04 * math.cos(r_rad)
        ax.quiver(ph_lon, ph_lat, ru, rv, color='black', scale=1, scale_units='xy', angles='xy', width=0.006, headwidth=4)
        ax.text(ph_lon + ru, ph_lat + rv, "PH Launch", color='black', fontsize=9, fontweight='bold')
        
        ax.set_xlim(135.8, 136.5); ax.set_ylim(35.0, 35.5)
        ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
        st.pyplot(fig)
        st.caption("※Blue=AMeDAS / Red=Report / Green=Forecast / Black=Launch Dir")

    with col_r:
        st.subheader("横風判定")
        actual = reps[-1] if reps else (amedas["stations"].get("60131") if amedas and "stations" in amedas else None)
        if actual:
            cw = calculate_crosswind(actual.get("u", 0.0), actual.get("v", 0.0), runway_heading)
            cw_pct = (abs(cw)/launch_limit)*100
            
            st.metric("風速 (現在値)", f"{actual.get('speed', 0)} m/s")
            trend_str, trend_diff = get_wind_trend("60131")
            st.metric("アメダス風速傾向 (直近1h)", trend_str, delta=f"{trend_diff:+.1f} m/s")
            st.metric("横風成分", f"{abs(cw)} m/s", delta="左から" if cw > 0 else "右から", delta_color="inverse")
            
            if cw_pct > 100: st.error(f"❌ STAY ({cw_pct:.1f}%)")
            elif cw_pct > 80: st.warning(f"⚠️ CAUTION ({cw_pct:.1f}%)")
            else: st.success(f"✅ GO ({cw_pct:.1f}%)")
        else:
            st.info("データ未取得。サイドバーから更新してください。")

# --- タブ3: 予報入力 ---
with tab3:
    st.subheader("🖊️ 予報値入力 (SCW / LFM / MSM)")
    st.info("※負荷対策のため、MSM等の予報データは担当者が目視確認して手入力する運用です。")
    with st.form("fore_form"):
        c1, c2, c3 = st.columns(3)
        with c1: 
            src = st.selectbox("種別", ["SCW", "MSM", "LFM"])
            issue_time = st.time_input("予報発表時刻 (更新時刻)")
            target_time = st.selectbox("対象時刻", [f"{h:02d}:{m:02d}" for h in range(4, 20) for m in [0, 30]])
        with c2:
            # 🌟 グラフ描画用に英語名を使用
            loc_name = st.selectbox("地点", ["Hikone-Off", "Nagahama-Off", "Imazu-Off", "M-Komatsu-Off"])
            clock = st.selectbox("風向(時)", range(1, 13), index=11)
            spd = st.number_input("風速(m/s)", step=0.1)
        with c3:
            conf = st.selectbox("信頼度", ["高", "中", "低"])
            memo = st.text_input("コメント (悪化の前倒し等)")
            screenshot = st.file_uploader("スクショ (任意)", type=["png", "jpg"])
            
        if st.form_submit_button("予報を記録", type="primary", use_container_width=True):
            u, v = clock_to_uv(clock, spd)
            db = load_db(DB_FORECAST)
            db.append({
                "src": src, "issue_time": issue_time.strftime("%H:%M"), "target_time": target_time,
                "loc_name": loc_name, "speed": spd, "u": u, "v": v, "conf": conf, "memo": memo
            })
            save_db(DB_FORECAST, db)
            st.success("記録完了")
            st.rerun()

# --- タブ4: 実測報告 ---
with tab4:
    st.subheader(f"🚩 現地実測報告 【{current_run}】")
    if "rep_clock" not in st.session_state: st.session_state["rep_clock"] = 12
    
    with st.container():
        c1, c2, c3 = st.columns(3)
        with c1: 
            # 🌟 グラフ描画用に英語名を使用
            loc = st.selectbox("地点ID", ["Platform", "Boat-A", "Boat-B", "Custom"])
            obs_t = st.time_input("観測時刻 (自動入力/修正可)")
        with c2:
            st.write("平均風向 (時)")
            btn_cols = st.columns(5)
            for i, h in enumerate([10, 11, 12, 1, 2]):
                if btn_cols[i].button(f"{h}時", type="primary" if st.session_state["rep_clock"]==h else "secondary", key=f"r_{h}"):
                    st.session_state["rep_clock"] = h
                    st.rerun()
            spd = st.number_input("平均風速 (m/s)", step=0.1)
        with c3:
            gust = st.number_input("最大瞬間風速 (m/s) ※未測は空欄", value=None, step=0.1)
            method = st.selectbox("観測方法", ["風速計(採用候補)", "体感(参考)", "旗"])
        
        rep_memo = st.text_input("メモ (波・突風・危険兆候など)")
        
        if st.button("報告送信", type="primary", use_container_width=True):
            u, v = clock_to_uv(st.session_state["rep_clock"], spd)
            db = load_db(DB_REPORT)
            db.append({
                "time": obs_t.strftime("%H:%M"), "loc": loc, "speed": spd, "u": u, "v": v, 
                "gust": gust, "method": method, "memo": rep_memo, "run": current_run
            })
            save_db(DB_REPORT, db)
            st.success("送信完了")
            st.rerun()

# --- タブ5: 発進判定 ---
with tab5:
    st.subheader("🚀 発進判定ログ")
    with st.form("j_form"):
        res = st.radio("判定", ["🔴 STAY", "🟡 CAUTION", "🟢 GO"], horizontal=True)
        txt = st.text_area("理由 (誰が・いつ・何を見て決めたか)")
        if st.form_submit_button("判定を記録"):
            db = load_db(DB_JUDGE)
            db.append({"time": datetime.now().strftime("%H:%M"), "run": current_run, "res": res, "txt": txt})
            save_db(DB_JUDGE, db); st.rerun()
    for h in reversed(load_db(DB_JUDGE)):
        st.write(f"**[{h.get('time')}] {h.get('res')}** ({h.get('run')})"); st.caption(h.get('txt')); st.divider()

# --- タブ2: 予報比較 ---
with tab2:
    st.subheader("📊 時系列データ比較表")
    f_db = load_db(DB_FORECAST)
    r_db = load_db(DB_REPORT)
    combined = []
    
    for f in f_db: 
        combined.append({
            "対象時刻": f.get("target_time"), "種別": f"{f.get('src')} ({f.get('conf')})", 
            "地点": f.get("loc_name"), "風速": f.get("speed"), "メモ": f.get("memo", "")
        })
    for r in r_db: 
        combined.append({
            "対象時刻": r.get("time"), "種別": f"実測 ({r.get('method')})", 
            "地点": r.get("loc"), "風速": r.get("speed"), "メモ": f"瞬風:{r.get('gust','-')} / {r.get('memo','')}"
        })
        
    if combined: 
        st.dataframe(pd.DataFrame(combined).sort_values("対象時刻"), use_container_width=True)
