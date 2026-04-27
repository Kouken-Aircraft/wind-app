import streamlit as st
import json
import os
import time
import uuid  
from datetime import datetime, timedelta, timezone
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
import matplotlib_fontja  

# ==========================================
# ⚙️ 設定
# ==========================================
TEAM_PASSWORD = "iikanzi"
AUTH_DURATION_HOURS = 5  

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BG_IMAGE_FILE = "runway.png" 
GLOBAL_CONFIG_FILE = os.path.join(BASE_DIR, "wind_global.json") 
AUTH_FILE = os.path.join(BASE_DIR, "wind_auth.json") 

REFRESH_RATE = 2
PAD_X = 60
PAD_Y = 80

WIND_LEVELS = {
    "無風": {"val": 0.0, "color": "gray",      "label": "無風"},
    "微風": {"val": 1.0, "color": "#00BCD4",   "label": "微風"}, 
    "弱風": {"val": 2.5, "color": "#2962FF",   "label": "弱風"},  
    "中風": {"val": 3.5, "color": "#FFC107",   "label": "中風"},   
    "強風": {"val": 4.5, "color": "#FF5252",  "label": "強風"}   
}

def get_level_from_speed(speed):
    if speed <= 0.5: return "無風"
    elif speed <= 1.5: return "微風"
    elif speed <= 3.0: return "弱風"
    elif speed <= 4.0: return "中風"
    else: return "強風"

RUNS = [f"{i}走目" for i in range(1, 21)]

# ==========================================
# 💾 関数群
# ==========================================
def load_valid_tokens():
    if not os.path.exists(AUTH_FILE): return {}
    try:
        with open(AUTH_FILE, "r", encoding="utf-8") as f:
            tokens = json.load(f)
            current_time = time.time()
            return {k: v for k, v in tokens.items() if v > current_time}
    except: return {}

def save_auth_token(token):
    tokens = load_valid_tokens()
    tokens[token] = time.time() + (AUTH_DURATION_HOURS * 3600)
    try:
        with open(AUTH_FILE, "w", encoding="utf-8") as f:
            json.dump(tokens, f, ensure_ascii=False, indent=2)
    except: pass

def load_global_config():
    if not os.path.exists(GLOBAL_CONFIG_FILE): return {"current_run": RUNS[0]}
    try:
        with open(GLOBAL_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {"current_run": RUNS[0]}

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

def save_point_data(run_name, distance_m, clock_dir, level_name, speed_val=None):
    current_data = load_all_data(run_name)
    dist_key = str(distance_m)
    
    if speed_val is None:
        speed_val = WIND_LEVELS[level_name]["val"]
        
    current_data[dist_key] = {"clock": clock_dir, "level": level_name, "speed": speed_val, "updated": time.time()}
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
            
            speed_val = item.get('speed', WIND_LEVELS.get(level_name, WIND_LEVELS["無風"])["val"])
            
            level_info = WIND_LEVELS.get(level_name, WIND_LEVELS["無風"])
            arrow_color = level_info["color"]
            
            if speed_val > 0.5:
                label_text = f"{level_name}({speed_val}m)"
            else:
                label_text = "無風"

            if dist_m < 0 or dist_m > max_dist: continue
            x, y = 50, dist_m
            ax.plot(x, y, 'o', color='black', markersize=8, zorder=3)
            
            if speed_val > 0.5:
                wind_from_angle = 90 - (clock * 30)
                arrow_angle_rad = np.radians(wind_from_angle + 180)
                
                mag = 0.12 + (speed_val * 0.04) 
                
                U = np.cos(arrow_angle_rad) * mag
                V = np.sin(arrow_angle_rad) * mag
                
                ax.quiver(x, y, U, V, color=arrow_color, 
                          angles='uv', scale_units='width', scale=1,
                          width=0.025, headwidth=4, headlength=5, 
                          edgecolor='white', linewidth=1.0, zorder=4)
                          
                ax.text(x + 20, y, label_text, color='black', fontsize=12, fontweight='bold',
                        bbox=dict(facecolor='white', alpha=0.8, boxstyle='round,pad=0.3', edgecolor='none'), zorder=5)
            else:
                ax.text(x + 20, y, "無風", color='gray', fontsize=11, fontweight='bold',
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
    initial_sidebar_state="collapsed"
)

# ----------------------------------------------
# 🔒 パスワード（ログイン）処理
# ----------------------------------------------
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

url_token = st.query_params.get("session")

if url_token and not st.session_state["authenticated"]:
    valid_tokens = load_valid_tokens()
    if url_token in valid_tokens:
        st.session_state["authenticated"] = True

if not st.session_state["authenticated"]:
    st.markdown("## 🔒 チーム専用アクセス")
    st.info(f"このアプリを利用するにはパスワードが必要です。")
    
    with st.form(key="login_form"):
        pwd_input = st.text_input("パスワードを入力", type="password")
        submit_btn = st.form_submit_button("ログイン", type="primary")
        
        if submit_btn:
            if pwd_input == TEAM_PASSWORD:
                st.session_state["authenticated"] = True
                new_token = str(uuid.uuid4())
                save_auth_token(new_token)
                st.query_params["session"] = new_token
                st.success("ログイン成功！アプリを起動します...")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ パスワードが違います")
                
    st.stop() 

# ==========================================
# （ここから下はログイン成功した人だけが見れる）
# ==========================================

if "current_mode" not in st.session_state:
    st.session_state["current_mode"] = "🚩 風の入力 (地上クルー用)"

# ----------------------------------------------
# 🛫 サイドバー (走目選択 ＆ 設定メニュー)
# ----------------------------------------------
st.sidebar.markdown("### 🛫 どのフライト？ (走目選択)")

global_config = load_global_config()
global_run = global_config.get("current_run", RUNS[0])

if "current_run" not in st.session_state:
    st.session_state["current_run"] = global_run
elif st.session_state["current_run"] != global_run:
    st.session_state["current_run"] = global_run
    st.rerun()

selected_run = st.sidebar.selectbox("記録・表示するフライト", RUNS, index=RUNS.index(st.session_state["current_run"]), label_visibility="collapsed")

if selected_run != st.session_state["current_run"]:
    st.session_state["current_run"] = selected_run
    save_global_config(selected_run)
    st.rerun()

current_run = st.session_state["current_run"]
config = load_config(current_run)
MAX_DISTANCE = config.get("max_distance", 600)

st.sidebar.write("---")

st.sidebar.markdown("### ⚙️ 管理者メニュー")
is_settings = (st.session_state["current_mode"] == "⚙️ アプリの設定 (管理者用)")
if st.sidebar.button("⚙️ アプリの設定", type="primary" if is_settings else "secondary", use_container_width=True):
    st.session_state["current_mode"] = "⚙️ アプリの設定 (管理者用)"
    st.rerun()

# ----------------------------------------------
# 🔀 メイン画面トップ
# ----------------------------------------------
col1, col2 = st.columns(2)
with col1:
    is_input = (st.session_state["current_mode"] == "🚩 風の入力 (地上クルー用)")
    if st.button("🚩 入力", type="primary" if is_input else "secondary", use_container_width=True):
        st.session_state["current_mode"] = "🚩 風の入力 (地上クルー用)"
        st.rerun()
        
with col2:
    is_map = (st.session_state["current_mode"] == "✈️ マップを見る (全体監視用)")
    if st.button("✈️ マップ", type="primary" if is_map else "secondary", use_container_width=True):
        st.session_state["current_mode"] = "✈️ マップを見る (全体監視用)"
        st.rerun()

st.write("---")

mode = st.session_state["current_mode"]

# ----------------------------------------------

pilot_area = st.empty()
crew_area = st.empty()
settings_area = st.empty()

# ----------------------------------------------------
# ✈️ PILOT MODE
# ----------------------------------------------------
if mode == "✈️ マップを見る (全体監視用)":
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
elif mode == "🚩 風の入力 (地上クルー用)":
    pilot_area.empty()
    settings_area.empty()
    
    with crew_area.container():
        st.markdown(f"## 🚩 Input Data 【{current_run}】")
        
        default_dist = None
        if "dist" in st.query_params:
            try: default_dist = int(st.query_params["dist"])
            except: default_dist = None

        my_dist = st.number_input(
            f"📍 現在位置 (m) ※最大{MAX_DISTANCE}m", 
            min_value=0, 
            max_value=MAX_DISTANCE, 
            step=50, 
            value=default_dist,
            placeholder="数値を入力"
        )
        
        if my_dist is not None and my_dist != default_dist: 
            st.query_params["dist"] = str(my_dist)
            
        st.write("---")
        
        all_data = load_all_data(current_run)
        current_val = all_data.get(str(my_dist), {"clock": 12, "level": "無風", "speed": 0.0})
        
        dist_display = f"{my_dist}m" if my_dist is not None else "【未入力】"
        st.info(f"送信先: 【{current_run}】の {dist_display} = 【 {current_val['level']}({current_val.get('speed', 0.0)}m) 】 ({current_val['clock']}時の風)")

        st.write("### ① 風向き (時計)")
        clock_labels = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        for i in range(0, 12, 3):
            cols = st.columns(3)
            chunk = clock_labels[i : i+3]
            for j, hour in enumerate(chunk):
                with cols[j]:
                    btn_type = "primary" if current_val['clock'] == hour else "secondary"
                    if st.button(f"{hour}時", key=f"clk_{hour}", type=btn_type, use_container_width=True):
                        if my_dist is None:
                            st.error("⚠️ 上の入力欄に「現在位置 (m)」を入力してからボタンを押してください！")
                        else:
                            save_point_data(current_run, my_dist, hour, current_val['level'], current_val.get('speed', 0.0))
                            st.rerun()

        st.write("---")
        
        # 🌟【変更】ボタンを無くし、スライダー操作だけで即保存するようにしました！
        st.write("### ② 風の強さ (m/s)")
        
        init_speed = current_val.get('speed', WIND_LEVELS[current_val['level']]["val"])
        if init_speed > 5.0:
            init_speed = 5.0
            
        # on_changeを使って、スライダーから指を離した瞬間に処理を走らせます
        def on_speed_change():
            if my_dist is not None:
                new_speed = st.session_state["speed_slider"]
                auto_level = get_level_from_speed(new_speed)
                save_point_data(current_run, my_dist, current_val['clock'], auto_level, new_speed)

        selected_speed = st.slider(
            "指でスライドして風速を設定", 
            min_value=0.0, 
            max_value=5.0, 
            value=float(init_speed), 
            step=0.5,
            key="speed_slider",
            on_change=on_speed_change  # 🌟 指を離した瞬間に上の関数が動いて保存！
        )
        
        auto_level = get_level_from_speed(selected_speed)
        level_color = WIND_LEVELS[auto_level]["color"]
        
        # 🌟 即保存されるので、確認用に「保存済み」の文字を出します
        st.markdown(f"**自動判定:** <span style='color:{level_color}; font-size:20px; font-weight:bold;'>{auto_level}</span>", unsafe_allow_html=True)
                    
        st.write("---")
        if st.button("🗑️ この地点のデータを削除", type="secondary"):
            if my_dist is None:
                st.error("⚠️ 上の入力欄に「現在位置 (m)」を入力してからボタンを押してください！")
            else:
                delete_point_data(current_run, my_dist)
                st.rerun()

# ----------------------------------------------------
# ⚙️ SETTINGS MODE
# ----------------------------------------------------
elif mode == "⚙️ アプリの設定 (管理者用)":
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
        
        st.markdown(f"### 📥 データのダウンロード (エクスポート)")
        current_data = load_all_data(current_run)
        export_bundle = {
            "max_distance": MAX_DISTANCE,
            "wind_data": current_data
        }
        json_string = json.dumps(export_bundle, ensure_ascii=False, indent=2)
        st.download_button(
            label=f"💾 {current_run} のデータを保存 (JSON)",
            data=json_string,
            file_name=f"wind_data_{current_run}.json",
            mime="application/json"
        )

        st.write("---")
        
        st.markdown(f"### 📤 データのアップロード (一括インポート対応)")
        st.caption("手元にあるJSONファイルを読み込ませて復元します。複数ファイルを一気に選んで「一括インポート」も可能です！\n※ファイル名（例: `wind_data_1走目.json`）から自動で走目を判定します。")
        
        uploaded_files = st.file_uploader("ファイルを選択してください", type=["json"], accept_multiple_files=True)
        
        if uploaded_files:
            if st.button("選択したファイルで上書きする", type="primary"):
                success_count = 0
                for uploaded_file in uploaded_files:
                    try:
                        uploaded_data = json.load(uploaded_file)
                        
                        file_name = uploaded_file.name
                        target_run = file_name.replace("wind_data_", "").replace(".json", "")
                        
                        if target_run not in RUNS:
                            if len(uploaded_files) == 1:
                                target_run = current_run 
                            else:
                                st.warning(f"⚠️ {file_name} は走目が判定できないためスキップしました。")
                                continue
                                
                        data_file = get_data_file(target_run)
                        
                        if "wind_data" in uploaded_data and "max_distance" in uploaded_data:
                            save_config(target_run, uploaded_data["max_distance"])
                            with open(data_file, "w", encoding="utf-8") as f:
                                json.dump(uploaded_data["wind_data"], f, ensure_ascii=False, indent=2)
                        else:
                            with open(data_file, "w", encoding="utf-8") as f:
                                json.dump(uploaded_data, f, ensure_ascii=False, indent=2)
                        
                        success_count += 1
                        
                    except Exception as e:
                        st.error(f"❌ {uploaded_file.name} 読み込みエラー: {e}")
                        
                if success_count > 0:
                    st.success(f"✅ {success_count} 件のデータを読み込みました！")
                    time.sleep(1.5)
                    st.rerun()

        st.write("---")
        
        st.markdown(f"### 🗑️ 個別データ削除 【{current_run}】")
        st.warning(f"現在選択中の「{current_run}」の風データのみを削除します。")
        if st.button(f"「{current_run}」をクリアする"):
            clear_all_data(current_run)
            st.success(f"{current_run} のデータを削除しました。")
            time.sleep(1)
            st.rerun()

        st.write("---")

        st.markdown("### 💣 全データ削除")
        st.warning("記録されている**すべてのフライト（1走目〜20走目）**の風データを一括で削除します。この操作は元に戻せません。")
        if st.button("🚨 すべてのデータを完全に削除する", type="primary"):
            for r in RUNS:
                clear_all_data(r)
            st.success("すべてのフライトデータを完全に削除しました！")
            time.sleep(1.5)
            st.rerun()
