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
DATA_FILE = os.path.join(BASE_DIR, "wind_data_v4.json") # ファイル名変更
BG_IMAGE_FILE = "runway.png" 

REFRESH_RATE = 2  # 自動更新間隔
MAX_DISTANCE = 1000  # 滑走路全長 (m)

# 風の強さ定義（表示名と、矢印を描くための仮の風速値）
WIND_LEVELS = {
    "無風": {"val": 0.0, "color": "gray"},
    "微風": {"val": 2.0, "color": "#2196F3"}, # 青
    "弱風": {"val": 4.0, "color": "#2196F3"}, # 青
    "中風": {"val": 6.0, "color": "#FFC107"}, # 黄
    "強風": {"val": 9.0, "color": "#FF5252"}  # 赤
}
LEVEL_NAMES = list(WIND_LEVELS.keys())

# ==========================================
# 💾 データ管理
# ==========================================
def load_all_data():
    if not os.path.exists(DATA_FILE): return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {}

def save_point_data(distance_m, clock_dir, level_name):
    """
    level_name: "強風" などの文字列を受け取る
    """
    current_data = load_all_data()
    dist_key = str(distance_m)
    current_data[dist_key] = {
        "clock": clock_dir, 
        "level": level_name, # 数値ではなく言葉で保存
        "updated": time.time()
    }
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
    fig, ax = plt.subplots(figsize=(5, 10))
    
    # --- 背景 ---
    bg_path = os.path.join(BASE_DIR, BG_IMAGE_FILE)
    if os.path.exists(bg_path):
        img = mpimg.imread(bg_path)
        ax.imshow(img, extent=[0, 100, 0, MAX_DISTANCE])
    else:
        ax.set_xlim(0, 100); ax.set_ylim(0, MAX_DISTANCE)
        ax.set_facecolor('#8BC34A')
        runway = plt.Rectangle((30, 0), 40, MAX_DISTANCE, color='#555555', alpha=0.9)
        ax.add_patch(runway)
        ax.plot([50, 50], [0, MAX_DISTANCE], color='white', linestyle='--', linewidth=2)
        for d in range(0, MAX_DISTANCE + 1, 100):
            ax.text(25, d, f"{d}m", color='white', fontsize=8, ha='right', va='center')

    # --- 矢印描画 ---
    for dist_key, item in data.items():
        try:
            dist_m = int(dist_key)
            clock = item['clock']
            level_name = item.get('level', "無風")
            
            # 風レベルから、矢印の長さ(val)と色(color)を取得
            level_info = WIND_LEVELS.get(level_name, WIND_LEVELS["無風"])
            speed_val = level_info["val"]
            arrow_color = level_info["color"]
            
            if dist_m < 0 or dist_m > MAX_DISTANCE: continue
            
            x, y = 50, dist_m
            
            # 計測点マーカー
            ax.plot(x, y, 'o', color='black', markersize=8, zorder=3)
            
            # 無風なら矢印を描かない
            if level_name != "無風" and speed_val > 0:
                # 角度計算 (12時=北=90度 からの変換)
                wind_from_angle = 90 - (clock * 30)
                arrow_angle_rad = np.radians(wind_from_angle + 180) # 風下へ向ける
                
                # ベクトル計算
                scale = 20.0 # 基本サイズ
                # 強風ほど矢印を少し長くする補正
                len_factor = 1.0 + (speed_val / 10.0) 
                
                U = np.cos(arrow_angle_rad) * scale * len_factor
                V = np.sin(arrow_angle_rad) * scale * len_factor
                
                # 矢印
                ax.quiver(x, y, U, V, color=arrow_color, 
                          angles='xy', scale_units='xy', scale=1,
                          width=0.025, headwidth=5, 
                          edgecolor='white', linewidth=1.5, zorder=4)
                
                # ラベル表示（風速値も時計も消して、レベル名だけ表示）
                # 例: [ 矢印 ] -> "強風"
                ax.text(x + 15, y, level_name, color='black', fontsize=14, fontweight='bold',
                        bbox=dict(facecolor='white', alpha=0.8, boxstyle='round,pad=0.3'), zorder=5)
            else:
                # 無風の場合は文字だけ出す
                ax.text(x + 15, y, "無風", color='gray', fontsize=12, fontweight='bold',
                        bbox=dict(facecolor='white', alpha=0.8, boxstyle='round'), zorder=5)
                
        except: continue

    ax.axis('off')
    return fig

# ==========================================
# 📱 アプリ画面
# ==========================================
st.set_page_config(page_title="Wind Monitor V4", layout="centered")

mode = st.sidebar.radio("Mode", ["Ground Crew (Input)", "Pilot (Map Monitor)"])

# ------------------------------------------
# ✈️ PILOT MODE
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
# 🚩 GROUND CREW MODE
# ------------------------------------------
else:
    st.markdown("## 🚩 Input Data")
    
    # 自分の場所
    my_dist = st.number_input("📍 現在位置 (m)", 
                              min_value=0, max_value=MAX_DISTANCE, step=50, value=0)
    st.write("---")
    
    # 現在のデータ取得
    all_data = load_all_data()
    current_val = all_data.get(str(my_dist), {"clock": 12, "level": "無風"})
    
    # 表示
    st.info(f"送信中: {my_dist}m地点 = 【 {current_val['level']} 】 ( {current_val['clock']}時の風 )")

    # 1. 風向き (クロック)
    st.write("### ① 風向き (時計)")
    c1, c2, c3, c4 = st.columns(4)
    clock_labels = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    
    for i, hour in enumerate(clock_labels):
        with [c1, c2, c3, c4][i % 4]:
            btn_type = "primary" if current_val['clock'] == hour else "secondary"
            if st.button(f"{hour}時", key=f"clk_{hour}", type=btn_type, use_container_width=True):
                # 風向きを変えたら、強さはそのままで保存
                save_point_data(my_dist, hour, current_val['level'])
                st.rerun()

    st.write("---")

    # 2. 風の強さ (5段階ボタン)
    st.write("### ② 風の強さ")
    
    # 5つのボタンを並べる
    cols = st.columns(5)
    levels = ["無風", "微風", "弱風", "中風", "強風"]
    
    for i, lvl in enumerate(levels):
        with cols[i]:
            # 選択中のボタンは色を変える
            is_selected = (current_val['level'] == lvl)
            btn_type = "primary" if is_selected else "secondary"
            
            if st.button(lvl, key=f"lvl_{i}", type=btn_type, use_container_width=True):
                save_point_data(my_dist, current_val['clock'], lvl)
                st.rerun()
                
    st.write("")
    if st.button("🗑️ データ削除", type="secondary"):
        delete_point_data(my_dist)
        st.rerun()
