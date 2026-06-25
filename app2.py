import streamlit as st
import pandas as pd
import time
import gspread
from google.oauth2.service_account import Credentials

# ==================== 1. 初始化 Google Sheets 資料庫 ====================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1l7LZxRIv-WeApoVloQv0sLxFagDHclyeNJiRffTbB1E/edit?gid=0#gid=0"

@st.cache_resource
def get_spreadsheet_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    skey = dict(st.secrets["gcp_service_account"])
    credentials = Credentials.from_service_account_info(skey, scopes=scopes)
    client = gspread.authorize(credentials)
    return client.open_by_url(SHEET_URL)

try:
    sh = get_spreadsheet_client()
except Exception as e:
    st.error("❌ 無法連接到 Google Sheets。請檢查網址與服務帳號權限。")
    st.stop()

@st.cache_data(ttl=15)
def read_sheet(sheet_name):
    try:
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        
        columns_map = {
            "Users": ["user_id", "name", "balance"],
            "Matches": ["match_id", "home_team", "away_team", "status", "score_home", "score_away", "first_goal_player"],
            "Odds": ["odd_id", "match_id", "play_type", "selection", "odds_value"],
            "Bets": ["bet_id", "user_id", "bet_mode", "stake", "status", "win_amount"],
            "BetDetails": ["detail_id", "bet_id", "match_id", "odd_id", "selection", "odds_value", "status"]
        }
        
        if not data:
            return pd.DataFrame(columns=columns_map.get(sheet_name, []))
            
        df = pd.DataFrame(data)
        
        if sheet_name == "Matches":
            for col in ["score_home", "score_away", "first_goal_player", "status"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).replace("nan", "")
        return df
    except Exception as google_error:
        st.error(f"❌ 讀取【{sheet_name}】失敗，請稍候重整網頁。")
        st.stop()

def save_sheet(df, sheet_name):
    try:
        worksheet = sh.worksheet(sheet_name)
        worksheet.clear()
        if not df.empty:
            df_to_save = df.fillna("")
            data_to_write = [df_to_save.columns.values.tolist()] + df_to_save.values.tolist()
            worksheet.update(values=data_to_write, range_name="A1")
        else:
            worksheet.update(values=[df.columns.values.tolist()], range_name="A1")
        st.cache_data.clear()
    except Exception as e:
        st.error(f"❌ 寫入【{sheet_name}】失敗。")
        st.stop()

# ==================== 2. Streamlit 頁面全局設定 (極致高對比深字版) ====================
st.set_page_config(page_title="2026世界盃競猜", page_icon="🏆", layout="centered")

st.markdown("""
    <style>
    /* 強制全局背景為純白色，字體全部為純黑色，字體加粗 */
    .stApp { 
        background-color: #ffffff !important; 
    }
    
    /* 所有文字與標籤強制黑字 */
    div, p, label, span, li {
        color: #000000 !important;
        font-weight: 700 !important;
    }
    
    /* 網頁頂部 Banner 優化：粗黑外框，純黑大字 */
    .main-banner {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 8px;
        border: 3px solid #000000;
        text-align: center;
        margin-bottom: 20px;
    }
    .main-title { font-size: 1.8rem; font-weight: 900; color: #000000; margin-bottom: 5px; } 
    .sub-title { font-size: 1.1rem; color: #000000; font-weight: 800; }
    
    /* 手機版賽程黑框卡片設計 */
    .bracket-match {
        background-color: #ffffff;
        padding: 16px;
        border-radius: 8px;
        border: 2px solid #000000;
        margin-bottom: 14px;
        text-align: center;
    }
    .bracket-team { font-weight: 900; color: #000000; font-size: 1.3rem; } 
    .bracket-vs { color: #d60000; font-size: 1.1rem; margin: 6px 0; font-weight: 900; }
    
    /* 強制所有 Streamlit 自帶標題為極深藍色與極粗體 */
    h1, h2, h3, h4 { color: #0b1d3a !important; font-weight: 900 !important; }
    
    /* 讓 Streamlit 元件按鈕更黑更明顯 */
    .stButton>button {
        border: 2px solid #000000 !important;
        color: #000000 !important;
        font-weight: 900 !important;
        background-color: #ffffff !important;
    }
    </style>
    
    <div class="main-banner">
        <div class="main-title">🏆 2026 世界盃 32強競猜</div>
        <div class="sub-title">【內部專屬手機高清晰版】</div>
    </div>
    """, unsafe_allow_html=True)

# 簡短標籤，防手機擠壓變形
tabs = st.tabs(["📊 財富排行", "📅 32強賽程", "🎲 快速投注", "⚙️ 管理後台", "🏁 完賽結算"])

# ==================== 3. 提取雲端數據 ====================
df_users = read_sheet("Users")
if df_users.empty:
    df_users = pd.DataFrame({"user_id": range(1, 11), "name": [f"同事 {i}" for i in range(1, 11)], "balance": [2000.0] * 10})
    save_sheet(df_users, "Users")

df_matches = read_sheet("Matches")
df_odds = read_sheet("Odds")
df_bets = read_sheet("Bets")
df_details = read_sheet("BetDetails")

# ==================== TAB 1: 資產排行榜 ====================
with tabs[0]:
    st.markdown("### 📈 財富龍虎榜")
    df_ranking = df_users.sort_values(by="balance", ascending=False).reset_index(drop=True)
    
    if len(df_ranking) >= 3:
        st.markdown(f"#### 🥇 榜首：{df_ranking.iloc[0]['name']} — **{df_ranking.iloc[0]['balance']:.1f} pts**")
        st.markdown(f"#### 🥈 亞軍：{df_ranking.iloc[1]['name']} — **{df_ranking.iloc[1]['balance']:.1f} pts**")
        st.markdown(f"#### 🥉 季軍：{df_ranking.iloc[2]['name']} — **{df_ranking.iloc[2]['balance']:.1f} pts**")
    
    st.markdown("---")
    df_ranking.index = df_ranking.index + 1
    df_ranking = df_ranking.rename(columns={"name": "同事姓名", "balance": "積分餘額"})
    st.dataframe(df_ranking[["同事姓名", "積分餘額"]], use_container_width=True)

# ==================== TAB 2: 32強對陣賽程圖 (高對比粗黑框設計) ====================
with tabs[1]:
    st.markdown("### 📅 32 強對陣樹狀表")
    st.markdown("ℹ️ **提示：請點擊下方大黑字區塊，即可展開查看對手。**")
    
    with st.expander("▶️ 點擊展開：上半區賽事 (A組-D組對陣)", expanded=True):
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇩🇪 德國</div><div class="bracket-vs">VS</div><div class="bracket-team">🇯🇵 日本</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="bracket-match"><div class="bracket-team">🏴󠁧󠁢󠁥󠁮󠁧󠁿 英格蘭</div><div class="bracket-vs">VS</div><div class="bracket-team">🇸🇳 塞內加爾</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇫🇷 法國</div><div class="bracket-vs">VS</div><div class="bracket-team">🇺🇸 美國</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇦研廷</div><div class="bracket-vs">VS</div><div class="bracket-team">🇦🇺 澳洲</div></div>', unsafe_allow_html=True)

    with st.expander("▶️ 點擊展開：下半區賽事 (E組-H組對陣)", expanded=False):
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇪🇸 西班牙</div><div class="bracket-vs">VS</div><div class="bracket-team">摩洛哥 🇲🇦</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇵🇹 葡萄牙</div><div class="bracket-vs">VS</div><div class="bracket-team">瑞士 🇨🇭</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇧🇷 巴西</div><div class="bracket-vs">VS</div><div class="bracket-team">南韓 🇰🇷</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇳🇱 荷蘭</div><div class="bracket-vs">VS</div><div class="bracket-team">克羅埃西亞 🇭🇷</div></div>', unsafe_allow_html=True)

# ==================== TAB 3: 賽事投注中心 ====================
with tabs[2]:
    st.markdown("### 🎲 手機快速投注")
    open_matches = df_matches[df_matches['status'] == '未開賽']
    
    if df_matches.empty or open_matches.empty:
        st.markdown("#### 📭 目前暫時沒有開盤中的賽事。")
    else:
        with st.container(border=True):
            active_user = st.selectbox("👤 請選擇你的名字（身分）：", df_users["name"].tolist())
            user_row = df_users[df_users["name"] == active_user].iloc[0]
            st.markdown(f"### 💰 你的可用積分：**{user_row['balance']:.1f} pts**")
        
        st.markdown("---")
        bet_mode = st.radio("🎯 選擇下注類型：", ["單注下注", "過關串關"], horizontal=True)
        
        if bet_mode == "單注下注":
            with st.container(border=True):
                selected_match = st.selectbox("⚽ 選擇比賽場次：", open_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (ID:{r['match_id']})", axis=1))
                m_id = int(selected_match.split("ID:")[-1].replace(")", ""))
                
                match_odds = df_odds[df_odds["match_id"] == m_id]
                if match_odds.empty:
                    st.markdown("⚠️ **這場比賽管理員還沒設定賠率！**")
                else:
                    odds_options = match_odds.apply(lambda r: f"
