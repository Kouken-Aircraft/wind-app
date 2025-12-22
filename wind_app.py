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
DATA_FILE = os.path.join(BASE_DIR, "wind_data_v7.json")
BG_IMAGE_FILE = "runway.png" 

REFRESH_RATE = 2
# 【変更点1】 全長を600mに設定
MAX_DISTANCE = 600  

# 余白の設定 (見切れ防止用)
# 滑走路エリアの外側にどれだけスペースを取るか
PAD_X = 50  # 横の余白
PAD_Y = 80  # 上下の余白

WIND_LEVELS = {
    "無風": {"val": 0.0, "color": "gray",      "label": "CALM"},
    "微風": {"val": 2.0, "color": "#2196F3",   "label": "LIGHT"}, 
    "弱風": {"val": 4.0, "color": "#2196F3",   "label": "WEAK"},  
    "中風": {"val": 6.0, "color": "#FFC107",   "label": "MID"},   
    "強風": {"val": 9.0, "color": "#FF5252",   "label": "HIGH"}   
}

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
    current_data = load_all_data()
    dist_key = str(distance_m)
    current_data[dist_key] = {
        "clock": clock_dir, 
        "level": level_name, 
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
# 🎨 マップ描画 (600m対応 & 余白追加)
# ==========================================
def draw_map(data):
    # 600mを表示するため、縦長比率を調整 (幅5, 高さ10インチ)
    fig, ax = plt.subplots(figsize=(5, 10))
    
    # 【変更点2】 表示範囲(カメラ)を広げる設定
    # 実際の滑走路は 0~100(横), 0~600(縦) ですが
    # 表示範囲を -50~150, -80~680 に広げて、端っこの矢印も映るようにします
    ax.set_xlim(0 - PAD_X, 100 + PAD_X)
    ax.set_ylim(0 - PAD_Y, MAX_DISTANCE + PAD_Y)
    
    # --- 背景 (滑走路本体) ---
    bg_path = os.path.join(BASE_DIR, BG_IMAGE_FILE)
    if os.path.exists(bg_path):
        img = mpimg.imread(bg_path)
        # 画像はあくまで 0～MAX_DISTANCE の間に描画
        ax.imshow(img, extent=[0, 100, 0, MAX_DISTANCE])
    else:
        # 背景全体を少し薄い緑にする(余白部分)
        ax.set_facecolor('#F0F5F0') 
        
        # 滑走路エリアの緑 (0-100, 0-600)
        lawn = plt.Rectangle((0, 0), 100, MAX_DISTANCE, color='#8BC34A', alpha=0.3)
        ax.add_patch(lawn)
        
        # アスファルト
        runway = plt.Rectangle((30, 0), 40, MAX_DISTANCE, color='#555555', alpha=0.9)
        ax.add_patch(runway)
        
        # センターライン
        ax.plot([50, 50], [0, MAX_DISTANCE], color='white', linestyle='--', linewidth=2)
        
        # 距離マーカー (100mごと)
        for d in range(0, MAX_DISTANCE + 1, 100):
            # 文字が埋もれないよう背景色をつける
            ax.text(20, d, f"{d}m", color='black', fontsize=9, ha='right', va='center',
                    bbox=dict(facecolor='white', alpha=0.5, edgecolor='none', pad=1))

    # --- 矢印描画 ---
    for dist_key, item in data.items():
        try:
            dist_m = int(dist_key)
            clock = item['clock']
            level_name = item.get('level', "無風")
            
            level_info = WIND_LEVELS.get(level_name, WIND_LEVELS["無風"])
            speed_val = level_info["val"]
            arrow_color = level_info["color"]
            label_text = level_info["label"]
            
            # 範囲外データは描画しない (ただし余白があるので多少は許容できる)
            if dist_m < 0 or dist_m > MAX_DISTANCE: continue
            
            x, y = 50, dist_m
            
            # マーカー
            ax.plot(x, y, 'o', color='black', markersize=8, zorder=3)
            
            if level_name != "無風" and speed_val > 0:
                wind_from_angle = 90 - (clock * 30)
                arrow_angle_rad = np.radians(wind_from_angle + 180)
                
                # 矢印の長さ調整 (600mスケールに合わせて少し大きく補正)
                arrow_len = 25.0 + (speed_val * 6.0)
                
                U = np.cos(arrow_angle_rad) * arrow_len
                V = np.sin(arrow_angle_rad) * arrow_len
                
                ax.quiver(x, y, U, V, color=arrow_color, 
                          angles='xy', scale_units='xy', scale=1,
                          width=0.025, headwidth=4, 
                          edgecolor='white', linewidth=1.5, zorder=4)
                
                ax.text(x + 20, y, label_text, color='black', fontsize=12, fontweight='bold',
                        bbox=dict(facecolor='white', alpha=0.8, boxstyle='round,pad=0.3', edgecolor='none'), zorder=5)
            else:
                ax.text(x + 20, y, "CALM", color='gray', fontsize=11, fontweight='bold',
                        bbox=dict(facecolor='white', alpha=0.8, boxstyle='round', edgecolor='none'), zorder=5)
                
        except: continue

    ax.axis('off')
    plt.tight_layout()
    return fig

# ==========================================
# 📱 アプリ画面
# ==========================================
st.set_page_config(page_title="Wind Monitor V7", layout="centered")

mode = st.sidebar.radio("Mode", ["Ground Crew (Input)", "Pilot (Map Monitor)"])

# ------------------------------------------
# ✈️ PILOT MODE
# ------------------------------------------
if mode == "Pilot (Map Monitor)":
    st.markdown("## ✈️ Wind Map (600m)")
    all_data = load_all_data()
    fig = draw_map(all_data)
    st.pyplot(fig)
    st.caption(f"Update: {time.strftime('%H:%M:%S')}")
    time.sleep(REFRESH_RATE)
    st.rerun()

# ------------------------------------------
# 🚩 GROUND CREW MODE
# ------------------------------------------
else:
    st.markdown("## 🚩 Input Data")
    
    # スライダーの最大値を600mに変更
    my_dist = st.number_input("📍 現在位置 (m)", 
                              min_value=0, max_value=MAX_DISTANCE, step=50, value=0)
    st.write("---")
    
    all_data = load_all_data()
    current_val = all_data.get(str(my_dist), {"clock": 12, "level": "無風"})
    
    st.info(f"送信データ: {my_dist}m = 【 {current_val['level']} 】 ({current_val['clock']}時の風)")

    # 1. 風向き
    st.write("### ① 風向き (時計)")
    c1, c2, c3, c4 = st.columns(4)
    clock_labels = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    for i, hour in enumerate(clock_labels):
        with [c1, c2, c3, c4][i % 4]:
            btn_type = "primary" if current_val['clock'] == hour else "secondary"
            if st.button(f"{hour}時", key=f"clk_{hour}", type=btn_type, use_container_width=True):
                save_point_data(my_dist, hour, current_val['level'])
                st.rerun()

    st.write("---")

    # 2. 風の強さ
    st.write("### ② 風の強さ")
    cols = st.columns(5)
    levels_jp = ["無風", "微風", "弱風", "中風", "強風"]
    
    for i, lvl in enumerate(levels_jp):
        with cols[i]:
            is_selected = (current_val['level'] == lvl)
            btn_type = "primary" if is_selected else "secondary"
            if st.button(lvl, key=f"lvl_{i}", type=btn_type, use_container_width=True):
                save_point_data(my_dist, current_val['clock'], lvl)
                st.rerun()
                
    st.write("")
    if st.button("🗑️ データ削除", type="secondary"):
        delete_point_data(my_dist)
        st.rerun()
