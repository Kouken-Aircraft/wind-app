import streamlit as st
import json
import os
import time
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np

# ==========================================
# ⚙️ CONFIGURATION
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "wind_data_v2.json")
BG_IMAGE_FILE = "runway.png" 

REFRESH_RATE = 3  # Auto-refresh interval (sec)

# 📍 LOCATION CONFIGURATION
# (X, Y) coordinates relative to the map (0-100, 0-400)
LOCATION_COORDS = {
    "Start Point": (50, 20),
    "200m":        (50, 100),
    "400m":        (50, 180),
    "600m":        (50, 260),
    "Goal Area":   (50, 340)
}
LOCATIONS = list(LOCATION_COORDS.keys())

# Wind Directions (English)
DIRECTIONS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

# Direction to Angle Mapping (North=90deg in math)
DIR_TO_ANGLE = {
    "N": 90, "NE": 45, "E": 0, "SE": -45,
    "S": -90, "SW": -135, "W": 180, "NW": 135
}

# ==========================================
# 💾 DATA MANAGEMENT
# ==========================================
def load_all_data():
    if not os.path.exists(DATA_FILE):
        # Create default data
        initial_data = {loc: {"dir": "N", "speed": 0.0} for loc in LOCATIONS}
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, ensure_ascii=False, indent=2)
        except: pass
        return initial_data
    
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {loc: {"dir": "N", "speed": 0.0} for loc in LOCATIONS}

def save_location_data(location, direction, speed):
    current_all_data = load_all_data()
    current_all_data[location] = {"dir": direction, "speed": speed}
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_all_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Save Error: {e}")

# ==========================================
# 🎨 MAP DRAWING FUNCTION
# ==========================================
def draw_map(data):
    # Figure size (スマホで見やすい縦横比)
    fig, ax = plt.subplots(figsize=(5, 8))
    
    # --- Draw Background (背景) ---
    bg_path = os.path.join(BASE_DIR, BG_IMAGE_FILE)
    if os.path.exists(bg_path):
        img = mpimg.imread(bg_path)
        ax.imshow(img, extent=[0, 100, 0, 400])
    else:
        # Default Green Runway
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 400)
        ax.set_facecolor('#8BC34A') # 明るめの緑に変更
        
        # Asphalt
        runway = plt.Rectangle((30, 0), 40, 400, color='#555555', alpha=0.9)
        ax.add_patch(runway)
        
        # Center Line
        ax.plot([50, 50], [0, 400], color='white', linestyle='--', linewidth=3)
        ax.text(50, 380, "RUNWAY", color='white', ha='center', fontweight='bold', fontsize=15)

    # --- Draw Wind Vectors (矢印) ---
    for loc_name, coords in LOCATION_COORDS.items():
        if loc_name in data:
            item = data[loc_name]
            speed = item['speed']
            direction_str = item['dir']
            
            # 計測地点に黒い点を打つ (アンカー)
            ax.plot(coords[0], coords[1], 'o', color='black', markersize=8, zorder=3)
            
            if speed > 0:
                # 風向きの計算 (北風は「南に向かうベクトル」なので -90度)
                # Mathematical: 0=East, 90=North. 
                # Wind "FROM North" blows "TO South" (-90 deg).
                wind_angle_map = {
                    "N": -90, "NE": -135, "E": 180, "SE": 135,
                    "S": 90,  "SW": 45,   "W": 0,   "NW": -45
                }
                
                angle_deg = wind_angle_map.get(direction_str, -90)
                angle_rad = np.radians(angle_deg)
                
                # 色の決定 (信号機カラー)
                arrow_color = '#2196F3' # Blue (Safe)
                if speed >= 3.0: arrow_color = '#FFC107' # Yellow (Caution)
                if speed >= 5.0: arrow_color = '#FF5252' # Red (Danger)

                # ベクトル成分
                # 矢印の長さはある程度一定にして見やすく、太さで強調する
                scale = 15.0 
                U = np.cos(angle_rad) * scale
                V = np.sin(angle_rad) * scale
                
                # 矢印を描画 (quiverのパラメータを調整して太くする)
                ax.quiver(coords[0], coords[1], U, V, 
                          color=arrow_color, 
                          angles='xy', scale_units='xy', scale=1,
                          width=0.025,       # 太さ (以前は0.015)
                          headwidth=5,       # 頭の横幅
                          headlength=4,      # 頭の長さ
                          headaxislength=3.5, 
                          edgecolor='white', # 矢印に白いフチをつける
                          linewidth=1.5,
                          zorder=4)          # 最前面に表示
                
                # 風速のラベル (白いボックス付きで見やすく)
                ax.text(coords[0] + 15, coords[1], f"{speed}m", 
                        color='black', fontsize=14, fontweight='bold', 
                        bbox=dict(facecolor='white', alpha=0.8, edgecolor='black', boxstyle='round,pad=0.3'),
                        zorder=5)
            
            # 地点名ラベル
            ax.text(coords[0] - 10, coords[1], loc_name, 
                    color='white', fontsize=10, ha='right', fontweight='bold',
                    bbox=dict(facecolor='black', alpha=0.5, edgecolor='none', pad=0.2),
                    zorder=5)

    ax.axis('off')
    return fig

# ==========================================
# 📱 MAIN APPLICATION
# ==========================================
st.set_page_config(page_title="Birdman Wind Map", layout="centered")

# Sidebar Mode Selection
mode = st.sidebar.radio("Mode Selection", ["Controller (Ground Crew)", "Monitor (Map View)"])

all_data = load_all_data()

# ------------------------------------------
# 🗺️ MONITOR MODE
# ------------------------------------------
if mode == "Monitor (Map View)":
    st.markdown("## 🗺️ Real-time Wind Map")
    
    fig = draw_map(all_data)
    st.pyplot(fig)
    
    st.caption(f"Auto-refreshing... ({REFRESH_RATE}s)")
    time.sleep(REFRESH_RATE)
    st.rerun()

# ------------------------------------------
# 🚩 CONTROLLER MODE
# ------------------------------------------
else:
    st.markdown("## 🚩 Data Input")
    
    selected_loc = st.selectbox("📍 Select Location", LOCATIONS)
    
    st.write("---")
    
    # Get current data for selected location
    target_data = all_data.get(selected_loc, {"dir": "N", "speed": 0.0})
    
    # Display current status
    st.info(f"Current: {selected_loc} -> 【 {target_data['dir']} / {target_data['speed']} m/s 】")

    # === Wind Direction ===
    st.write("Wind Direction")
    c1, c2, c3, c4 = st.columns(4)
    for i, d in enumerate(DIRECTIONS):
        with [c1, c2, c3, c4][i % 4]:
            btn_type = "primary" if target_data['dir'] == d else "secondary"
            if st.button(d, key=f"d_{i}", type=btn_type, use_container_width=True):
                save_location_data(selected_loc, d, target_data['speed'])
                st.rerun()

    # === Wind Speed ===
    st.write("Wind Speed (m/s)")
    sc1, sc2, sc3 = st.columns([1, 2, 1])
    with sc1:
        if st.button("➖ 0.5", use_container_width=True):
            save_location_data(selected_loc, target_data['dir'], max(0.0, target_data['speed'] - 0.5))
            st.rerun()
    with sc2:
        st.markdown(f"<h2 style='text-align: center; margin: 0;'>{target_data['speed']:.1f}</h2>", unsafe_allow_html=True)
    with sc3:
        if st.button("➕ 0.5", use_container_width=True):
            save_location_data(selected_loc, target_data['dir'], target_data['speed'] + 0.5)
            st.rerun()
            
    # Preset Buttons
    st.write("Quick Set")
    cols = st.columns(5)
    for i, p in enumerate([0.0, 1.0, 2.0, 3.0, 5.0]):
        with cols[i]:
            if st.button(str(p), key=f"p_{i}", use_container_width=True):
                save_location_data(selected_loc, target_data['dir'], p)
                st.rerun()

