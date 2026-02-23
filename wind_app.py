import streamlit as st
import json
import os
import time
from datetime import datetime, timedelta, timezone
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np

# ==========================================
# ⚙️ 設定
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BG_IMAGE_FILE = "runway.png" 
# 【追加】全員で「今の走目」を共有するためのファイル
GLOBAL_CONFIG_FILE = os.path.join(BASE_DIR, "wind_global.json") 

REFRESH_RATE = 2
PAD_X = 60
PAD_Y = 80

WIND_LEVELS = {
    "無風": {"val": 0.0, "color": "gray",      "label": "CALM"},
    "微風": {"val": 2.0, "color": "#00BCD4",   "label": "LIGHT"}, 
    "弱風": {"val": 4.5, "color": "#2962FF",   "label": "WEAK"},  
    "中風": {"val": 7.0, "color": "#FFC107",   "label": "MID"},   
    "強風": {"val": 10.0, "color": "#FF5252",  "label": "HIGH"}   
}

# 🛫 用意するフライト（走目）のリスト
RUNS = ["1走目", "2走目", "3走目", "4走目", "5走目"]

# ==========================================
# 💾 関数群
# ==========================================
# 【追加】全体設定（今の走目）を読み込む
def load_global_config():
    if not os.path.exists(GLOBAL_CONFIG_FILE): return {"current_run": RUNS[0]}
    try:
        with open(GLOBAL_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {"current_run": RUNS[0]}

# 【追加】全体設定（今の走目）を保存して全員に知らせる
def save_global_config(run_name):
    try:
        with open(GLOBAL_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump({"current_run": run_name}, f, ensure_ascii=False, indent=2)
    except Exception as e: st.error(str(e))

def get_config_file(run_name):
    return os.path.join(BASE_DIR, f"wind_config_{run_name}.json")

def get_data_file(run_name):
    return os.path.join(BASE_DIR, f"wind_data_{run_name}.json")

def load_config(run_name):
    default_conf = {"max_distance": 600}
    c_file = get_config_file(run_name)
    if not os.path.exists(c_file): return default_conf
    try:
        with open(c_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return default_conf

def save_config(run_name, max_distance):
    config = {"max_distance": max_distance}
    c_file = get_config_file(run_name)
    try:
        with open(c_file, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e: st.error(str(e))

def load_all_data(run_name):
    data_file = get_data_file(run_name)
    if not os.path.exists(data_file): return {}
    try:
        with open(data_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {}

def save_point_data(run_name, distance_m, clock_dir, level_name):
    current_data = load_all_data(run_name)
    dist_key = str(distance_m)
    current_data[dist_key] = {"clock": clock_dir, "level": level_name, "updated": time.time()}
    try:
        data_file = get_data_file(run_name)
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)
    except: pass

def delete_point_data(run_name, distance_m):
    current_data = load_all_data(run_name)
    if str(distance_m) in current_data:
        del current_data[str(distance_m)]
        data_file = get_data_file(run_name)
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(current_data, f, ensure_ascii=False, indent=2)

def clear_all_data(run_name):
    try:
        data_file = get_data_file(run_name)
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    except Exception as e: st.error(str(e))

def draw_map(data, max_dist):
    fig_height = max(6, min(15, 10 * (max_dist / 600)))
    fig, ax = plt.subplots(figsize=(5, fig_height))
    ax.set_xlim(0 - PAD_X, 100 + PAD_X)
    ax.set_ylim(0 - PAD_Y, max_dist + PAD_Y)
    
    bg_path = os.path.join(BASE_DIR, BG_IMAGE_FILE)
    if os.path.exists(bg_path):
        img = mpimg.imread(bg_path)
        ax.imshow(img, extent=[0, 100, 0, max_dist])
    else:
        ax.set_facecolor('#F0F5F0') 
        lawn = plt.Rectangle((0, 0), 100, max_dist, color='#8BC34A', alpha=0.3)
        ax.add_patch(lawn)
        runway = plt.Rectangle((30, 0), 40, max_dist, color='#555555', alpha=0.9)
        ax.add_patch(runway)
        ax.plot([50, 50], [0, max_dist], color='white', linestyle='--', linewidth=2)
        step = 100 if max_dist > 300 else 50
        for d in range(0, max_dist + 1, step):
            ax.text(-25, d, f"{d}m", color='black', fontsize=10, ha='right', va='center',
                    bbox=dict(facecolor='white', alpha=0.6, edgecolor='none', pad=1))

    for dist_key, item in data.items():
        try:
            dist_m = int(dist_key)
            clock = item['clock']
            level_name = item.get('level', "無風")
            level_info = WIND_LEVELS.get(level_name, WIND_LEVELS["無風"])
            speed_val = level_info["val"]
            arrow_color = level_info["color"]
            label_text = level_info["label"]
            if dist_m < 0 or dist_m > max_dist: continue
            x, y = 50, dist_m
            ax.plot(x, y, 'o', color='black', markersize=8, zorder=3)
            
            if level_name != "無風" and speed_val > 0:
                wind_from_angle = 90 - (clock * 30)
                arrow_angle_rad = np.radians(wind_from_angle + 180)
                base_scale = 20.0 if max_dist <= 600 else 30.0
                arrow_len = base_scale + (speed_val * 7.0)
                U = np.cos(arrow_angle_rad) * arrow_len
                V = np.sin(arrow_angle_rad) * arrow_len
                ax.quiver(x, y, U, V, color=arrow_color, angles='xy', scale_units='xy', scale=1,
                          width=0.025, headwidth=4, edgecolor='white', linewidth=1.5, zorder=4)
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
# 🚀 メイン処理
# ==========================================
st.set_page_config(
    page_title="Wind Monitor", 
    page_icon="✈️", 
    layout="centered",
    initial_sidebar_state="expanded"
)

# ----------------------------------------------
# 🛫 フライト(Run) 選択 【全体シンクロ処理】
# ----------------------------------------------
st.sidebar.markdown("### 🛫 フライト選択")

# 1. 全員で共有している「現在の走目」をファイルから読み込む
global_config = load_global_config()
global_run = global_config.get("current_run", RUNS[0])

# 2. 自分の画面の走目が、全体の走目と違っていたら強制的に合わせる
if "current_run" not in st.session_state:
    st.session_state["current_run"] = global_run
elif st.session_state["current_run"] != global_run:
    st.session_state["current_run"] = global_run
    st.rerun() # 画面をリロードして新しい走目に切り替える

# 3. 画面上のセレクトボックス
selected_run = st.sidebar.selectbox("記録・表示するフライト", RUNS, index=RUNS.index(st.session_state["current_run"]))

# 4. 誰かがセレクトボックスを変更したら、全体ファイルに書き込む
if selected_run != st.session_state["current_run"]:
    st.session_state["current_run"] = selected_run
    save_global_config(selected_run) # 全員に知らせる！
    st.rerun()

current_run = st.session_state["current_run"]
st.sidebar.write("---")

# 選択されたフライト専用の設定を読み込む
config = load_config(current_run)
MAX_DISTANCE = config.get("max_distance", 600)

# ----------------------------------------------
# 🔘 デカボタン式モード選択
# ----------------------------------------------
if "current_mode" not in st.session_state:
    st.session_state["current_mode"] = "Ground Crew (Input)" 

st.sidebar.markdown("### 🔀 モード選択")

MODES = [
    "Ground Crew (Input)",
    "Pilot (Map Monitor)",
    "Settings (Config)"
]

for m in MODES:
    is_active = (st.session_state["current_mode"] == m)
    btn_type = "primary" if is_active else "secondary"
    
    if st.sidebar.button(m, key=f"btn_mode_{m}", type=btn_type, use_container_width=True):
        st.session_state["current_mode"] = m
        st.rerun()

mode = st.session_state["current_mode"]
# ----------------------------------------------

pilot_area = st.empty()
crew_area = st.empty()
settings_area = st.empty()

# ----------------------------------------------------
# ✈️ PILOT MODE
# ----------------------------------------------------
if mode == "Pilot (Map Monitor)":
    crew_area.empty()
    settings_area.empty()
    
    with pilot_area.container():
        all_data = load_all_data(current_run)
        
        st.markdown(f"### ✈️ Wind Monitor 【{current_run}】 ({MAX_DISTANCE}m)")
        
        fig = draw_map(all_data, MAX_DISTANCE)
        st.pyplot(fig, use_container_width=True)
        
        JST = timezone(timedelta(hours=9))
        now_jst = datetime.now(JST)
        st.caption(f"Update: {now_jst.strftime('%H:%M:%S')} (JST)")
        plt.close(fig)

    time.sleep(REFRESH_RATE)
    st.rerun()

# ----------------------------------------------------
# 🚩 GROUND CREW MODE
# ----------------------------------------------------
elif mode == "Ground Crew (Input)":
    pilot_area.empty()
    settings_area.empty()
    
    with crew_area.container():
        st.markdown(f"## 🚩 Input Data 【{current_run}】")
        
        default_dist = 0
        if "dist" in st.query_params:
            try: default_dist = int(st.query_params["dist"])
            except: default_dist = 0

        my_dist = st.number_input(f"📍 現在位置 (m) ※最大{MAX_DISTANCE}m", min_value=0, max_value=MAX_DISTANCE, step=50, value=default_dist)
        if my_dist != default_dist: st.query_params["dist"] = str(my_dist)
        st.write("---")
        
        all_data = load_all_data(current_run)
        current_val = all_data.get(str(my_dist), {"clock": 12, "level": "無風"})
        st.info(f"送信先: 【{current_run}】の {my_dist}m = 【 {current_val['level']} 】 ({current_val['clock']}時の風)")

        st.write("### ① 風向き (時計)")
        clock_labels = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        for i in range(0, 12, 3):
            cols = st.columns(3)
            chunk = clock_labels[i : i+3]
            for j, hour in enumerate(chunk):
                with cols[j]:
                    btn_type = "primary" if current_val['clock'] == hour else "secondary"
                    if st.button(f"{hour}時", key=f"clk_{hour}", type=btn_type, use_container_width=True):
                        save_point_data(current_run, my_dist, hour, current_val['level'])
                        st.rerun()

        st.write("---")
        st.write("### ② 風の強さ")
        cols = st.columns(5)
        levels_jp = ["無風", "微風", "弱風", "中風", "強風"]
        for i, lvl in enumerate(levels_jp):
            with cols[i]:
                is_selected = (current_val['level'] == lvl)
                btn_type = "primary" if is_selected else "secondary"
                if st.button(lvl, key=f"lvl_{i}", type=btn_type, use_container_width=True):
                    save_point_data(current_run, my_dist, current_val['clock'], lvl)
                    st.rerun()
                    
        st.write("")
        if st.button("🗑️ この地点のデータを削除", type="secondary"):
            delete_point_data(current_run, my_dist)
            st.rerun()

# ----------------------------------------------------
# ⚙️ SETTINGS MODE
# ----------------------------------------------------
elif mode == "Settings (Config)":
    pilot_area.empty()
    crew_area.empty()

    with settings_area.container():
        st.markdown("## ⚙️ Config")
        st.markdown(f"### 📏 滑走路設定 【{current_run}】")
        new_dist = st.number_input(f"【{current_run}】の滑走路の全長 (m)", value=MAX_DISTANCE, step=50, min_value=100)
        
        if st.button("長さを保存", type="primary"):
            save_config(current_run, new_dist)
            st.success(f"【{current_run}】の設定を保存しました！")
            time.sleep(1)
            st.rerun()
        
        st.write("---")
        
        # 🌟 ここに追加：ダウンロードボタン 🌟
        st.markdown(f"### 📥 データ取り出し 【{current_run}】")
        data_file = get_data_file(current_run)
        if os.path.exists(data_file):
            with open(data_file, "r", encoding="utf-8") as f:
                json_string = f.read()
            st.download_button(
                label=f"💾 {current_run}のデータをダウンロード (JSON)",
                data=json_string,
                file_name=f"wind_data_{current_run}.json",
                mime="application/json",
                type="primary"
            )
        else:
            st.info("まだ保存されたデータがありません。")

        st.write("---")
        
        st.markdown(f"### 🗑️ データ管理 【{current_run}】")
        st.warning(f"現在選択中の「{current_run}」の風データをすべて削除します。")
        if st.button(f"「{current_run}」をクリアする"):
            clear_all_data(current_run)
            st.success(f"{current_run} のデータを削除しました。")
            time.sleep(1)
            st.rerun()
