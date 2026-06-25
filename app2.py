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
    st.error("""❌ 無法連接到 Google Sheets。請檢查網址與服務帳號共用權限。""")
    st.stop()

@st.cache_data(ttl=15)  # 🛡️ 安全快取設定為 15 秒，兼顧即時性與防禦 429 流量限制
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
        
        # 強制校正 Matches 欄位型別，防止 PyArrow 報錯
        if sheet_name == "Matches":
            for col in ["score_home", "score_away", "first_goal_player", "status"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).replace("nan", "")
        return df
    except Exception as google_error:
        st.error(f"❌ 讀取分頁【{sheet_name}】失敗，可能正處於 Google 流量冷卻期，請稍候重整。")
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
        st.cache_data.clear()
    except Exception as e:
        st.error(f"❌ 寫入分頁【{sheet_name}】失敗。")
        st.stop()

# ==================== 2. Streamlit 頁面全局視覺 UI 優化 ====================
st.set_page_config(page_title="2026世界盃虛擬競猜", page_icon="🏆", layout="wide")

# 注入高級運動競猜風 CSS
st.markdown("""
    <style>
    /* 全局背景與字體優化 */
    .stApp { background-color: #f8fafc; }
    
    /* 頂部高級漸層 Banner */
    .main-banner {
        background: linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #1d4ed8 100%);
        padding: 30px;
        border-radius: 16px;
        color: white;
        text-align: center;
        box-shadow: 0 10px 25px -5px rgba(30, 58, 138, 0.3);
        margin-bottom: 25px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }
    .main-title { font-size: 2.8rem; font-weight: 800; letter-spacing: 2px; color: #f59e0b; margin-bottom: 5px; text-shadow: 2px 2px 4px rgba(0,0,0,0.5); }
    .sub-title { font-size: 1.1rem; color: #cbd5e1; font-weight: 300; }
    
    /* 卡片樣式調優 */
    div[data-testid="stMetric"] {
        background-color: white;
        padding: 15px 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        border-left: 5px solid #f59e0b;
    }
    
    /* 賽程樹對陣框樣式 */
    .bracket-match {
        background: white;
        padding: 10px;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02);
        margin-bottom: 12px;
        text-align: center;
    }
    .bracket-team { font-weight: 600; color: #334155; font-size: 0.95rem; }
    .bracket-vs { color: #94a3b8; font-size: 0.8rem; margin: 2px 0; font-style: italic; }
    .bracket-title { font-size: 0.85rem; font-weight: bold; color: #1e3a8a; margin-bottom: 6px; text-transform: uppercase; }
    </style>
    
    <div class="main-banner">
        <div class="main-title">🏆 2026 世界盃虛擬競猜平台</div>
        <div class="sub-title">ROUND OF 32 ・ 內部專屬娛樂資產結算系統</div>
    </div>
    """, unsafe_allow_html=True)

tabs = st.tabs(["📊 資產排行榜", "📅 32強對陣賽程", "🎲 賽事投注中心", "⚙️ 賽事管理 (Admin)", "🧾 賽果結算 (Admin)"])

# ==================== 3. 提取雲端數據 ====================
df_users = read_sheet("Users")
if df_users.empty:
    df_users = pd.DataFrame({"user_id": range(1, 11), "name": [f"同事 {i}" for i in range(1, 11)], "balance": [2000.0] * 10})
    save_sheet(df_users, "Users")

df_matches = read_sheet("Matches")
df_odds = read_sheet("Odds")
df_bets = read_sheet("Bets")
df_details = read_sheet("BetDetails")

# ==================== TAB 1: 資產排行榜 (精美視覺化) ====================
with tabs[0]:
    st.markdown("### 📈 內部財富龍虎榜")
    df_ranking = df_users.sort_values(by="balance", ascending=False).reset_index(drop=True)
    
    if len(df_ranking) >= 3:
        r1, r2, r3 = st.columns(3)
        with r2: st.metric(label="🥇 榜首 (Top 1)", value=df_ranking.iloc[0]["name"], delta=f"{df_ranking.iloc[0]['balance']:.1f} pts")
        with r1:
            if len(df_ranking) > 1: st.metric(label="🥈 亞軍 (Top 2)", value=df_ranking.iloc[1]["name"], delta=f"{df_ranking.iloc[1]['balance']:.1f} pts", delta_color="off")
        with r3:
            if len(df_ranking) > 2: st.metric(label="🥉 季軍 (Top 3)", value=df_ranking.iloc[2]["name"], delta=f"{df_ranking.iloc[2]['balance']:.1f} pts", delta_color="off")
    
    st.markdown("<br>", unsafe_allow_html=True)
    df_ranking.index = df_ranking.index + 1
    df_ranking = df_ranking.rename(columns={"name": "同事姓名", "balance": "當前可用積分 (pts)"})
    st.dataframe(df_ranking[["同事姓名", "當前可用積分 (pts)"]], use_container_width=True)

# ==================== TAB 2: 32強對陣賽程圖 (全新樹狀網格與圖片支援) ====================
with tabs[1]:
    st.markdown("### 📅 2026 世界盃 32 強淘汰賽對陣圖")
    
    # 支援自行更換高畫質大圖網址
    custom_image_url = "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?auto=format&fit=crop&w=1200&q=80" # 預設精美足球背景
    st.image(custom_image_url, caption="💡 提示：此處可替換為官方 32 強最新即時對陣樹狀圖表", use_container_width=True)
    
    st.divider()
    st.markdown("#### 🪵 網頁互動式對陣架構表 (Upper/Lower Brackets)")
    
    b_col1, b_col2, b_col3, b_col4 = st.columns(4)
    with b_col1:
        st.markdown('<div class="bracket-title">🔥 上半區 (左)</div>', unsafe_allow_html=True)
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇩🇪 德國</div><div class="bracket-vs">VS</div><div class="bracket-team">🇯🇵 日本</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="bracket-match"><div class="bracket-team">🏴󠁧󠁢󠁥󠁮󠁧󠁿 英格蘭</div><div class="bracket-vs">VS</div><div class="bracket-team">🇸🇳 塞內加爾</div></div>', unsafe_allow_html=True)
    with b_col2:
        st.markdown('<div class="bracket-title">🔥 上半區 (右)</div>', unsafe_allow_html=True)
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇫🇷 法國</div><div class="bracket-vs">VS</div><div class="bracket-team">🇺🇸 美國</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇦🇷 阿根廷</div><div class="bracket-vs">VS</div><div class="bracket-team">🇦🇺 澳洲</div></div>', unsafe_allow_html=True)
    with b_col3:
        st.markdown('<div class="bracket-title">❄️ 下半區 (左)</div>', unsafe_allow_html=True)
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇪🇸 西班牙</div><div class="bracket-vs">VS</div><div class="bracket-team">摩洛哥 🇲🇦</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇵🇹 葡萄牙</div><div class="bracket-vs">VS</div><div class="bracket-team">瑞士 🇨🇭</div></div>', unsafe_allow_html=True)
    with b_col4:
        st.markdown('<div class="bracket-title">❄️ 下半區 (右)</div>', unsafe_allow_html=True)
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇧🇷 巴西</div><div class="bracket-vs">VS</div><div class="bracket-team">南韓 🇰🇷</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="bracket-match"><div class="bracket-team">🇳🇱 荷蘭</div><div class="bracket-vs">VS</div><div class="bracket-team">克羅埃西亞 🇭🇷</div></div>', unsafe_allow_html=True)

# ==================== TAB 3: 賽事投注中心 (卡片化封裝) ====================
with tabs[2]:
    st.markdown("### 📱 玩家虛擬下注面板")
    open_matches = df_matches[df_matches['status'] == '未開賽']
    
    if df_matches.empty or open_matches.empty:
        st.info("💡 暫時沒有開盤中的 32 強賽事，請管理員到後台建檔比賽！")
    else:
        with st.container(border=True):
            col_user, col_bal = st.columns([2, 1])
            with col_user:
                active_user = st.selectbox("👤 請選擇你的帳號身分：", df_users["name"].tolist())
                user_row = df_users[df_users["name"] == active_user].iloc[0]
            with col_bal:
                st.metric(label="💰 帳戶可用餘額", value=f"{user_row['balance']:.1f} pts")
        
        st.divider()
        bet_mode = st.radio("🎲 玩法選擇：", ["單注 (Single)", "過關串關 (Parlay)"], horizontal=True)
        
        if bet_mode == "單注 (Single)":
            with st.container(border=True):
                selected_match = st.selectbox("⚽ 選擇想下注的 32 強對陣：", open_matches.apply(lambda r: f"【🟢 接受投注】 {r['home_team']} VS {r['away_team']} (賽事ID:{r['match_id']})", axis=1))
                m_id = int(selected_match.split("賽事ID:")[-1].replace(")", ""))
                
                match_odds = df_odds[df_odds["match_id"] == m_id]
                if match_odds.empty:
                    st.warning("⚠️ 此賽事賠率正在精算中，暫未配置！")
                else:
                    odds_options = match_odds.apply(lambda r: f"[{r['play_type']}] {r['selection']} @ 賠率 {r['odds_value']}", axis=1).tolist()
                    selected_odd_str = st.selectbox("🎯 選擇盤口項目：", odds_options)
                    
                    chosen_play_type = selected_odd_str.split("] ")[0].replace("[", "")
                    chosen_selection = selected_odd_str.split("] ")[1].split(" @")[0]
                    chosen_odd = match_odds[(match_odds["play_type"] == chosen_play_type) & (match_odds["selection"] == chosen_selection)].iloc[0]
                    o_id = chosen_odd["odd_id"]
                    
                    stake = st.number_input("💵 輸入投注點數：", min_value=1.0, max_value=float(user_row['balance']), value=100.0, step=50.0)
                    
                    if st.button("🚀 送出注單", type="primary", use_container_width=True):
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
            st.markdown("#### 🔗 32強全場景串關神器 (Parlay Builder)")
            selected_odds_ids = []
            
            with st.container(border=True):
                for idx, row in open_matches.iterrows():
                    m_id = row['match_id']
                    match_odds = df_odds[df_odds["match_id"] == m_id]
                    if not match_odds.empty:
                        odds_options = ["⬜ 不串此場比賽"] + match_odds.apply(lambda r: f"[{r['play_type']}] {r['selection']} @ {r['odds_value']}", axis=1).tolist()
                        choice = st.selectbox(f"⚽ {row['home_team']} VS {row['away_team']}", odds_options, key=f"parlay_{m_id}")
                        if choice != "⬜ 不串此場比賽":
                            chosen_play_type = choice.split("] ")[0].replace("[", "")
                            chosen_selection = choice.split("] ")[1].split(" @")[0]
                            chosen_odd = match_odds[(match_odds["play_type"] == chosen_play_type) & (match_odds["selection"] == chosen_selection)].iloc[0]
                            selected_odds_ids.append((m_id, chosen_odd["odd_id"]))
            
            if len(selected_odds_ids) < 2:
                st.warning("⚠️ 串關組合至少需要選擇 2 場不同的賽事項目！")
            else:
                total_odds = 1.0
                for _, o_id in selected_odds_ids:
                    total_odds *= float(df_odds[df_odds["odd_id"] == o_id].iloc[0]["odds_value"])
                
                st.success(f"📊 串關狀態: **{len(selected_odds_ids)} 串 1** ｜ 綜合總賠率: **{total_odds:.2f}**")
                stake = st.number_input("💵 輸入串關總下注點數：", min_value=1.0, max_value=float(user_row['balance']), value=100.0, step=50.0)
                
                if st.button("🚀 執行過關組合下單", type="primary", use_container_width=True):
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
                    
                    st.toast(f"豪華過關下單成功！扣除 {stake} 點。", icon="🎉")
                    time.sleep(1)
                    st.rerun()

# ==================== TAB 4: 賽事與賠率管理 (Admin) ====================
with tabs[3]:
    st.markdown("### 🛠️ 賽事管理及自定義賠率後台")
    col_match, col_odd = st.columns(2)
    with col_match:
        with st.container(border=True):
            st.markdown("#### ➕ 增設新開盤賽事")
            h_team = st.text_input("🏠 主隊（國家隊）", value="德國")
            a_team = st.text_input("✈️ 客隊（國家隊）", value="日本")
            if st.button("確認開盤此比賽", use_container_width=True):
                new_m_id = len(df_matches) + 1
                new_m = pd.DataFrame([{"match_id": new_m_id, "home_team": h_team, "away_team": a_team, "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""}])
                df_matches = pd.concat([df_matches, new_m], ignore_index=True)
                save_sheet(df_matches, "Matches")
                st.toast("新對陣建檔完成！", icon="✅")
                time.sleep(1)
                st.rerun()
            
    with col_odd:
        with st.container(border=True):
            st.markdown("#### ⚙️ 自定義賠率精算")
            if df_matches.empty:
                st.info("請先創建賽事")
            else:
                match_list = df_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (ID:{r['match_id']})", axis=1).tolist()
                sel_match = st.selectbox("選擇指定賽事", match_list)
                target_m_id = int(sel_match.split("ID:")[-1].replace(")", ""))
                
                p_type = st.selectbox("精選玩法", ["主客和", "讓球盤", "波膽(精確比分)", "首名入球員"])
                selection_name = st.text_input("選項名稱 (例: '主勝', '1:1', '和局')", value="主勝")
                odds_val = st.number_input("設定即時賠率", min_value=1.01, value=2.20, step=0.05)
                
                if st.button("寫入賠率庫", use_container_width=True):
                    new_o_id = len(df_odds) + 1
                    new_odd = pd.DataFrame([{"odd_id": new_o_id, "match_id": target_m_id, "play_type": p_type, "selection": selection_name, "odds_value": odds_val}])
                    df_odds = pd.concat([df_odds, new_odd], ignore_index=True)
                    save_sheet(df_odds, "Odds")
                    st.toast("賠率配置成功！", icon="✅")
                    time.sleep(1)
                    st.rerun()
                    
    with st.expander("🔍 核心資料庫即時監控面板", expanded=False):
        st.caption("Matches 賽事表單")
        st.dataframe(df_matches, use_container_width=True, hide_index=True)
        st.caption("Odds 賠率對照表單")
        st.dataframe(df_odds, use_container_width=True, hide_index=True)

# ==================== TAB 5: 賽果結算後台 (Admin) ====================
with tabs[4]:
    st.markdown("### 🏁 賽果錄入與派彩結算中心")
    if df_matches.empty:
         st.success("✅ 當前無任何賽事資料。")
    else:
        unsettled_matches = df_matches[df_matches["status"] == "未開賽"]
        
        if unsettled_matches.empty:
            st.success("🎉 精彩！目前所有 32 強賽事皆已全數派彩結算完畢。")
        else:
            with st.container(border=True):
                sel_unsettled = st.selectbox("📌 選擇準備結算的完賽場次：", unsettled_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (ID:{r['match_id']})", axis=1))
                settle_m_id = int(sel_unsettled.split("ID:")[-1].replace(")", ""))
                
                st.warning("""💡 **結算規則**：請打勾下方所有**「判定為贏面、中獎」**的賠率選項，未打勾的系統會一律判定為未中獎。""")
                
                match_all_odds = df_odds[df_odds["match_id"] == settle_m_id]
                
                if match_all_odds.empty:
                    st.error("❌ 該賽事查無配置賠率，無法執行結算。")
                else:
                    st.markdown("#### 1. 勾選所有中獎盤口")
                    winning_odds_ids = []
                    
                    odds_cols = st.columns(2)
                    for idx, row in match_all_odds.iterrows():
                        col_target = odds_cols[idx % 2]
                        with col_target:
                            is_win = st.checkbox(f"[{row['play_type']}] {row['selection']}", key=f"win_{row['odd_id']}")
                            if is_win: winning_odds_ids.append(row['odd_id'])
                    
                    st.markdown("#### 2. 輸入最終官方正賽數據")
                    res_col1, res_col2, res_col3 = st.columns(3)
                    with res_col1: sc_home = st.number_input("🏠 主隊總比分", min_value=0, value=2)
                    with res_col2: sc_away = st.number_input("✈️ 客隊總比分", min_value=0, value=1)
                    with res_col3: f_goal = st.text_input("⚽ 首位進球球員", value="無")
                    
                    if st.button("📊 精準派彩！一鍵執行利潤發放", type="primary", use_container_width=True):
                        with st.spinner('計算中，正將發放金額同步並刷新 Google Sheets，請稍候...'):
                            
                            # 型別安全轉型字串
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
                                            
                                            win_amt = round(float(bet["stake"]) * total_odds, 1)
                                            df_bets.loc[df_bets["bet_id"] == b_id, "win_amount"] = win_amt
                                            
                                            u_id = bet["user_id"]
                                            df_users.loc[df_users["user_id"] == u_id, "balance"] += win_amt
                                
                                save_sheet(df_bets, "Bets")
                                save_sheet(df_users, "Users")
                            time.sleep(0.5)
                            
                        st.success("""🎉 結算完畢！得獎同事的帳戶點數已發放完成，龍虎排行榜已自動重新洗牌。""")
                        time.sleep(1)
                        st.rerun()

