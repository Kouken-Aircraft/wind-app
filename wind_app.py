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

# マップ描画時の矢印の長さ(val)や色の設定
WIND_LEVELS = {
    "無風": {"val": 0.0, "color": "gray",      "label": "無風"},
    "微風": {"val": 0.4, "color": "#00BCD4",   "label": "微風"}, 
    "弱風": {"val": 0.8, "color": "#2962FF",   "label": "弱風"},  
    "中風": {"val": 1.2, "color": "#FFC107",   "label": "中風"},   
    "強風": {"val": 1.5, "color": "#FF5252",  "label": "強風"}   
}

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
    default_config = {"current_run": RUNS[0]}
    if not os.path.exists(GLOBAL_CONFIG_FILE): return default_config
    try:
        with open(GLOBAL_CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return default_config

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
            label_text = level_name 

            if dist_m < 0 or dist_m > max_dist: continue
            x, y = 50, dist_m
            ax.plot(x, y, 'o', color='black', markersize=8, zorder=3)
            
            if level_name != "無風":
                wind_from_angle = 90 - (clock * 30)
                arrow_angle_rad = np.radians(wind_from_angle + 180)
                
                mag = 0.12 + (speed_val * 0.08) 
                
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
    if st.button("🚩 Ground Crew (入力)", type="primary" if is_input else "secondary", use_container_width=True):
        st.session_state["current_mode"] = "🚩 風の入力 (地上クルー用)"
        st.rerun()
        
with col2:
    is_map = (st.session_state["current_mode"] == "✈️ マップを見る (全体監視用)")
    if st.button("✈️ Pilot (マップ)", type="primary" if is_map else "secondary", use_container_width=True):
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
        
        all_data = load_all_data(current_run)
        
        if my_dist is not None:
            st.query_params["dist"] = str(my_dist)
            
            if ("prev_dist" not in st.session_state or st.session_state["prev_dist"] != my_dist) or \
               ("prev_run" not in st.session_state or st.session_state["prev_run"] != current_run):
                st.session_state["prev_dist"] = my_dist
                st.session_state["prev_run"] = current_run
                saved_data = all_data.get(str(my_dist), {})
                st.session_state["selected_clock"] = saved_data.get("clock", None)
        else:
            if "selected_clock" not in st.session_state:
                st.session_state["selected_clock"] = None
            
        st.write("---")
        
        # 表示用のテキスト
        current_val = all_data.get(str(my_dist), {"clock": None, "level": None})
        if current_val['level'] is not None:
            st.info(f"✅ 保存済みデータ: 【 {current_val['level']} 】 ({current_val['clock']}時の風)")
        else:
            st.info("⚠️ この地点はまだ記録されていません")

        # ==================================
        # ① 風向き選択（スマート・ダイヤルUI）
        # ==================================
        st.write("### ① 風向き (時計)")
        
        # null状態からの初期化（選ぶ時は12時を基準にする）
        if st.session_state.get("selected_clock") is None:
            st.session_state["selected_clock"] = 12
            
        clock_options = [12, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
        current_idx = clock_options.index(st.session_state["selected_clock"])
        
        col1, col2, col3 = st.columns([1, 1.5, 1])
        with col1:
            if st.button("◀ 左へ", use_container_width=True):
                if my_dist is None:
                    st.error("⚠️ 上の入力欄に「現在位置 (m)」を入力してください！")
                else:
                    st.session_state["selected_clock"] = clock_options[(current_idx - 1) % 12]
                    st.rerun()
        with col2:
            chosen = st.selectbox(
                "風向", 
                clock_options, 
                index=current_idx, 
                format_func=lambda x: f"🧭 {x}時の方向", 
                label_visibility="collapsed"
            )
            if chosen != st.session_state["selected_clock"]:
                if my_dist is None:
                    st.error("⚠️ 上の入力欄に「現在位置 (m)」を入力してください！")
                else:
                    st.session_state["selected_clock"] = chosen
                    st.rerun()
        with col3:
            if st.button("右へ ▶", use_container_width=True):
                if my_dist is None:
                    st.error("⚠️ 上の入力欄に「現在位置 (m)」を入力してください！")
                else:
                    st.session_state["selected_clock"] = clock_options[(current_idx + 1) % 12]
                    st.rerun()

        st.write("---")

        # ==================================
        # ② 風速ボタン（ここで送信・保存）
        # ==================================
        st.write("### ② 記録・送信")
        cols = st.columns(5)
        levels_jp = ["無風", "微風", "弱風", "中風", "強風"]
        for i, lvl in enumerate(levels_jp):
            with cols[i]:
                is_selected = (current_val['level'] == lvl)
                btn_type = "primary" if is_selected else "secondary"
                
                if st.button(lvl, key=f"lvl_btn_{i}", type=btn_type, use_container_width=True):
                    if my_dist is None:
                        st.error("⚠️ 上の入力欄に「現在位置 (m)」を入力してからボタンを押してください！")
                    else:
                        # 風速ボタンを押した瞬間にマップへ送信・保存
                        save_point_data(current_run, my_dist, st.session_state["selected_clock"], lvl)
                        st.rerun()
                    
        st.write("---")
        if st.button("🗑️ この地点のデータを削除", type="secondary"):
            if my_dist is None:
                st.error("⚠️ 上の入力欄に「現在位置 (m)」を入力してからボタンを押してください！")
            else:
                delete_point_data(current_run, my_dist)
                st.session_state["selected_clock"] = None # 削除したら風向もリセット
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
