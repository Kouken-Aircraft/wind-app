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
    # Figure size (5x8 inches)
    fig, ax = plt.subplots(figsize=(5, 8))
    
    # --- Draw Background ---
    bg_path = os.path.join(BASE_DIR, BG_IMAGE_FILE)
    if os.path.exists(bg_path):
        # Use image if available
        img = mpimg.imread(bg_path)
        ax.imshow(img, extent=[0, 100, 0, 400])
    else:
        # Draw default runway (Green background)
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 400)
        ax.set_facecolor('#4CAF50') # Grass Green
        
        # Asphalt
        runway = plt.Rectangle((30, 0), 40, 400, color='gray', alpha=0.8)
        ax.add_patch(runway)
        
        # Center Line
        ax.plot([50, 50], [0, 400], color='white', linestyle='--', linewidth=2)
        ax.text(50, 380, "RUNWAY", color='white', ha='center', fontweight='bold')

    # --- Draw Wind Vectors ---
    for loc_name, coords in LOCATION_COORDS.items():
        if loc_name in data:
            item = data[loc_name]
            speed = item['speed']
            direction_str = item['dir']
            
            # Draw arrow only if wind exists
            if speed > 0:
                angle_deg = DIR_TO_ANGLE.get(direction_str, 90)
                angle_rad = np.radians(angle_deg)
                
                # Vector Components
                scale = 2.0
                U = speed * np.cos(angle_rad) * scale
                V = speed * np.sin(angle_rad) * scale
                
                # Draw Arrow
                ax.quiver(coords[0], coords[1], U, V, 
                          color='red', scale=1, scale_units='xy', 
                          angles='xy', width=0.015, headwidth=4)
                
                # Wind Speed Label
                ax.text(coords[0] + 10, coords[1], f"{speed}m", 
                        color='black', fontsize=12, fontweight='bold', 
                        bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
            
            # Location Label
            ax.text(coords[0] - 25, coords[1], loc_name, 
                    color='blue', fontsize=9, ha='right')

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
