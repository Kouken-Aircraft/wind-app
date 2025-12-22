import streamlit as st
import json
import os
import time

# ==========================================
# ⚙️ 設定・ファイルパスの固定（ここが重要）
# ==========================================
# この wind_app.py がある場所を基準にする
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "wind_data.json")

# パイロット画面の更新頻度（秒）
REFRESH_RATE = 2

# ==========================================
# 💾 データの読み書き関数
# ==========================================
def load_data():
    # ファイルがない場合は初期値を作成して返す
    if not os.path.exists(DATA_FILE):
        default_data = {"dir": "北", "speed": 0.0}
        save_data("北", 0.0) # ファイルを生成しておく
        return default_data
    
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        # 読み込みに失敗したら初期値を返す（アプリを落とさないため）
        return {"dir": "北", "speed": 0.0}

def save_data(direction, speed):
    data = {"dir": direction, "speed": speed}
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except Exception as e:
        st.error(f"保存エラー: {e}")

# ==========================================
# 📱 アプリのメイン処理
# ==========================================
st.set_page_config(page_title="鳥人間 風況モニター", layout="centered")

# サイドバーでモード切替
mode = st.sidebar.radio("モード選択", ["コントローラー (地上クルー)", "モニター (パイロット)"])

# 常に最新データを読み込む
current_data = load_data()

# ------------------------------------------
# ✈️ パイロット用モニター画面
# ------------------------------------------
if mode == "モニター (パイロット)":
    st.markdown("## ✈️ パイロット用モニター")
    
    # 視認性重視のデザイン (HTML/CSS埋め込み)
    st.markdown(
        f"""
        <div style="text-align: center; border: 4px solid #2196F3; padding: 20px; border-radius: 15px; background-color: #0e1117;">
            <p style="font-size: 20px; color: #ccc; margin: 0;">WIND DIR (風向)</p>
            <h1 style="font-size: 80px; margin: 0; color: #FFeb3b; font-weight: bold;">{current_data['dir']}</h1>
            <hr style="border-color: #444; margin: 20px 0;">
            <p style="font-size: 20px; color: #ccc; margin: 0;">WIND SPEED (風速)</p>
            <h1 style="font-size: 100px; margin: 0; color: #fff; font-weight: bold;">{current_data['speed']:.1f} <span style="font-size:40px">m/s</span></h1>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    st.caption(f"最終更新: {time.strftime('%H:%M:%S')}")
    
    # 自動更新ロジック (2秒待ってから再実行)
    time.sleep(REFRESH_RATE)
    st.rerun()

# ------------------------------------------
# 🚩 地上クルー用コントローラー画面
# ------------------------------------------
else:
    st.markdown("## 🚩 風況入力")
    st.info("ボタンを押すと即座にパイロット画面へ反映されます")

    # 現在値の確認用表示
    st.markdown(f"**現在の送信データ:** {current_data['dir']} / {current_data['speed']} m/s")

    st.write("---")
    
    # === ① 風向入力 ===
    st.subheader("① 風向")
    col1, col2, col3, col4 = st.columns(4)
    directions = ["北", "北東", "東", "南東", "南", "南西", "西", "北西"]
    
    for i, d in enumerate(directions):
        # 4つずつ列を割り振る
        if i < 4: col = [col1, col2, col3, col4][i]
        else: col = [col1, col2, col3, col4][i-4]
        
        with col:
            # 現在選択されている風向を目立たせる（primary色にする）
            btn_type = "primary" if current_data['dir'] == d else "secondary"
            
            if st.button(d, key=f"dir_{i}", type=btn_type, use_container_width=True):
                save_data(d, current_data['speed'])
                st.rerun()

    st.write("---")

    # === ② 風速入力 ===
    st.subheader("② 風速 (m/s)")
    
    # 増減ボタン
    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("➖ 0.5減らす", use_container_width=True):
            new_speed = max(0.0, current_data['speed'] - 0.5)
            save_data(current_data['dir'], new_speed)
            st.rerun()
    with c3:
        if st.button("➕ 0.5増やす", use_container_width=True):
            new_speed = current_data['speed'] + 0.5
            save_data(current_data['dir'], new_speed)
            st.rerun()
    
    # 中央に大きく表示
    with c2:
        st.markdown(f"<h2 style='text-align: center; margin: 0;'>{current_data['speed']:.1f} m/s</h2>", unsafe_allow_html=True)

    # プリセットボタン（よくある数字を一発入力）
    st.write("一発入力")
    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
    presets = [0.0, 1.0, 2.0, 3.0, 5.0]
    
    for idx, p in enumerate(presets):
        col = [sc1, sc2, sc3, sc4, sc5][idx]
        with col:
            if st.button(str(p), key=f"pre_{p}", use_container_width=True):
                save_data(current_data['dir'], p)
                st.rerun()