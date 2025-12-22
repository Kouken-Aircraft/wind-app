import streamlit as st
import json
import os
import time

# ==========================================
# ⚙️ 設定・ファイルパス
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "wind_data_v2.json") # ファイル名を変更
REFRESH_RATE = 3 # 更新頻度（秒）

# 📍 計測地点のリスト（ここを自由に増減してください）
LOCATIONS = [
    "① スタート地点",
    "② 200m地点",
    "③ 400m地点",
    "④ 600m地点",
    "⑤ ゴール付近"
]
DIRECTIONS = ["北", "北東", "東", "南東", "南", "南西", "西", "北西"]

# ==========================================
# 💾 データの読み書き関数（多地点対応版）
# ==========================================
def load_all_data():
    """全地点のデータをまとめて読み込む"""
    # ファイルがなければ、全地点の初期値を作成
    if not os.path.exists(DATA_FILE):
        initial_data = {}
        for loc in LOCATIONS:
            initial_data[loc] = {"dir": "北", "speed": 0.0}
        # ファイルを生成しておく（初回のみ）
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(initial_data, f, ensure_ascii=False, indent=2)
        except: pass
        return initial_data
    
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        # エラー時は空の初期値を返す（アプリを落とさない）
        return {loc: {"dir": "北", "speed": 0.0} for loc in LOCATIONS}

def save_location_data(location, direction, speed):
    """特定の地点のデータだけを更新して保存する"""
    # まず現在の全データを読み込む
    current_all_data = load_all_data()
    
    # 指定された地点のデータを上書き
    current_all_data[location] = {"dir": direction, "speed": speed}
    
    # 全データをファイルに書き戻す
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current_all_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"保存エラー: {e}")

# ==========================================
# 📱 アプリのメイン処理
# ==========================================
st.set_page_config(page_title="鳥人間 風況マップ Ver.2", layout="centered")

# サイドバーでモード切替
mode = st.sidebar.radio("モード選択", ["コントローラー (地上クルー)", "モニター (全体表示)"])

# 常に最新の全データを読み込んでおく
all_data = load_all_data()

# ------------------------------------------
# 🗺️ モニター (全体表示) - 今は暫定的に表で表示
# ------------------------------------------
if mode == "モニター (全体表示)":
    st.markdown("## 🗺️ 全地点の風況一覧")
    st.info("（ステップ2でここに地図と矢印が表示されます）")
    
    # データをみやすい表形式に変換して表示
    display_data = []
    for loc in LOCATIONS:
        # もしデータ定義後に地点が増えてもエラーにならないようgetを使う
        loc_data = all_data.get(loc, {"dir": "-", "speed": 0.0})
        display_data.append({
            "計測地点": loc,
            "風向": loc_data["dir"],
            "風速 (m/s)": f"{loc_data['speed']:.1f}"
        })
    st.table(display_data)
    
    st.caption(f"最終更新: {time.strftime('%H:%M:%S')} / {REFRESH_RATE}秒ごとに自動更新")
    # 自動更新ロジック
    time.sleep(REFRESH_RATE)
    st.rerun()

# ------------------------------------------
# 🚩 コントローラー (地上クルー) - 地点選択式
# ------------------------------------------
else:
    st.markdown("## 🚩 データ入力")
    
    # 【重要】まず「どこにいるか」を選んでもらう
    selected_loc = st.selectbox("📍 あなたの場所を選択してください", LOCATIONS)
    
    st.write("---")
    st.markdown(f"### {selected_loc} の情報を入力中")
    
    # 選択された場所の現在のデータを取得（なければ初期値）
    target_data = all_data.get(selected_loc, {"dir": "北", "speed": 0.0})
    st.info(f"現在の値: 【 {target_data['dir']} / {target_data['speed']} m/s 】")

    # === ① 風向入力 ===
    st.write("風向を選択")
    c1, c2, c3, c4 = st.columns(4)
    for i, d in enumerate(DIRECTIONS):
        col = [c1, c2, c3, c4][i % 4]
        with col:
            # 選択中の風向を目立たせる
            btn_type = "primary" if target_data['dir'] == d else "secondary"
            if st.button(d, key=f"d_{i}", type=btn_type, use_container_width=True):
                # 選択された場所を指定して保存
                save_location_data(selected_loc, d, target_data['speed'])
                st.rerun()

    # === ② 風速入力 ===
    st.write("風速を変更 (m/s)")
    sc1, sc2, sc3 = st.columns([1, 2, 1])
    with sc1:
        if st.button("➖ 0.5", use_container_width=True):
            new_speed = max(0.0, target_data['speed'] - 0.5)
            save_location_data(selected_loc, target_data['dir'], new_speed)
            st.rerun()
    with sc2:
        st.markdown(f"<h2 style='text-align: center; margin: 0;'>{target_data['speed']:.1f}</h2>", unsafe_allow_html=True)
    with sc3:
        if st.button("➕ 0.5", use_container_width=True):
            new_speed = target_data['speed'] + 0.5
            save_location_data(selected_loc, target_data['dir'], new_speed)
            st.rerun()
            
    # プリセット
    st.write("一発入力")
    cols = st.columns(5)
    for i, p in enumerate([0.0, 1.0, 2.0, 3.0, 5.0]):
        with cols[i]:
            if st.button(str(p), key=f"p_{i}", use_container_width=True):
                save_location_data(selected_loc, target_data['dir'], p)
                st.rerun()
