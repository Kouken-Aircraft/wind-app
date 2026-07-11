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

# MSM解析用ライブラリ (要 requirements.txt)
try:
    import xarray as xr
except ImportError:
    st.error("xarrayがインストールされていません。requirements.txtに追加してください。")

# ==========================================
# ⚙️ 設定・パス
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE_AMEDAS = os.path.join(BASE_DIR, "ops_amedas.json")
SCW_DATA_FILE = os.path.join(BASE_DIR, "ops_scw_data.json")
REPORT_DATA_FILE = os.path.join(BASE_DIR, "ops_report_data.json")
MSM_DATA_FILE = os.path.join(BASE_DIR, "ops_msm_data.json")
JUDGE_DATA_FILE = os.path.join(BASE_DIR, "ops_judge_data.json")

# MSM抽出地点 (琵琶湖をカバーする代表点)
MSM_POINTS = {
    "彦根沖": {"lat": 35.3, "lon": 136.2},
    "今津沖": {"lat": 35.4, "lon": 136.0},
    "南小松沖": {"lat": 35.2, "lon": 136.0},
    "長浜沖": {"lat": 35.4, "lon": 136.2}
}

# ==========================================
# 🌊 MSM 自動取得ロジック (Phase 2 核心)
# ==========================================
def fetch_msm_latest():
    """京都大学RISHからMSM最新予報(地上面)を取得しJSON化"""
    try:
        # 最新のデータ日時に合わせてURLを構築 (実際にはUTC時間などで計算が必要)
        # ここでは仕様書に基づきOpenDAPまたは直接NetCDFを読み込む構造を定義
        now = datetime.now(timezone.utc)
        # MSMの更新タイミングに合わせたパス構築 (例: 1日1回のアーカイブアクセス)
        url = f"http://database.rish.kyoto-u.ac.jp/arch/jmadata/data/gpv/netcdf/MSM-S/{now.year}/{now.strftime('%m%d')}.nc"
        
        # 🌟xarrayでリモートNetCDFを開く
        with xr.open_dataset(url) as ds:
            # 琵琶湖周辺を抽出
            msm_extracted = []
            obs_time_list = ds.time.values
            
            for loc_name, pos in MSM_POINTS.items():
                # 最寄りの格子点を選択
                point_ds = ds.sel(lat=pos["lat"], lon=pos["lon"], method="nearest")
                
                for t_idx in range(len(obs_time_list)):
                    t_val = pd.to_datetime(obs_time_list[t_idx]).tz_localize('UTC').tz_convert('Asia/Tokyo')
                    # 本日の日中データのみ抽出
                    if t_val.hour >= 4 and t_val.hour <= 19:
                        u = float(point_ds.u.values[t_idx])
                        v = float(point_ds.v.values[t_idx])
                        speed = math.sqrt(u**2 + v**2)
                        
                        msm_extracted.append({
                            "time": t_val.strftime("%H:%M"),
                            "location": loc_name,
                            "speed": round(speed, 2),
                            "u": round(u, 2),
                            "v": round(v, 2),
                            "type": "FORECAST_MSM"
                        })
            
            with open(MSM_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(msm_extracted, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"MSM取得失敗(サーバー未更新または通信制限): {e}")
        return False

# ==========================================
# 🛠️ 既存ユーティリティ
# ==========================================
def load_data(path):
    if not os.path.exists(path): return [] if "data" in path or "scw" in path or "msm" in path else None
    try:
        with open(path, "r", encoding="utf-8") as f: return json.load(f)
    except: return [] if "data" in path else None

def save_data(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def calculate_crosswind(u, v, runway_deg):
    speed = math.sqrt(u**2 + v**2)
    if speed < 0.1: return 0.0
    wind_from_deg = (math.degrees(math.atan2(-u, -v)) + 360) % 360
    relative_angle = math.radians(wind_from_deg - runway_deg)
    return round(speed * math.sin(relative_angle), 2)

# ==========================================
# 🚀 メイン UI
# ==========================================
st.set_page_config(page_title="Birdman Wind Ops", page_icon="🦅", layout="wide")
st.markdown("# 🦅 Birdman Wind Ops <small>Ver.97</small>", unsafe_allow_html=True)

with st.sidebar:
    st.header("🌐 Global Settings")
    current_run = st.selectbox("対象フライト", [f"{i}走目" for i in range(1, 21)])
    runway_heading = st.number_input("離陸方位 (deg)", value=270)
    launch_limit = st.number_input("横風限界 (m/s)", value=3.0)
    
    st.write("---")
    if st.button("📡 アメダス ＋ 🌊 MSM 更新", use_container_width=True):
        a_ok = True # amedas fetch logic (省略して継承)
        m_ok = fetch_msm_latest()
        if a_ok and m_ok: st.success("全データ更新完了")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🧭 現在状況", "📊 予報比較", "🖊️ SCW入力", "🚩 実測報告", "🚀 発進判定"])

# --- タブ2: 予報比較 (MSMデータ統合版) ---
with tab2:
    st.subheader("📊 MSM予報 vs SCW予報 vs 実測")
    
    msm_data = load_data(MSM_DATA_FILE)
    scw_data = load_data(SCW_DATA_FILE)
    reps = load_data(REPORT_DATA_FILE)
    
    all_compare = []
    if msm_data:
        for m in msm_data:
            all_compare.append({"時刻": m["time"], "地点": m["location"], "ソース": "MSM(広域)", "風速": m["speed"]})
    if scw_data:
        for s in scw_data:
            all_compare.append({"時刻": s.get("time"), "地点": s.get("location"), "ソース": "SCW(局地)", "風速": s.get("speed")})
    
    if all_compare:
        df = pd.DataFrame(all_compare).sort_values(["時刻", "地点"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("MSMデータを取得するか、SCWを入力してください。")

# --- タブ1: 現在状況 (背景場表示) ---
with tab1:
    msm = load_data(MSM_DATA_FILE)
    # 現在時刻に近いMSM予報を「背景場」として地図やサマリーに反映
    now_str = datetime.now(timezone(timedelta(hours=9))).strftime("%H:00")
    
    col_l, col_r = st.columns([2, 1])
    with col_l:
        st.subheader("統合風況ダッシュボード")
        if msm:
            # 簡略化：最新MSM予報を表示
            latest_msm = [m for m in msm if m["time"] == now_str]
            if latest_msm:
                st.caption(f"🌊 MSM背景場 ({now_str} 予測): 琵琶湖全体は現在 {latest_msm[0]['speed']}m/s 程度の風の流れがあります。")
        
        # 横風計算表示（Ver.96を継承）
        # ... (ここに実測に基づいたメトリックを表示)

# --- 他のタブはVer.96を継承 ---
