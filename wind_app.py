import streamlit as st
import json
import os
import time
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np

# ==========================================
# ⚙️ 設定 (CONFIGURATION)
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "wind_data_v3.json") # ファイル名変更
BG_IMAGE_FILE = "runway.png" 

REFRESH_RATE = 2  # 自動更新間隔 (秒)
MAX_DISTANCE = 1000  # 滑走路の全長 (m) ※ここを変えると地図の縮尺が変わります

# ==========================================
# 💾 データ管理 (DATA MANAGEMENT)
# ==========================================
def load_all_data():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_point_data(distance_m, clock_dir, speed):
    """
    距離(m)をキーにしてデータを保存する
    例: "200" というキーで保存
    """
    current_data = load_all_data()
    # 文字列のキーとして保存
    dist_key = str(distance_m)
    current_data[dist_key] = {"clock": clock_dir, "speed": speed, "updated": time.time()}
    
    # 古すぎるデータ（1時間以上前）を消すなどの処理も可能だが今回は割愛
    
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Save Error: {e}")

def delete_point_data(distance_m):
    current_data = load_all_data()
    dist_key = str(distance_m)
    if dist_key in current_data:
        del current_data[dist_key]
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)

# ==========================================
# 🎨 マップ描画 (MAP DRAWING)
# ==========================================
def draw_map(data):
    # 縦長レイアウト (横5インチ, 縦10インチ)
    fig, ax = plt.subplots(figsize=(5, 10))
    
    # --- 背景 (滑走路) ---
    bg_path = os.path.join(BASE_DIR, BG_IMAGE_FILE)
    if os.path.exists(bg_path):
        img = mpimg.imread(bg_path)
        # 画像を 0-100(横), 0-MAX_DISTANCE(縦) に引き伸ばす
        ax.imshow(img, extent=[0, 100, 0, MAX_DISTANCE])
    else:
        # デフォルト描画
        ax.set_xlim(0, 100)
        ax.set_ylim(0, MAX_DISTANCE)
        ax.set_facecolor('#8BC34A') # 緑
        
        # 滑走路
        runway = plt.Rectangle((30, 0), 40, MAX_DISTANCE, color='#555555', alpha=0.9)
        ax.add_patch(runway)
        
        # センターライン
        ax.plot([50, 50], [0, MAX_DISTANCE], color='white', linestyle='--', linewidth=2)
        
        # 距離マーカー
        for d in range(0, MAX_DISTANCE + 1, 100):
            ax.text(25, d, f"{d}m", color='white', fontsize=8, ha='right', va='center')

    # --- 矢印の描画 ---
    for dist_key, item in data.items():
        try:
            dist_m = int(dist_key) # 距離（Y座標になる）
            speed = item['speed']
            clock = item['clock'] # 12, 1, 2...
            
            # 画面外のデータは無視
            if dist_m < 0 or dist_m > MAX_DISTANCE: continue
            
            # --- 角度計算 (クロックポジション -> 数学的な角度) ---
            # 12時(進行方向) = 北(90度)と仮定
            # 時計は1時間で30度進む (360 / 12 = 30)
            # 風が「吹いてくる」方向の角度
            wind_from_angle = 90 - (clock * 30) 
            # 矢印は「風が流れる」方向（+180度）
            arrow_angle_rad = np.radians(wind_from_angle + 180)
            
            # X座標は滑走路中央(50)固定、Y座標は距離(dist_m)
            x, y = 50, dist_m
            
            # 計測点のマーカー
            ax.plot(x, y, 'o', color='black', markersize=8, zorder=3)
            
            if speed > 0:
                # 色分け
                color = '#2196F3' # 青(安全)
                if speed >= 3.0: color = '#FFC107' # 黄
                if speed >= 5.0: color = '#FF5252' # 赤
                
                # ベクトル成分
                scale = 30.0 # 矢印の長さ
                U = np.cos(arrow_angle_rad) * scale
                V = np.sin(arrow_angle_rad) * scale
                
                # 矢印描画
                ax.quiver(x, y, U, V, color=color, 
                          angles='xy', scale_units='xy', scale=1,
                          width=0.025, headwidth=5, 
                          edgecolor='white', linewidth=1.5, zorder=4)
                
                # ラベル表示 (距離と風速)
                label_text = f"{clock}時 {speed}m"
                ax.text(x + 15, y, label_text, color='black', fontsize=12, fontweight='bold',
                        bbox=dict(facecolor='white', alpha=0.8, boxstyle='round'), zorder=5)
                
        except:
            continue

    ax.axis('off')
    return fig

# ==========================================
# 📱 アプリ画面 (MAIN APP)
# ==========================================
st.set_page_config(page_title="Wind Monitor V3", layout="centered")

mode = st.sidebar.radio("Mode", ["Ground Crew (Input)", "Pilot (Map Monitor)"])

# ------------------------------------------
# ✈️ PILOT MODE (MAP)
# ------------------------------------------
if mode == "Pilot (Map Monitor)":
    st.markdown("## ✈️ Wind Map")
    
    all_data = load_all_data()
    fig = draw_map(all_data)
    st.pyplot(fig)
    
    st.caption(f"Last Update: {time.strftime('%H:%M:%S')}")
    time.sleep(REFRESH_RATE)
    st.rerun()

# ------------------------------------------
# 🚩 GROUND CREW MODE (INPUT)
# ------------------------------------------
else:
    st.markdown("## 🚩 Input Data")
    
    # 1. 自分の場所を入力 (スライダーまたは手入力)
    my_dist = st.number_input("📍 現在位置 (スタートからの距離 m)", 
                              min_value=0, max_value=MAX_DISTANCE, step=50, value=0)
    
    st.write("---")
    
    # 保存されている自分の場所のデータがあれば取得
    all_data = load_all_data()
    current_val = all_data.get(str(my_dist), {"clock": 12, "speed": 0.0})
    
    st.info(f"現在の入力値: 【 {current_val['clock']}時方向 / {current_val['speed']} m/s 】")

    # 2. 風向 (クロックポジション)
    st.write("### ① 風向き (時計の針)")
    st.caption("12時=進行方向(向かい風)、6時=追い風")
    
    # 時計のようなボタン配置を作るのは難しいので、グリッドで配置
    # 12, 1, 2
    # 11,    3
    # 10,    4
    # 9, 8, 7... のように並べるか、シンプルに4x3にする
    
    c1, c2, c3, c4 = st.columns(4)
    # 12時から11時までのボタン
    clock_labels = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    
    for i, hour in enumerate(clock_labels):
        with [c1, c2, c3, c4][i % 4]:
            # 選択中は赤くする
            btn_type = "primary" if current_val['clock'] == hour else "secondary"
            if st.button(f"{hour}時", key=f"clk_{hour}", type=btn_type, use_container_width=True):
                save_point_data(my_dist, hour, current_val['speed'])
                st.rerun()

    st.write("---")

    # 3. 風速
    st.write("### ② 風速 (m/s)")
    sc1, sc2, sc3 = st.columns([1, 2, 1])
    with sc1:
        if st.button("➖ 0.5", use_container_width=True):
            new_s = max(0.0, current_val['speed'] - 0.5)
            save_point_data(my_dist, current_val['clock'], new_s)
            st.rerun()
    with sc2:
        st.markdown(f"<h1 style='text-align: center; margin: 0;'>{current_val['speed']:.1f}</h1>", unsafe_allow_html=True)
    with sc3:
        if st.button("➕ 0.5", use_container_width=True):
            new_s = current_val['speed'] + 0.5
            save_point_data(my_dist, current_val['clock'], new_s)
            st.rerun()

    # データ削除ボタン (間違えて場所を入れた時用)
    st.write("")
    if st.button("🗑️ この地点のデータを削除", type="primary"):
        delete_point_data(my_dist)
        st.success("削除しました")
        time.sleep(1)
        st.rerun()
