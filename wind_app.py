import streamlit as st
import json
import os
import time
from datetime import datetime, timedelta, timezone
import math

# ==========================================
# ⚙️ 設定
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCW_DATA_FILE = os.path.join(BASE_DIR, "ops_scw_data.json")

# SCW入力用の選択肢
SCW_LOCATIONS = ["彦根沖", "長浜沖", "今津沖", "南小松沖", "その他"]
SCW_CONFIDENCE = ["高 (High)", "中 (Mid)", "低 (Low)"]
CLOCK_LABELS = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]

# ==========================================
# 💾 関数群
# ==========================================
def load_scw_data():
    if not os.path.exists(SCW_DATA_FILE): return []
    try:
        with open(SCW_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return []

def save_scw_data(publish_time, target_time, location, clock_dir, speed, confidence, memo):
    current_data = load_scw_data()
    
    # u, vベクトル変換 (12時=北風、3時=東風と仮定)
    # 風向θ = 90 - (clock * 30)度
    # u = -W * sin(θ), v = -W * cos(θ) ※気象学的な風向ベクトル計算
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
# 🚀 メイン処理
# ==========================================
st.set_page_config(page_title="Birdman Wind Ops", page_icon="🦅", layout="wide")

st.markdown("# 🦅 Birdman Wind Ops <small>Ver.92</small>", unsafe_allow_html=True)

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
    st.subheader("琵琶湖広域風況マップ (開発中)")
    st.info("ここにAMeDAS実況と実測・SCWの統合マップが表示されます。")

# --- タブ2: 予報比較 ---
with tab2:
    st.subheader("予報モデル比較 (開発中)")

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
            save_scw_data(
                publish_time.strftime('%H:%M'), 
                target_time, 
                location, 
                clock_dir, 
                speed, 
                confidence, 
                memo
            )
            st.success(f"{location} の {target_time} 予測データを登録しました！")

    st.write("---")
    st.markdown("### 📋 登録済みのSCWデータ")
    saved_scw = load_scw_data()
    if saved_scw:
        # 最新のものが上に来るように反転
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
    st.info("前バージョンの入力UIがここに統合されます。")

# --- タブ5: 発進判定 ---
with tab5:
    st.subheader("🚀 発進・経路判断 (開発中)")
