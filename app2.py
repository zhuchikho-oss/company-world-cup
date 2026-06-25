import streamlit as st
import pandas as pd
import time
import gspread
from google.oauth2.service_account import Credentials

# ==================== 1. 初始化 Google Sheets 資料庫 ====================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1l7LZxRIv-WeApoVloQv0sLxFagDHclyeNJiRffTbB1E/edit?gid=0#gid=0"

@st.cache_resource
def get_spreadsheet_client():
    """建立並快取 Google Sheets 連接物件"""
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
    st.error("""❌ 無法連接到 Google Sheets。請檢查：
1. 網址是否正確
2. 是否已將服務帳號 Email 加入共用並設為「編輯者」""")
    st.exception(e)
    st.stop()

@st.cache_data(ttl=30)  # 🛡️ 升級至 30 秒安全快取，徹底杜絕 Google 429 流量限制
def read_sheet(sheet_name):
    """從 Google Sheet 讀取資料並進行嚴格型別校正"""
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
        
        # ⚡ 主動防禦：強制將可能混雜的欄位轉為純字串，全面封殺 PyArrow TypeError
        if sheet_name == "Matches":
            for col in ["score_home", "score_away", "first_goal_player", "status"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).replace("nan", "")
        return df
        
    except gspread.exceptions.APIError as google_error:
        st.error(f"❌ 讀取分頁【{sheet_name}】時，Google 伺服器返回了錯誤！")
        st.code(f"狀態代碼 (Status Code): {google_error.response.status_code}\n回應內文 (Response): {google_error.response.text}")
        st.stop()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"❌ 在你的 Google 試算表內，找不到名為【{sheet_name}】的分頁標籤！")
        st.stop()

def save_sheet(df, sheet_name):
    """將資料覆寫存回 Google Sheet，並立即清空快取"""
    try:
        worksheet = sh.worksheet(sheet_name)
        worksheet.clear()
        if not df.empty:
            df_to_save = df.fillna("")
            data_to_write = [df_to_save.columns.values.tolist()] + df_to_save.values.tolist()
            worksheet.update(values=data_to_write, range_name="A1")
        else:
            worksheet.update(values=[df.columns.values.tolist()], range_name="A1")
        st.cache_data.clear()  # 寫入成功時主動擦除記憶，確保下一秒讀到最新資料
    except gspread.exceptions.APIError as google_error:
        st.error(f"❌ 寫入分頁【{sheet_name}】時，Google 伺服器返回了錯誤！")
        st.code(f"狀態代碼 (Status Code): {google_error.response.status_code}\n回應內文 (Response): {google_error.response.text}")
        st.stop()

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
    df_ranking = df_users.sort_values(by="balance", ascending=False).reset_index(drop=True)
    
    if len(df_ranking) >= 3:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="🥇 榜首 (Top 1)", value=df_ranking.iloc[0]["name"], delta=f"{df_ranking.iloc[0]['balance']} pts")
        with col2:
            st.metric(label="🥈 亞軍 (Top 2)", value=df_ranking.iloc[1]["name"], delta=f"{df_ranking.iloc[1]['balance']} pts", delta_color="off")
        with col3:
            st.metric(label="🥉 季軍 (Top 3)", value=df_ranking.iloc[2]["name"], delta=f"{df_ranking.iloc[2]['balance']} pts", delta_color="off")
    
    st.divider()
    df_ranking.index = df_ranking.index + 1
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
                    
                    chosen_play_type = selected_odd_str.split("] ")[0].replace("[", "")
                    chosen_selection = selected_odd_str.split("] ")[1].split(" @")[0]
                    chosen_odd = match_odds[(match_odds["play_type"] == chosen_play_type) & (match_odds["selection"] == chosen_selection)].iloc[0]
                    o_id = chosen_odd["odd_id"]
                    
                    stake = st.number_input("💵 輸入下注積分：", min_value=1.0, max_value=float(user_row['balance']), value=100.0, step=10.0)
                    
                    if st.button("🚀 確認下單 (單注)", type="primary"):
                        df_users.loc[df_users["user_id"] == user_row["user_id"], "balance"] -= stake
                        save_sheet(df_users, "Users")
                        
                        new_bet_id = len(df_bets) + 1
                        new_bet = pd.DataFrame([{"bet_id": new_bet_id, "user_id": user_row["user_id"], "bet_mode": "單注", "stake": stake, "status": "未開獎", "win_amount": 0.0}])
                        df_bets = pd.concat([df_bets, new_bet], ignore_index=True)
                        save_sheet(df_bets, "Bets")
                        
                        new_detail = pd.DataFrame([{"detail_id": len(df_details)+1, "bet_id": new_bet_id, "match_id": m_id, "odd_id": o_id, "selection": chosen_odd["selection"], "odds_value": chosen_odd["odds_value"], "status": "未開獎"}])
                        df_details = pd.concat([df_details, new_detail], ignore_index=True)
                        save_sheet(df_details, "BetDetails")
                        
                        st.toast(f"投注成功！已扣除 {stake} 積分。", icon="✅")
                        time.sleep(1)
                        st.rerun()
                        
        else:
            st.markdown("#### 🔗 串關組合 (Parlay Builder)")
            st.caption("請勾選你想串的比賽，每場比賽只能選一項。")
            selected_odds_ids = []
            
            with st.container(border=True):
                for idx, row in open_matches.iterrows():
                    m_id = row['match_id']
                    match_odds = df_odds[df_odds["match_id"] == m_id]
                    if not match_odds.empty:
                        odds_options = ["不選此場"] + match_odds.apply(lambda r: f"[{r['play_type']}] {r['selection']} @ {r['odds_value']}", axis=1).tolist()
                        choice = st.selectbox(f"⚽ {row['home_team']} VS {row['away_team']}", odds_options, key=f"parlay_{m_id}")
                        if choice != "不選此場":
                            chosen_play_type = choice.split("] ")[0].replace("[", "")
                            chosen_selection = choice.split("] ")[1].split(" @")[0]
                            chosen_odd = match_odds[(match_odds["play_type"] == chosen_play_type) & (match_odds["selection"] == chosen_selection)].iloc[0]
                            selected_odds_ids.append((m_id, chosen_odd["odd_id"]))
            
            if len(selected_odds_ids) < 2:
                st.warning("⚠️ 過關模式至少需要選擇 2 場不同的賽事！")
            else:
                total_odds = 1.0
                for _, o_id in selected_odds_ids:
                    total_odds *= float(df_odds[df_odds["odd_id"] == o_id].iloc[0]["odds_value"])
                
                st.success(f"📊 當前組合: **{len(selected_odds_ids)} 串 1** ｜ 預計總賠率: **{total_odds:.2f}**")
                stake = st.number_input("💵 輸入過關總下注積分：", min_value=1.0, max_value=float(user_row['balance']), value=100.0, step=10.0)
                
                if st.button("🚀 確認下單 (過關)", type="primary"):
                    df_users.loc[df_users["user_id"] == user_row["user_id"], "balance"] -= stake
                    save_sheet(df_users, "Users")
                    
                    new_bet_id = len(df_bets) + 1
                    new_bet = pd.DataFrame([{"bet_id": new_bet_id, "user_id": user_row["user_id"], "bet_mode": "過關", "stake": stake, "status": "未開獎", "win_amount": 0.0}])
                    df_bets = pd.concat([df_bets, new_bet], ignore_index=True)
                    save_sheet(df_bets, "Bets")
                    
                    for m_id, o_id in selected_odds_ids:
                        chosen_odd = df_odds[df_odds["odd_id"] == o_id].iloc[0]
                        new_detail = pd.DataFrame([{"detail_id": len(df_details)+1, "bet_id": new_bet_id, "match_id": m_id, "odd_id": o_id, "selection": chosen_odd["selection"], "odds_value": chosen_odd["odds_value"], "status": "未開獎"}])
                        df_details = pd.concat([df_details, new_detail], ignore_index=True)
                    save_sheet(df_details, "BetDetails")
                    
                    st.toast(f"過關組合投注成功！扣除 {stake} 積分。", icon="🎉")
                    time.sleep(1)
                    st.rerun()

# ==================== 3. 賽事與賠率管理 (Admin) ====================
with tabs[2]:
    st.markdown("### 🛠️ 賽事及自定義賠率後台")
    col_match, col_odd = st.columns(2)
    with col_match:
        with st.container(border=True):
            st.markdown("#### ➕ 建立新賽事")
            h_team = st.text_input("🏠 主隊名稱", value="阿根廷")
            a_team = st.text_input("✈️ 客隊名稱", value="葡萄牙")
            if st.button("創建賽事", use_container_width=True):
                new_m_id = len(df_matches) + 1
                new_m = pd.DataFrame([{"match_id": new_m_id, "home_team": h_team, "away_team": a_team, "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""}])
                df_matches = pd.concat([df_matches, new_m], ignore_index=True)
                save_sheet(df_matches, "Matches")
                st.toast(f"賽事建立成功！", icon="✅")
                time.sleep(1)
                st.rerun()
            
    with col_odd:
        with st.container(border=True):
            st.markdown("#### ⚙️ 為賽事配置賠率")
            if df_matches.empty:
                st.info("請先創建賽事")
            else:
                match_list = df_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (ID:{r['match_id']})", axis=1).tolist()
                sel_match = st.selectbox("選擇要配置的賽事", match_list)
                target_m_id = int(sel_match.split("ID:")[-1].replace(")", ""))
                
                p_type = st.selectbox("玩法類目", ["主客和", "讓球主客和", "讓球", "波膽", "首名入球"])
                selection_name = st.text_input("選項名稱 (例: '主勝', '2:1', '美斯')", value="主勝")
                odds_val = st.number_input("設定賠率", min_value=1.01, value=2.15, step=0.01)
                
                if st.button("添加賠率項目", use_container_width=True):
                    new_o_id = len(df_odds) + 1
                    new_odd = pd.DataFrame([{"odd_id": new_o_id, "match_id": target_m_id, "play_type": p_type, "selection": selection_name, "odds_value": odds_val}])
                    df_odds = pd.concat([df_odds, new_odd], ignore_index=True)
                    save_sheet(df_odds, "Odds")
                    st.toast("賠率添加成功！", icon="✅")
                    time.sleep(1)
                    st.rerun()
                    
    with st.expander("🔍 預覽已錄入的賽事與賠率資料庫", expanded=False):
        st.markdown("**賽事總覽**")
        st.dataframe(df_matches, use_container_width=True, hide_index=True)
        st.markdown("**賠率配置總覽**")
        st.dataframe(df_odds, use_container_width=True, hide_index=True)

# ==================== TAB 4: 賽果結算後台 (Admin) ====================
with tabs[3]:
    st.markdown("### 🏁 賽果錄入與自動結算系統")
    if df_matches.empty:
         st.success("✅ 目前尚未創建任何賽事。")
    else:
        unsettled_matches = df_matches[df_matches["status"] == "未開賽"]
        
        if unsettled_matches.empty:
            st.success("✅ 所有賽事均已結算完畢！目前沒有待結算的比賽。")
        else:
            with st.container(border=True):
                sel_unsettled = st.selectbox("📌 選擇要結算的比賽：", unsettled_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (ID:{r['match_id']})", axis=1))
                settle_m_id = int(sel_unsettled.split("ID:")[-1].replace(")", ""))
                
                st.warning("""⚠️ **核心結算邏輯**：請勾選這場比賽中**所有被判定為贏（中獎）**的選項。未勾選的將一律判定為輸。""")
                
                match_all_odds = df_odds[df_odds["match_id"] == settle_m_id]
                
                if match_all_odds.empty:
                    st.error("❌ 此比賽尚未配置任何賠率，無法結算！")
                else:
                    st.markdown("#### 1. 勾選獲勝的賠率選項")
                    winning_odds_ids = []
                    
                    odds_cols = st.columns(2)
                    for idx, row in match_all_odds.iterrows():
                        col_target = odds_cols[idx % 2]
                        with col_target:
                            is_win = st.checkbox(f"[{row['play_type']}] {row['selection']}", key=f"win_{row['odd_id']}")
                            if is_win:
                                winning_odds_ids.append(row['odd_id'])
                    
                    st.markdown("#### 2. 錄入最終賽果資料庫")
                    res_col1, res_col2, res_col3 = st.columns(3)
                    with res_col1: sc_home = st.number_input("🏠 主隊入球數", min_value=0, value=2)
                    with res_col2: sc_away = st.number_input("✈️ 客隊入球數", min_value=0, value=1)
                    with res_col3: f_goal = st.text_input("⚽ 首名入球員 (選填)", value="")
                    
                    if st.button("📊 確認賽果，一鍵自動派彩！", type="primary", use_container_width=True):
                        with st.spinner('系統結算中，同時將資料同步至 Google Sheets，請稍候...'):
                            
                            # 🚀 🔥 終極型別防護：明確使用 str() 將所有數據轉型為字串，徹底滿足 Pandas PyArrow 檢查
                            df_matches.loc[df_matches["match_id"] == settle_m_id, "status"] = "已結算"
                            df_matches.loc[df_matches["match_id"] == settle_m_id, "score_home"] = str(sc_home)
                            df_matches.loc[df_matches["match_id"] == settle_m_id, "score_away"] = str(sc_away)
                            df_matches.loc[df_matches["match_id"] == settle_m_id, "first_goal_player"] = str(f_goal)
                            save_sheet(df_matches, "Matches")
                            
                            if not df_details.empty:
                                df_details.loc[(df_details["match_id"] == settle_m_id) & (df_details["odd_id"].isin(winning_odds_ids)), "status"] = "贏"
                                df_details.loc[(df_details["match_id"] == settle_m_id) & (~df_details["odd_id"].isin(winning_odds_ids)), "status"] = "輸"
                                save_sheet(df_details, "BetDetails")
                            
                            if not df_bets.empty:
                                open_bets = df_bets[df_bets["status"] == "未開獎"]
                                
                                for idx, bet in open_bets.iterrows():
                                    b_id = bet["bet_id"]
                                    bet_details = df_details[df_details["bet_id"] == b_id]
                                    
                                    if settle_m_id in bet_details["match_id"].values:
                                        all_statuses = bet_details["status"].tolist()
                                        
                                        if "輸" in all_statuses:
                                            df_bets.loc[df_bets["bet_id"] == b_id, "status"] = "輸"
                                            df_bets.loc[df_bets["bet_id"] == b_id, "win_amount"] = 0.0
                                        elif "未開獎" not in all_statuses:
                                            df_bets.loc[df_bets["bet_id"] == b_id, "status"] = "贏"
                                            total_odds = 1.0
                                            for _, detail in bet_details.iterrows():
                                                total_odds *= float(detail["odds_value"])
                                            
                                            win_amt = round(float(bet["stake"]) * total_odds, 2)
                                            df_bets.loc[df_bets["bet_id"] == b_id, "win_amount"] = win_amt
                                            
                                            u_id = bet["user_id"]
                                            df_users.loc[df_users["user_id"] == u_id, "balance"] += win_amt
                                
                                save_sheet(df_bets, "Bets")
                                save_sheet(df_users, "Users")
                            
                            time.sleep(1)
                            
                        st.success("""🎉 本場賽事結算完成！贏家的虛擬積分已自動派發，排行榜與 Google Sheets 已實時刷新。""")
                        time.sleep(1.5)
                        st.rerun()


