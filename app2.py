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
        st.error(f"❌ 讀取【{sheet_name}】失敗，可能遭遇流量限制，請等待 10 秒後重整網頁。")
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

# ==================== 2. Streamlit 頁面全局設定 (手機高清晰版) ====================
st.set_page_config(page_title="2026世界盃競猜", page_icon="🏆", layout="centered") # 改為 centered 讓手機置中更好看

st.markdown("""
    <style>
    /* 強制深色字體與清晰背景 */
    .stApp { background-color: #ffffff; }
    
    /* 頂部 Banner 優化：白底深字，高對比 */
    .main-banner {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 12px;
        border: 2px solid #1e3a8a;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
    }
    /* 字體調小一點適應手機，但加粗加深 */
    .main-title { font-size: 1.6rem; font-weight: 900; color: #1e3a8a; margin-bottom: 5px; } 
    .sub-title { font-size: 1rem; color: #0f172a; font-weight: 700; }
    
    /* 手機版賽程卡片設計 */
    .bracket-match {
        background-color: #f8fafc;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #cbd5e1;
        margin-bottom: 12px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .bracket-team { font-weight: 800; color: #0f172a; font-size: 1.2rem; } /* 極深色，大字體 */
    .bracket-vs { color: #b91c1c; font-size: 1rem; margin: 5px 0; font-weight: 900; }
    .bracket-title { font-size: 1.2rem; font-weight: 900; color: #1e3a8a; margin-bottom: 10px; border-bottom: 2px solid #1e3a8a; padding-bottom: 5px; }
    
    /* 強制所有 Markdown 標題為深色 */
    h1, h2, h3, h4 { color: #0f172a !important; font-weight: 800 !important; }
    </style>
    
    <div class="main-banner">
        <div class="main-title">🏆 2026 世界盃競猜</div>
        <div class="sub-title">32強淘汰賽・內部手機投注版</div>
    </div>
    """, unsafe_allow_html=True)

# 縮短 Tabs 名稱，避免手機螢幕擠不下
tabs = st.tabs(["📊 排名", "📅 賽程", "🎲 投注", "⚙️ 管理", "🏁 結算"])

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
        # 手機上垂直堆疊更能看清楚
        st.success(f"🥇 榜首：**{df_ranking.iloc[0]['name']}** ({df_ranking.iloc[0]['balance']:.1f} pts)")
        st.info(f"🥈 亞軍：**{df_ranking.iloc[1]['name']}** ({df_ranking.iloc[1]['balance']:.1f} pts)")
        st.warning(f"🥉 季軍：**{df_ranking.iloc[2]['name']}** ({df_ranking.iloc[2]['balance']:.1f} pts)")
    
    df_ranking.index = df_ranking.index + 1
    df_ranking = df_ranking.rename(columns={"name": "同事姓名", "balance": "積分餘額"})
    st.dataframe(df_ranking[["同事姓名", "積分餘額"]], use_container_width=True)

# ==================== TAB 2: 32強對陣賽程圖 (手機直向排版) ====================
with tabs[1]:
    st.markdown("### 📅 32 強對陣名單")
    st.info("💡 賽程已優化為手機滑動模式，點擊下方區塊展開查看對陣。")
    
    with st.expander("🔥 展開：上半區賽事 (左半部)", expanded=True):
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇩🇪 德國</div><div class="bracket-vs">VS</div><div class="bracket-team">🇯🇵 日本</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="bracket-match"><div class="bracket-team">🏴󠁧󠁢󠁥󠁮󠁧󠁿 英格蘭</div><div class="bracket-vs">VS</div><div class="bracket-team">🇸🇳 塞內加爾</div></div>', unsafe_allow_html=True)

    with st.expander("🔥 展開：上半區賽事 (右半部)", expanded=False):
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇫🇷 法國</div><div class="bracket-vs">VS</div><div class="bracket-team">🇺🇸 美國</div></div>',

