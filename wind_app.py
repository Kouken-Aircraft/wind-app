import streamlit as st
import json
import os
import time
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np

# ==========================================
# ⚙️ 設定エリア
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "wind_data_v2.json")
# 背景画像のファイル名（もし写真があればここに名前を書く。なければ自動描画）
BG_IMAGE_FILE = "runway.png" 

REFRESH_RATE = 3

# 📍 座標の設定 (重要！)
# 滑走路の「どこ」に矢印を出すかを (X, Y) 座標で決めます
# ※ 図の左下が (0,0)、右上が (100, 400) と仮定した座標系です
LOCATION_COORDS = {
    "① スタート地点": (50, 20),
    "② 200m地点":    (50, 100),
    "③ 400m地点":    (50, 180),
    "④ 600m地点":    (50, 260),
    "⑤ ゴール付近":    (50, 340)
}
LOCATIONS = list(LOCATION_COORDS.keys())
DIRECTIONS = ["北", "北東", "東", "南東", "南", "南西", "西", "北西"]

# 風向を角度に変換する辞書（北を90度とする数学的な角度変換）
# matplotlibのquiverは、0度が「右(東)」なので注意が必要
DIR_TO_ANGLE = {
    "北": 90, "北東": 45, "東": 0, "南東": -45,
    "南": -90, "南西": -135, "西": 180, "北西": 135
}

# ==========================================
# 💾 データ処理関数
# ==========================================
def load_all_data():
    if not os.path.exists(DATA_FILE):
        initial_data = {loc: {"dir": "北", "speed": 0.0} for loc in LOCATIONS}
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, ensure_ascii=False, indent=2)
        except: pass
        return initial_data
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {loc: {"dir": "北", "speed": 0.0} for loc in LOCATIONS}

def save_location_data(location, direction, speed):
    current_all_data = load_all_data()
    current_all_data[location] = {"dir": direction, "speed": speed}
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_all_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"保存エラー: {e}")

# ==========================================
# 🎨 マップ描画関数
# ==========================================
def draw_map(data):
    # 図のサイズ比率 (横5インチ, 縦8インチ)
    fig, ax = plt.subplots(figsize=(5, 8))
    
    # --- 背景の描画 ---
    bg_path = os.path.join(BASE_DIR, BG_IMAGE_FILE)
    if os.path.exists(bg_path):
        # 画像ファイルがある場合：それを表示
        img = mpimg.imread(bg_path)
        ax.imshow(img, extent=[0, 100, 0, 400])
    else:
        # 画像がない場合：灰色の長方形（滑走路）を描く
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 400)
        ax.set_facecolor('#4CAF50') # 芝生っぽい緑
        # 滑走路のアスファルト
        runway = plt.Rectangle((30, 0), 40, 400, color='gray', alpha=0.8)
        ax.add_patch(runway)
        # 中心線
        ax.plot([50, 50], [0, 400], color='white', linestyle='--', linewidth=2)
        ax.text(50, 380, "RUNWAY", color='white', ha='center', fontweight='bold')

    # --- 矢印（風ベクトル）の描画 ---
    for loc_name, coords in LOCATION_COORDS.items():
        if loc_name in data:
            item = data[loc_name]
            speed = item['speed']
            direction_str = item['dir']
            
            if speed > 0:
                # 角度を計算
                angle_deg = DIR_TO_ANGLE.get(direction_str, 90)
                angle_rad = np.radians(angle_deg)
                
                # ベクトル成分 (U, V)
                # 風速に応じて矢印を長くする
                scale = 2.0  # 矢印の長さ調整係数
                U = speed * np.cos(angle_rad) * scale
                V = speed * np.sin(angle_rad) * scale
                
                # 矢印を描画 (quiver)
                ax.quiver(coords[0], coords[1], U, V, 
                          color='red', scale=1, scale_units='xy', 
                          angles='xy', width=0.015, headwidth=4)
                
                # 風速の数値を横に書く
                ax.text(coords[0] + 10, coords[1], f"{speed}m", 
                        color='black', fontsize=12, fontweight='bold', 
                        bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
            
            # 地点名を書く
            ax.text(coords[0] - 25, coords[1], loc_name.split(" ")[1], 
                    color='blue', fontsize=9, ha='right')

    # 軸や枠線を消す（地図っぽくするため）
    ax.axis('off')
    return fig

# ==========================================
# 📱 アプリのメイン処理
# ==========================================
st.set_page_config(page_title="鳥人間 風況マップ Ver.2", layout="centered")

mode = st.sidebar.radio("モード選択", ["コントローラー (地上クルー)", "モニター (全体マップ)"])
all_data = load_all_data()

# ------------------------------------------
# 🗺️ モニター (マップ表示)
# ------------------------------------------
if mode == "モニター (全体マップ)":
    st.markdown("## 🗺️ リアルタイム風況マップ")
    
    # 描画したグラフを表示
    fig = draw_map(all_data)
    st.pyplot(fig)
    
    st.caption(f"自動更新中... ({REFRESH_RATE}秒間隔)")
    time.sleep(REFRESH_RATE)
    st.rerun()

# ------------------------------------------
# 🚩 コントローラー (地上クルー)
# ------------------------------------------
else:
    st.markdown("## 🚩 データ入力")
    selected_loc = st.selectbox("📍 あなたの場所", LOCATIONS)
    st.write("---")
    
    target_data = all_data.get(selected_loc, {"dir": "北", "speed": 0.0})
    st.info(f"{selected_loc}: 【 {target_data['dir']} / {target_data['speed']} m/s 】")

    # 風向
    st.write("風向")
    c1, c2, c3, c4 = st.columns(4)
    for i, d in enumerate(DIRECTIONS):
        with [c1, c2, c3, c4][i % 4]:
            btn_type = "primary" if target_data['dir'] == d else "secondary"
            if st.button(d, key=f"d_{i}", type=btn_type, use_container_width=True):
                save_location_data(selected_loc, d, target_data['speed'])
                st.rerun()

    # 風速
    st.write("風速 (m/s)")
    sc1, sc2, sc3 = st.columns([1, 2, 1])
    with sc1:
        if st.button("➖ 0.5", use_container_width=True):
            save_location_data(selected_loc, target_data['dir'], max(0.0, target_data['speed'] - 0.5)); st.rerun()
    with sc2:
        st.markdown(f"<h2 style='text-align: center; margin: 0;'>{target_data['speed']:.1f}</h2>", unsafe_allow_html=True)
    with sc3:
        if st.button("➕ 0.5", use_container_width=True):
            save_location_data(selected_loc, target_data['dir'], target_data['speed'] + 0.5); st.rerun()
            
    # 一発入力
    cols = st.columns(5)
    for i, p in enumerate([0.0, 1.0, 2.0, 3.0, 5.0]):
        with cols[i]:
            if st.button(str(p), key=f"p_{i}", use_container_width=True):
                save_location_data(selected_loc, target_data['dir'], p); st.rerun()
