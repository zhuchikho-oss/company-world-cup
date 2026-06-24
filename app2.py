import streamlit as st
import pandas as pd
import time
import gspread
from google.oauth2.service_account import Credentials

# ==================== 1. 初始化 Google Sheets 資料庫 ====================
# ⚠️ 請務必將下方的網址替換成你自己的 Google 試算表網址！
SHEET_URL = "請把你的_Google_Sheet_網址貼在這裡"

@st.cache_resource
def get_gspread_client():
    """連接 Google Sheets 的授權驗證"""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    # 從 Streamlit Secrets 讀取金鑰保險箱
    skey = dict(st.secrets["gcp_service_account"])
    credentials = Credentials.from_service_account_info(skey, scopes=scopes)
    client = gspread.authorize(credentials)
    return client

# 建立雲端連接
try:
    gc = get_gspread_client()
    sh = gc.open_by_url(SHEET_URL)
except Exception as e:
    st.error("❌ 無法連接到 Google Sheets。請檢查：\n1. 網址是否正確\n2. 是否已將服務帳號 Email 加入共用並設為「編輯者」")
    st.stop()

def read_sheet(sheet_name):
    """從 Google Sheet 讀取資料並轉換為 DataFrame"""
    worksheet = sh.worksheet(sheet_name)
    data = worksheet.get_all_records()
    if not data:
        # 如果表格是空的，自動定義基礎欄位防止報錯
        columns_map = {
            "Users": ["user_id", "name", "balance"],
            "Matches": ["match_id", "home_team", "away_team", "status", "score_home", "score_away", "first_goal_player"],
            "Odds": ["odd_id", "match_id", "play_type", "selection", "odds_value"],
            "Bets": ["bet_id", "user_id", "bet_mode", "stake", "status", "win_amount"],
            "BetDetails": ["detail_id", "bet_id", "match_id", "odd_id", "selection", "odds_value", "status"]
        }
        return pd.DataFrame(columns=columns_map.get(sheet_name, []))
    return pd.DataFrame(data)

def save_sheet(df, sheet_name):
    """將資料覆寫存回 Google Sheet"""
    worksheet = sh.worksheet(sheet_name)
    worksheet.clear() # 先清空舊資料
    if not df.empty:
        # 避免 NaN 空值導致 JSON 序列化失敗，將空值替換為空字串
        df_to_save = df.fillna("")
        data_to_write = [df_to_save.columns.values.tolist()] + df_to_save.values.tolist()
        worksheet.update(values=data_to_write, range_name="A1")
    else:
        # 如果是空的，至少保留標題列
        worksheet.update(values=[df.columns.values.tolist()], range_name="A1")

# ==================== 2. Streamlit 頁面全局設定 ====================
st.set_page_config(page_title="企業世界盃虛擬競猜", page_icon="🏆", layout="wide")

st.markdown("""
    <style>
    .main-header {font-size: 2.5rem; font-weight: 700; color: #1E3A8A; margin-bottom: 0px;}
    .sub-header {font-size: 1.2rem; color: #6B7280; margin-bottom: 30px;}
    </style>
    <div class="main-header">🏆 企業世界盃虛擬競猜平台</div>
    <div class="sub-header">內部專屬娛樂・資產排名結算系統 (Cloud Version)</div>
    """, unsafe_allow_html=True)

tabs = st.tabs(["📊 資產排行榜", "🎲 賽事投注中心", "⚙️ 賽事與賠率管理 (Admin)", "🧾 賽果結算後台 (Admin)"])

# ==================== 3. 提取當前雲端數據 ====================
df_users = read_sheet("Users")

# 如果雲端 Users 表格完全空白，自動初始化 10 個同事帳號
if df_users.empty:
    df_users = pd.DataFrame({
        "user_id": range(1, 11),
        "name": [f"同事 {i}" for i in range(1, 11)],
        "balance": [2000.0] * 10
    })
    save_sheet(df_users, "Users")

df_matches = read_sheet("Matches")
df_odds = read_sheet("Odds")
df_bets = read_sheet("Bets")
df_details = read_sheet("BetDetails")

# ==================== TAB 1: 資產排行榜 ====================
with tabs[0]:
    st.markdown("### 📈 內部財富龍虎榜 (Wealth Ranking)")
    
    # 按餘額降序排列
    df_ranking = df_users.sort_values(by="balance", ascending=False).reset_index(drop=True)
    
    if len(df_ranking) >= 3:
        # 高階展示：前三名使用 Metric 卡片
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="🥇 榜首 (Top 1)", value=df_ranking.iloc[0]["name"], delta=f"{df_ranking.iloc[0]['balance']} pts")
        with col2:
            st.metric(label="🥈 亞軍 (Top 2)", value=df_ranking.iloc[1]["name"], delta=f"{df_ranking.iloc[1]['balance']} pts", delta_color="off")
        with col3:
            st.metric(label="🥉 季軍 (Top 3)", value=df_ranking.iloc[2]["name"], delta=f"{df_ranking.iloc[2]['balance']} pts", delta_color="off")
    
    st.divider()
    
    # 完整排行榜
    df_ranking.index = df_ranking.index + 1  # 排名從1開始
    df_ranking = df_ranking.rename(columns={"name": "同事姓名", "balance": "當前可用積分 (pts)"})
    st.dataframe(df_ranking[["同事姓名", "當前可用積分 (pts)"]], use_container_width=True)

# ==================== TAB 2: 賽事投注中心 ====================
with tabs[1]:
    st.markdown("### 📱 虛擬投注中心")
    
    if df_matches.empty or df_matches[df_matches['status'] == '未開賽'].empty:
        st.info("💡 目前沒有正在開盤的賽事，請聯絡管理員添加比賽！")
    else:
        with st.container(border=True):
            col_user, col_bal = st.columns([2, 1])
            with col_user:
                active_user = st.selectbox("👤 請選擇你的身分（帳號）：", df_users["name"].tolist())
                user_row = df_users[df_users["name"] == active_user].iloc[0]
            with col_bal:
                st.metric(label="💰 你的可用積分餘額", value=f"{user_row['balance']} pts")
        
        st.divider()
        bet_mode = st.radio("🎲 選擇投注模式：", ["單注 (Single)", "過關 (Parlay)"], horizontal=True)
        open_matches = df_matches[df_matches['status'] == '未開賽']
        
        if bet_mode == "單注 (Single)":
            with st.container(border=True):
                selected_match = st.selectbox("⚽ 選擇賽事：", open_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (賽事ID:{r['match_id']})", axis=1))
                m_id = int(selected_match.split("賽事ID:")[-1].replace(")", ""))
                
                match_odds = df_odds[df_odds["match_id"] == m_id]
                if match_odds.empty:
                    st.warning("⚠️ 管理員尚未為這場比賽配置賠率！")
                else:
                    odds_options = match_odds.apply(lambda r: f"[{r['play_type']}] {r['selection']} @ 賠率 {r['odds_value']}", axis=1).tolist()
                    selected_odd_str = st.selectbox("🎯 選擇投注項目：", odds_options)
                    
                    # 反查 ID
                    chosen_play_type = selected_odd_str.split("] ")[0].replace("[", "")
                    chosen_selection = selected_odd_str.split("] ")[1].split(" @")[0]
                    chosen_odd = match_odds[(match_odds["play_type"] == chosen_play_type) & (match_odds["selection"] == chosen_selection)].iloc[0]
                    o_id = chosen_odd["odd_id"]
                    
                    stake = st.number



