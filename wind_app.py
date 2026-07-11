import streamlit as st
import json
import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta, timezone
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
import matplotlib_fontja

# ==========================================
# ⚙️ 基本設定・定数
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 琵琶湖周辺のアメダス地点定義
AMEDAS_STATIONS = {
    "60131": {"name": "彦根", "lat": 35.2750, "lon": 136.2467},
    "60026": {"name": "長浜", "lat": 35.3850, "lon": 136.2650},
    "60066": {"name": "米原", "lat": 35.3150, "lon": 136.2867},
    "60191": {"name": "南小松", "lat": 35.2400, "lon": 135.9633},
    "60216": {"name": "大津", "lat": 35.0150, "lon": 135.8750},
    "60111": {"name": "今津", "lat": 35.4117, "lon": 136.0350}
}

# ファイルパス
DATA_FILE_AMEDAS = os.path.join(BASE_DIR, "ops_amedas.json")
DATA_FILE_REPORT = os.path.join(BASE_DIR, "ops_report.json")
CONFIG_FILE = os.path.join(BASE_DIR, "ops_config.json")

REFRESH_RATE = 10 # 秒 (アメダス監視用)

# ==========================================
# 📡 AMeDAS 自動取得ロジック (Phase 1 核心)
# ==========================================
def fetch_amedas_latest():
    """気象庁JSONから最新のアメダスデータを取得・保存"""
    try:
        # 1. 最新の観測時刻を確認
        time_url = "https://www.jma.go.jp/bosai/amedas/data/latest_time.txt"
        latest_time_str = requests.get(time_url).text.strip()
        # 例: 2024-05-20T10:10:00+09:00 -> 20240520101000
        dt = datetime.fromisoformat(latest_time_str)
        time_key = dt.strftime("%Y%m%d%H%M%S")
        
        # 2. その時刻の全国データを取得
        data_url = f"https://www.jma.go.jp/bosai/amedas/data/map/{time_key}.json"
        all_data = requests.get(data_url).json()
        
        # 3. 必要な地点だけ抽出
        extracted = {"observed": latest_time_str, "stations": {}}
        for st_id, info in AMEDAS_STATIONS.items():
            if st_id in all_data:
                s_data = all_data[st_id]
                # 風向(deg), 風速(m/s)を抽出 (wndDir, wind)
                # 気象庁の風向は16方位(0-16)で来るため変換が必要な場合があるが、まずはそのまま保持
                extracted["stations"][st_id] = {
                    "name": info["name"],
                    "wind_speed": s_data.get("wind", [None])[0],
                    "wind_dir": s_data.get("wndDir", [None])[0],
                    "temp": s_data.get("temp", [None])[0]
                }
        
        # 4. 保存
        with open(DATA_FILE_AMEDAS, "w", encoding="utf-8") as f:
            json.dump(extracted, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        st.error(f"アメダス取得エラー: {e}")
        return False

def load_amedas():
    if not os.path.exists(DATA_FILE_AMEDAS): return None
    with open(DATA_FILE_AMEDAS, "r", encoding="utf-8") as f:
        return json.load(f)

#方位変換用（アメダスの1方位=22.5度）
DIR_16_NAMES = ["無風", "北北東", "北東", "東北東", "東", "東南東", "南東", "南南東", "南", "南南西", "南西", "西南西", "西", "西北西", "北西", "北北西", "北"]

# ==========================================
# 📊 描画系
# ==========================================
def draw_ops_map(amedas_data, reports):
    # Phase 1では簡易的なリスト表示と地図の枠組みだけ
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.set_facecolor('#E3F2FD') # 琵琶湖っぽい青
    ax.set_title("Lake Biwa Wind Overview (Phase 1)", fontsize=15)
    
    # 簡易的にアメダス地点をプロット
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
# 🚀 メイン UI
# ==========================================
st.set_page_config(page_title="Birdman Wind Ops", layout="wide")

st.markdown("# 🦅 Birdman Wind Ops <small>Ver.90</small>", unsafe_allow_html=True)

# サイドバー：全体共有設定
with st.sidebar:
    st.header("🌐 Global Settings")
    current_run = st.selectbox("対象フライト", [f"{i}走目" for i in range(1, 21)])
    launch_limit = st.number_input("横風限界 (m/s)", value=3.0, step=0.5)
    
    if st.button("アメダス強制更新"):
        if fetch_amedas_latest():
            st.success("更新完了")
            st.rerun()

# --- タブ構造の実装 ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🧭 現在状況", 
    "📊 予報比較", 
    "🖊️ SCW入力", 
    "🚩 実測報告", 
    "⚙️ 設定"
])

# --- タブ1: 現在状況 (判断者用) ---
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
            st.warning("アメダスデータがまだ取得されていません。")

# --- タブ2: 予報比較 (気象担当用) ---
with tab2:
    st.info("Phase 2 で実装予定: MSM予報データと実測のズレを視覚化します。")

# --- タブ3: SCW入力 (気象担当用) ---
with tab3:
    st.info("Phase 3 で実装予定: SCW(LFM)の要約値を手入力するフォームを設置します。")

# --- タブ4: 実測報告 (観測班用) ---
with tab4:
    st.subheader(f"🚩 現地実測報告フォーム ({current_run})")
    st.markdown("以前のアプリのUIをここに統合します。")
    # ここにVer.89の入力ロジックを移植予定
    with st.expander("入力プロトタイプ", expanded=True):
        st.number_input("地点 (m)", value=0, step=50)
        st.columns(5) # 風速ボタンなどの配置
        st.button("送信", type="primary")

# --- タブ5: 設定 ---
with tab5:
    st.subheader("システム設定")
    if st.button("全データを初期化"):
        st.warning("実装中...")

# 自動更新の仕組み
st.caption(f"自動更新まであと数秒...")
time.sleep(1) # 本番は st_autorefresh などを使用検討
