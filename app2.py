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
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇫🇷 法國</div><div class="bracket-vs">VS</div><div class="bracket-team">🇺🇸 美國</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇦🇷 阿根廷</div><div class="bracket-vs">VS</div><div class="bracket-team">🇦🇺 澳洲</div></div>', unsafe_allow_html=True)

    with st.expander("❄️ 展開：下半區賽事 (左半部)", expanded=False):
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇪🇸 西班牙</div><div class="bracket-vs">VS</div><div class="bracket-team">摩洛哥 🇲🇦</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇵🇹 葡萄牙</div><div class="bracket-vs">VS</div><div class="bracket-team">瑞士 🇨🇭</div></div>', unsafe_allow_html=True)

    with st.expander("❄️ 展開：下半區賽事 (右半部)", expanded=False):
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇧🇷 巴西</div><div class="bracket-vs">VS</div><div class="bracket-team">南韓 🇰🇷</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇳🇱 荷蘭</div><div class="bracket-vs">VS</div><div class="bracket-team">克羅埃西亞 🇭🇷</div></div>', unsafe_allow_html=True)

# ==================== TAB 3: 賽事投注中心 (大按鈕配置) ====================
with tabs[2]:
    st.markdown("### 📱 快速下注面板")
    open_matches = df_matches[df_matches['status'] == '未開賽']
    
    if df_matches.empty or open_matches.empty:
        st.warning("目前沒有開盤中的賽事。")
    else:
        with st.container(border=True):
            active_user = st.selectbox("👤 選擇你的帳號：", df_users["name"].tolist())
            user_row = df_users[df_users["name"] == active_user].iloc[0]
            st.success(f"💰 你的可用餘額：**{user_row['balance']:.1f} pts**")
        
        bet_mode = st.radio("🎲 選擇玩法：", ["單注", "過關串關"], horizontal=True)
        
        if bet_mode == "單注":
            with st.container(border=True):
                selected_match = st.selectbox("⚽ 選擇賽事：", open_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (ID:{r['match_id']})", axis=1))
                m_id = int(selected_match.split("ID:")[-1].replace(")", ""))
                
                match_odds = df_odds[df_odds["match_id"] == m_id]
                if match_odds.empty:
                    st.error("⚠️ 尚未配置賠率")
                else:
                    odds_options = match_odds.apply(lambda r: f"[{r['play_type']}] {r['selection']} @ {r['odds_value']}", axis=1).tolist()
                    selected_odd_str = st.selectbox("🎯 選擇盤口：", odds_options)
                    
                    chosen_play_type = selected_odd_str.split("] ")[0].replace("[", "")
                    chosen_selection = selected_odd_str.split("] ")[1].split(" @")[0]
                    chosen_odd = match_odds[(match_odds["play_type"] == chosen_play_type) & (match_odds["selection"] == chosen_selection)].iloc[0]
                    o_id = chosen_odd["odd_id"]
                    
                    stake = st.number_input("💵 投注金額：", min_value=1.0, max_value=float(user_row['balance']), value=100.0, step=50.0)
                    
                    if st.button("🚀 確認送出注單", type="primary", use_container_width=True):
                        df_users.loc[df_users["user_id"] == user_row["user_id"], "balance"] -= stake
                        save_sheet(df_users, "Users")
                        
                        new_bet_id = len(df_bets) + 1
                        new_bet = pd.DataFrame([{"bet_id": new_bet_id, "user_id": user_row["user_id"], "bet_mode": "單注", "stake": stake, "status": "未開獎", "win_amount": 0.0}])
                        df_bets = pd.concat([df_bets, new_bet], ignore_index=True)
                        save_sheet(df_bets, "Bets")
                        
                        new_detail = pd.DataFrame([{"detail_id": len(df_details)+1, "bet_id": new_bet_id, "match_id": m_id, "odd_id": o_id, "selection": chosen_odd["selection"], "odds_value": chosen_odd["odds_value"], "status": "未開獎"}])
                        df_details = pd.concat([df_details, new_detail], ignore_index=True)
                        save_sheet(df_details, "BetDetails")
                        
                        st.toast(f"投注成功！扣除 {stake} 點。", icon="✅")
                        time.sleep(1)
                        st.rerun()
                        
        else:
            st.markdown("#### 🔗 串關組合")
            selected_odds_ids = []
            
            with st.container(border=True):
                for idx, row in open_matches.iterrows():
                    m_id = row['match_id']
                    match_odds = df_odds[df_odds["match_id"] == m_id]
                    if not match_odds.empty:
                        odds_options = ["⬜ 不串此場"] + match_odds.apply(lambda r: f"[{r['play_type']}] {r['selection']} @ {r['odds_value']}", axis=1).tolist()
                        choice = st.selectbox(f"⚽ {row['home_team']} VS {row['away_team']}", odds_options, key=f"parlay_{m_id}")
                        if choice != "⬜ 不串此場":
                            chosen_play_type = choice.split("] ")[0].replace("[", "")
                            chosen_selection = choice.split("] ")[1].split(" @")[0]
                            chosen_odd = match_odds[(match_odds["play_type"] == chosen_play_type) & (match_odds["selection"] == chosen_selection)].iloc[0]
                            selected_odds_ids.append((m_id, chosen_odd["odd_id"]))
            
            if len(selected_odds_ids) < 2:
                st.warning("請至少選擇 2 場賽事！")
            else:
                total_odds = 1.0
                for _, o_id in selected_odds_ids:
                    total_odds *= float(df_odds[df_odds["odd_id"] == o_id].iloc[0]["odds_value"])
                
                st.info(f"📊 **{len(selected_odds_ids)} 串 1** ｜ 總賠率: **{total_odds:.2f}**")
                stake = st.number_input("💵 串關投注金額：", min_value=1.0, max_value=float(user_row['balance']), value=100.0, step=50.0)
                
                if st.button("🚀 確認過關下單", type="primary", use_container_width=True):
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
                    
                    st.toast("串關下單成功！", icon="🎉")
                    time.sleep(1)
                    st.rerun()

# ==================== TAB 4: 賽事管理 (Admin) ====================
with tabs[3]:
    st.markdown("### 🛠️ 賽事與賠率建檔")
    with st.expander("➕ 建立新對陣賽事", expanded=True):
        h_team = st.text_input("🏠 主隊", value="德國")
        a_team = st.text_input("✈️ 客隊", value="日本")
        if st.button("創建比賽", use_container_width=True):
            new_m_id = len(df_matches) + 1
            new_m = pd.DataFrame([{"match_id": new_m_id, "home_team": h_team, "away_team": a_team, "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""}])
            df_matches = pd.concat([df_matches, new_m], ignore_index=True)
            save_sheet(df_matches, "Matches")
            st.toast("建立成功！", icon="✅")
            time.sleep(1)
            st.rerun()
            
    with st.expander("⚙️ 新增玩法與賠率", expanded=True):
        if df_matches.empty:
            st.warning("請先創建賽事")
        else:
            match_list = df_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (ID:{r['match_id']})", axis=1).tolist()
            sel_match = st.selectbox("選擇賽事", match_list)
            target_m_id = int(sel_match.split("ID:")[-1].replace(")", ""))
            
            p_type = st.selectbox("玩法類目", ["主客和", "讓球盤", "波膽(比分)", "首名進球"])
            selection_name = st.text_input("選項名稱 (例:主勝)", value="主勝")
            odds_val = st.number_input("賠率設定", min_value=1.01, value=2.20, step=0.05)
            
            if st.button("儲存賠率", use_container_width=True):
                new_o_id = len(df_odds) + 1
                new_odd = pd.DataFrame([{"odd_id": new_o_id, "match_id": target_m_id, "play_type": p_type, "selection": selection_name, "odds_value": odds_val}])
                df_odds = pd.concat([df_odds, new_odd], ignore_index=True)
                save_sheet(df_odds, "Odds")
                st.toast("賠率新增成功！", icon="✅")
                time.sleep(1)
                st.rerun()

# ==================== TAB 5: 賽果結算 (Admin) ====================
with tabs[4]:
    st.markdown("### 🏁 一鍵派彩結算")
    if df_matches.empty:
         st.success("暫無資料。")
    else:
        unsettled_matches = df_matches[df_matches["status"] == "未開賽"]
        if unsettled_matches.empty:
            st.success("🎉 所有賽事皆已結算完畢！")
        else:
            with st.container(border=True):
                sel_unsettled = st.selectbox("📌 選擇完賽場次：", unsettled_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (ID:{r['match_id']})", axis=1))
                settle_m_id = int(sel_unsettled.split("ID:")[-1].replace(")", ""))
                
                st.info("💡 請打勾下方所有「贏」的盤口。未打勾視為輸。")
                match_all_odds = df_odds[df_odds["match_id"] == settle_m_id]
                
                if match_all_odds.empty:
                    st.error("此賽事查無賠率。")
                else:
                    winning_odds_ids = []
                    for idx, row in match_all_odds.iterrows():
                        if st.checkbox(f"[{row['play_type']}] {row['selection']}", key=f"win_{row['odd_id']}"):
                            winning_odds_ids.append(row['odd_id'])
                    
                    st.markdown("#### 錄入比分")
                    sc_home = st.number_input("🏠 主隊比分", min_value=0, value=2)
                    sc_away = st.number_input("✈️ 客隊比分", min_value=0, value=1)
                    
                    if st.button("📊 執行派彩", type="primary", use_container_width=True):
                        with st.spinner('計算與派彩中...'):
                            df_matches.loc[df_matches["match_id"] == settle_m_id, "status"] = "已結算"
                            df_matches.loc[df_matches["match_id"] == settle_m_id, "score_home"] = str(sc_home)
                            df_matches.loc[df_matches["match_id"] == settle_m_id, "score_away"] = str(sc_away)
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
                                            win_amt = round(float(bet["stake"]) * total_odds, 1)
                                            df_bets.loc[df_bets["bet_id"] == b_id, "win_amount"] = win_amt
                                            u_id = bet["user_id"]
                                            df_users.loc[df_users["user_id"] == u_id, "balance"] += win_amt
                                save_sheet(df_bets, "Bets")
                                save_sheet(df_users, "Users")
                        st.success("🎉 結算完畢！積分已發放。")
                        time.sleep(1)
                        st.rerun()
