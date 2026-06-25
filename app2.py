import streamlit as st
import pandas as pd
import time
import requests
import xml.etree.ElementTree as ET
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

# ==================== 2. Streamlit 頁面全局設定 ====================
st.set_page_config(page_title="2026世界盃競猜", page_icon="🏆", layout="centered")

st.markdown("""
<style>
.stApp { background-color: #0c1328 !important; }
p, label, h1, h2, h3, h4, h5, h6 { color: #fef3c7 !important; font-weight: 700 !important; }
div[data-baseweb="select"] *, div[role="listbox"] *, ul[data-baseweb="menu"] *, input {
    color: #000000 !important; font-weight: 800 !important;
}
.main-banner {
    background-color: #0c1328; padding: 15px; border-radius: 8px;
    border: 2px solid #fef3c7; text-align: center; margin-bottom: 20px;
}
.main-title { font-size: 1.8rem; font-weight: 900; color: #fef3c7 !important; margin-bottom: 5px; } 
.sub-title { font-size: 1.1rem; color: #fef3c7 !important; font-weight: 800; }
hr { border-color: #cbd5e1 !important; }
.news-card {
    background-color: #1a1f33; border-left: 4px solid #fef3c7; padding: 12px 15px;
    margin-bottom: 12px; border-radius: 0 8px 8px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}
.news-title { color: #f8fafc !important; font-weight: 800; font-size: 1.05rem; margin-bottom: 4px; }
.news-time { color: #94a3b8 !important; font-size: 0.8rem; }
.bracket-wrapper {
    display: flex; flex-direction: row; overflow-x: auto; padding: 20px 5px; gap: 25px; white-space: nowrap;
}
.bracket-wrapper::-webkit-scrollbar { height: 6px; }
.bracket-wrapper::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
.bracket-round { display: flex; flex-direction: column; justify-content: space-around; gap: 20px; min-width: 230px; }
.round-title {
    font-size: 0.85rem; color: #fef3c7 !important; font-weight: 800; text-align: center;
    background: #1e293b; padding: 6px 12px; border-radius: 20px; border: 1px solid #475569;
    margin-bottom: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);
}
.match-card {
    background: linear-gradient(135deg, #131a35, #1e294b); border: 2px solid #38bdf8;
    border-radius: 12px; padding: 14px; box-shadow: 0 10px 20px rgba(0,0,0,0.4);
    display: flex; flex-direction: column; gap: 8px;
}
.border-gray { border-color: #475569 !important; }
.final-card {
    border: 3px solid #fbbf24 !important; background: linear-gradient(135deg, #1c1917, #292524) !important;
    box-shadow: 0 0 15px rgba(251, 191, 36, 0.3);
}
.match-header {
    display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem;
    color: #94a3b8 !important; border-bottom: 1px solid #334155; padding-bottom: 6px; font-weight: bold;
}
.team-row { display: flex; justify-content: space-between; align-items: center; }
.team-name { font-size: 0.95rem; font-weight: 800; color: #f8fafc !important; }
.text-muted { color: #64748b !important; font-weight: 600; }
.team-score {
    font-size: 1.05rem; font-weight: 900; color: #fbbf24 !important; background: #0f172a;
    padding: 2px 10px; border-radius: 6px; min-width: 32px; text-align: center; border: 1px solid #334155;
}
.status-badge { font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; font-weight: 900 !important; color: #ffffff !important; }
.status-badge.settled { background-color: #059669; }
.status-badge.live { background-color: #dc2626; animation: pulse 1.5s infinite; }
.status-badge.upcoming { background-color: #475569; }
.next-route {
    font-size: 0.75rem; color: #38bdf8 !important; background: #0f172a; padding: 4px 8px;
    border-radius: 6px; text-align: center; font-weight: bold; margin-top: 4px; border: 1px solid #1e293b;
}
.final-winner { font-size: 0.8rem; color: #fbbf24 !important; text-align: center; font-weight: 900; letter-spacing: 0.1em; margin-top: 4px; }
@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.6; } 100% { opacity: 1; } }
</style>

<div class="main-banner">
<div class="main-title">🏆 2026 世界盃 競猜中心</div>
<div class="sub-title">【內部專屬手機高清晰深色版】</div>
</div>
""", unsafe_allow_html=True)

# 🚨 隱藏後台邏輯
is_admin = False
if "role" in st.query_params and st.query_params["role"] == "boss":
    is_admin = True

if is_admin:
    tabs = st.tabs(["📊 財富排行", "📅 賽況樹状圖", "🎲 快速投注", "⚙️ 管理後台", "🏁 完賽結算"])
else:
    tabs = st.tabs(["📊 財富排行", "📅 賽況樹状圖", "🎲 快速投注"])

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

# ==================== TAB 2: 高級樹狀圖賽程 (32強) ====================
with tabs[1]:
    st.markdown("### 📰 最新世界盃動態")
    with st.expander("📡 點擊展開即時體育新聞", expanded=False):
        try:
            response = requests.get("https://sports.yahoo.com/soccer/rss/", timeout=4)
            if response.status_code == 200:
                root = ET.fromstring(response.content)
                count = 0
                for item in root.findall('./channel/item'):
                    if count >= 4: break
                    title = item.find('title').text
                    pubDate = item.find('pubDate').text
                    clean_time = pubDate.split(" +")[0].split(" GMT")[0]
                    st.markdown(f"""
<div class="news-card">
<div class="news-title">⚽ {title}</div>
<div class="news-time">🕒 {clean_time}</div>
</div>
""", unsafe_allow_html=True)
                    count += 1
        except Exception:
            st.markdown("<p style='color:#94a3b8;'>網路連線超時</p>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🏆 32強淘汰賽晉級線路圖")
    st.markdown("<p style='font-size:0.85rem; color:#cbd5e1; margin-top:-10px;'>👉 提示：手機版支援<b>左右滑動瀏覽</b>！</p>", unsafe_allow_html=True)

    def get_route_text(m_id):
        if 1 <= m_id <= 16: return f"➡️ 晉級：十六強 (場次 {17 + (m_id - 1) // 2})"
        elif 17 <= m_id <= 24: return f"➡️ 晉級：八強 (場次 {25 + (m_id - 17) // 2})"
        elif 25 <= m_id <= 28: return f"➡️ 晉級：四強 (場次 {29 + (m_id - 25) // 2})"
        elif 29 <= m_id <= 30: return "🏆 前進總決賽 (場次 31)"
        elif m_id == 31: return "👑 爭奪世界之巔"
        else: return "➡️ 晉級下一輪"

    def get_match_card_html(m_id, title_name):
        route_text = get_route_text(m_id)
        if df_matches.empty:
            return f'<div class="match-card"><div class="match-header"><span>{title_name}</span><span class="status-badge upcoming">未開賽</span></div><div class="team-row"><span class="team-name text-muted">待定</span><span class="team-score">-</span></div><div class="team-row"><span class="team-name text-muted">待定</span><span class="team-score">-</span></div></div>'
        
        m_rows = df_matches[df_matches['match_id'] == m_id]
        if m_rows.empty:
            home, away, status, s_home, s_away = "待定", "待定", "未開賽", "-", "-"
        else:
            row = m_rows.iloc[0]
            home = row['home_team'] if str(row['home_team']).strip() != "" else "待定"
            away = row['away_team'] if str(row['away_team']).strip() != "" else "待定"
            status = row['status']
            
            # 只有在「已結算」的狀態下，才會將比分顯示出來；否則強制顯示 "-"
            if status == "已結算":
                s_home = str(row['score_home']).strip() if str(row['score_home']).strip() != "" else "-"
                s_away = str(row['score_away']).strip() if str(row['score_away']).strip() != "" else "-"
            else:
                s_home = "-"
                s_away = "-"

        if status == "已結算": badge = '<span class="status-badge settled">已完賽</span>'
        elif status == "進行中": badge = '<span class="status-badge live">LIVE</span>'
        else: badge = '<span class="status-badge upcoming">未開賽</span>'
            
        is_final = (m_id == 31)
        card_class = "match-card final-card" if is_final else "match-card"
        if not m_rows.empty and m_id > 16 and status == "未開賽":
            card_class += " border-gray"
            
        header_style = ' style="border-color: #fbbf24;"' if is_final else ''
        title_style = ' style="color:#fbbf24 !important; font-weight:900;"' if is_final else ''
        score_style = ' style="color:#fbbf24;"' if is_final else ''
        
        html = f"""
<div class="{card_class}">
<div class="match-header"{header_style}><span{title_style}>{title_name} (M{m_id})</span>{badge}</div>
<div class="team-row"><span class="team-name">⚽ {home}</span><span class="team-score"{score_style}>{s_home}</span></div>
<div class="team-row"><span class="team-name">⚽ {away}</span><span class="team-score"{score_style}>{s_away}</span></div>
"""
        if is_final: html += f'<div class="final-winner">{route_text}</div></div>'
        else: html += f'<div class="next-route">{route_text}</div></div>'
        return html

    ro32_html = "".join([get_match_card_html(i, "32強賽") for i in range(1, 17)])
    ro16_html = "".join([get_match_card_html(i, "十六強賽") for i in range(17, 25)])
    qf_html = "".join([get_match_card_html(i, "半準決賽") for i in range(25, 29)])
    sf_html = "".join([get_match_card_html(i, "準決賽") for i in range(29, 31)])
    final_html = get_match_card_html(31, "🏆 FINAL 總決賽")

    bracket_html = f"""
<div class="bracket-wrapper">
<div class="bracket-round"><div class="round-title">⚔️ 32強淘汰賽</div>{ro32_html}</div>
<div class="bracket-round"><div class="round-title">🔥 16強淘汰賽</div>{ro16_html}</div>
<div class="bracket-round"><div class="round-title">⚡ 八強半準決賽</div>{qf_html}</div>
<div class="bracket-round"><div class="round-title">🌟 四強準決賽</div>{sf_html}</div>
<div class="bracket-round"><div class="round-title" style="color:#fbbf24;">👑 冠軍總決賽</div>{final_html}</div>
</div>
"""
    st.markdown(bracket_html, unsafe_allow_html=True)

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
                    st.markdown("⚠️ 這場比賽還沒設定賠率！")
                else:
                    odds_options = match_odds.apply(lambda r: f"[{r['play_type']}] {r['selection']} @ {r['odds_value']} 倍", axis=1).tolist()
                    selected_odd_str = st.selectbox("🎯 選擇盤口選項：", odds_options)
                    
                    chosen_play_type = selected_odd_str.split("] ")[0].replace("[", "")
                    chosen_selection = selected_odd_str.split("] ")[1].split(" @")[0]
                    chosen_odd = match_odds[(match_odds["play_type"] == chosen_play_type) & (match_odds["selection"] == chosen_selection)].iloc[0]
                    o_id = chosen_odd["odd_id"]
                    
                    stake = st.number_input("💵 輸入下注金額：", min_value=1.0, max_value=float(user_row['balance']), value=100.0, step=50.0)
                    
                    if st.button("📱 確認送出注單", type="primary", use_container_width=True):
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
            st.markdown("#### 🔗 串關組合 (Parlay Builder)")
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
                st.markdown("⚠️ 過關模式至少需要選擇 2 場不同的賽事項目！")
            else:
                total_odds = 1.0
                for _, o_id in selected_odds_ids:
                    total_odds *= float(df_odds[df_odds["odd_id"] == o_id].iloc[0]["odds_value"])
                
                st.markdown(f"### 📊 當前組合: **{len(selected_odds_ids)} 串 1**")
                st.markdown(f"### 📈 總預計賠率: **{total_odds:.2f} 倍**")
                
                stake = st.number_input("💵 串關投注金額：", min_value=1.0, max_value=float(user_row['balance']), value=100.0, step=50.0)
                
                if st.button("🚀 確認執行串關下單", type="primary", use_container_width=True):
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

# ==================== ⚙️ 管理員獨享：TAB 4 & TAB 5 ====================
if is_admin:
    with tabs[3]:
        st.markdown("### ⚙️ 賽事管理與後台")
        
        st.markdown("#### 🛠️ 單一賽事編輯 / 新增 / 刪除")
        with st.container(border=True):
            manage_mode = st.radio("選擇操作模式：", ["✏️ 編輯 / 刪除現有賽事", "➕ 新增自定義賽事"], horizontal=True)
            
            if manage_mode == "✏️ 編輯 / 刪除現有賽事":
                if df_matches.empty:
                    st.warning("目前資料庫沒有任何賽事。")
                else:
                    match_list = df_matches.apply(lambda r: f"ID:{r['match_id']} | {r['home_team']} VS {r['away_team']} ({r['status']})", axis=1).tolist()
                    sel_match_str = st.selectbox("🔍 選擇要修改的賽事", match_list)
                    sel_m_id = int(sel_match_str.split("ID:")[1].split(" |")[0])
                    
                    target_row = df_matches[df_matches['match_id'] == sel_m_id].iloc[0]
                    
                    with st.form("edit_match_form"):
                        c1, c2, c3 = st.columns(3)
                        new_home = c1.text_input("🏠 主隊名稱", value=str(target_row['home_team']))
                        new_away = c2.text_input("✈️ 客隊名稱", value=str(target_row['away_team']))
                        new_status = c3.selectbox("📊 賽事狀態", ["未開賽", "進行中", "已結算"], index=["未開賽", "進行中", "已結算"].index(target_row['status']) if target_row['status'] in ["未開賽", "進行中", "已結算"] else 0)
                        
                        c4, c5 = st.columns(2)
                        new_sc_home = c4.text_input("🏠 主隊比分 (留空代表不呈現比分)", value=str(target_row['score_home']) if str(target_row['score_home']) != "nan" else "")
                        new_sc_away = c5.text_input("✈️ 客隊比分 (留空代表不呈現比分)", value=str(target_row['score_away']) if str(target_row['score_away']) != "nan" else "")
                        
                        col_btn1, col_btn2 = st.columns(2)
                        btn_update = col_btn1.form_submit_button("💾 更新此賽事資料 (含比分)", type="primary", use_container_width=True)
                        btn_delete = col_btn2.form_submit_button("🗑️ 刪除此賽事", use_container_width=True)
                        
                        if btn_update:
                            df_matches.loc[df_matches['match_id'] == sel_m_id, 'home_team'] = new_home.strip()
                            df_matches.loc[df_matches['match_id'] == sel_m_id, 'away_team'] = new_away.strip()
                            df_matches.loc[df_matches['match_id'] == sel_m_id, 'status'] = new_status
                            df_matches.loc[df_matches['match_id'] == sel_m_id, 'score_home'] = new_sc_home.strip()
                            df_matches.loc[df_matches['match_id'] == sel_m_id, 'score_away'] = new_sc_away.strip()
                            save_sheet(df_matches, "Matches")
                            st.toast("✅ 賽事資料與比分已同步更新！", icon="✅")
                            time.sleep(1)
                            st.rerun()
                            
                        if btn_delete:
                            df_matches = df_matches[df_matches['match_id'] != sel_m_id]
                            save_sheet(df_matches, "Matches")
                            st.toast("🗑️ 賽事已成功刪除！", icon="✅")
                            time.sleep(1)
                            st.rerun()

            elif manage_mode == "➕ 新增自定義賽事":
                with st.form("add_match_form"):
                    c1, c2 = st.columns(2)
                    new_m_id = int(df_matches['match_id'].max() + 1) if not df_matches.empty else 1
                    custom_id = c1.number_input("設定場次 ID (避開 1~31 的樹狀圖專用 ID)", min_value=1, value=max(32, new_m_id))
                    c2.markdown("<br><p style='color:#94a3b8; font-size:0.8rem;'>如果設定 ID 為 1~31，將會自動同步到賽況樹狀圖中。</p>", unsafe_allow_html=True)
                    
                    c3, c4 = st.columns(2)
                    add_home = c3.text_input("🏠 填寫主隊名稱")
                    add_away = c4.text_input("✈️ 填寫客隊名稱")
                    
                    if st.form_submit_button("➕ 建立賽事", type="primary", use_container_width=True):
                        if not df_matches[df_matches['match_id'] == custom_id].empty:
                            st.error(f"❌ ID {custom_id} 已經存在，請更換其他 ID。")
                        else:
                            new_m = pd.DataFrame([{"match_id": custom_id, "home_team": add_home.strip(), "away_team": add_away.strip(), "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""}])
                            df_matches = pd.concat([df_matches, new_m], ignore_index=True)
                            save_sheet(df_matches, "Matches")
                            st.toast("✅ 新賽事建立成功！", icon="🎉")
                            time.sleep(1)
                            st.rerun()

        st.markdown("#### 🏆 32強淘汰賽樹狀圖 一鍵設定")
        st.markdown("<p style='font-size:0.85rem; color:#94a3b8;'>👉 分區填寫隊伍，系統會自動將隊伍寫入對應的場次 ID (1 ~ 31)。留白則顯示為待定。</p>", unsafe_allow_html=True)
        
        with st.form("bracket_update_form"):
            with st.expander("⚔️ 填寫 32強 (場次 1 ~ 16)", expanded=False):
                c1, c2 = st.columns(2)
                updated_teams = {}
                for m_id in range(1, 17):
                    target_col = c1 if m_id <= 8 else c2
                    existing = df_matches[df_matches['match_id'] == m_id]
                    ch = str(existing.iloc[0]['home_team']) if not existing.empty else ""
                    ca = str(existing.iloc[0]['away_team']) if not existing.empty else ""
                    with target_col:
                        h = st.text_input(f"M{m_id} 主隊", value=ch, key=f"h_{m_id}")
                        a = st.text_input(f"M{m_id} 客隊", value=ca, key=f"a_{m_id}")
                        updated_teams[m_id] = {"home": h, "away": a}
                        st.markdown("<hr style='margin:4px 0; border-color:#334155;'>", unsafe_allow_html=True)

            with st.expander("🔥 填寫 16強 (場次 17 ~ 24)", expanded=False):
                c1, c2 = st.columns(2)
                for m_id in range(17, 25):
                    target_col = c1 if m_id <= 20 else c2
                    existing = df_matches[df_matches['match_id'] == m_id]
                    ch = str(existing.iloc[0]['home_team']) if not existing.empty else ""
                    ca = str(existing.iloc[0]['away_team']) if not existing.empty else ""
                    with target_col:
                        h = st.text_input(f"M{m_id} 主隊", value=ch, key=f"h_{m_id}")
                        a = st.text_input(f"M{m_id} 客隊", value=ca, key=f"a_{m_id}")
                        updated_teams[m_id] = {"home": h, "away": a}
                        st.markdown("<hr style='margin:4px 0; border-color:#334155;'>", unsafe_allow_html=True)

            with st.expander("⚡ 填寫 8強 至 總決賽 (場次 25 ~ 31)", expanded=False):
                c1, c2 = st.columns(2)
                for m_id in range(25, 32):
                    target_col = c1 if m_id <= 28 else c2
                    existing = df_matches[df_matches['match_id'] == m_id]
                    ch = str(existing.iloc[0]['home_team']) if not existing.empty else ""
                    ca = str(existing.iloc[0]['away_team']) if not existing.empty else ""
                    with target_col:
                        lbl = f"M{m_id} (八強)" if m_id<=28 else (f"M{m_id} (四強)" if m_id<=30 else "M31 (決賽)")
                        h = st.text_input(f"{lbl} 主隊", value=ch, key=f"h_{m_id}")
                        a = st.text_input(f"{lbl} 客隊", value=ca, key=f"a_{m_id}")
                        updated_teams[m_id] = {"home": h, "away": a}
                        st.markdown("<hr style='margin:4px 0; border-color:#334155;'>", unsafe_allow_html=True)
            
            if st.form_submit_button("💾 儲存樹狀圖名單", type="primary", use_container_width=True):
                for m_id, teams in updated_teams.items():
                    h_val = teams['home'].strip()
                    a_val = teams['away'].strip()
                    if not df_matches[df_matches['match_id'] == m_id].empty:
                        df_matches.loc[df_matches['match_id'] == m_id, 'home_team'] = h_val
                        df_matches.loc[df_matches['match_id'] == m_id, 'away_team'] = a_val
                    else:
                        if h_val or a_val:
                            new_m = pd.DataFrame([{"match_id": m_id, "home_team": h_val, "away_team": a_val, "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""}])
                            df_matches = pd.concat([df_matches, new_m], ignore_index=True)
                save_sheet(df_matches, "Matches")
                st.toast("✅ 樹狀圖對戰名單已同步上線！", icon="🎉")
                time.sleep(1)
                st.rerun()

        with st.container(border=True):
            st.markdown("#### ⚙️ 為賽事新增賠率盤口")
            if df_matches.empty:
                st.markdown("請先在上方設定賽事。")
            else:
                match_list = df_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (ID:{r['match_id']})", axis=1).tolist()
                sel_match = st.selectbox("選擇要開盤的比賽", match_list)
                target_m_id = int(sel_match.split("ID:")[-1].replace(")", ""))
                
                p_type = st.selectbox("玩法種類", ["主客和", "讓球盤", "波膽盤", "首名進球", "晉級隊伍"])
                selection_name = st.text_input("選項名稱 (例:主勝)", value="主勝")
                odds_val = st.number_input("賠率設定", min_value=1.01, value=2.20, step=0.05)
                
                if st.button("儲存賠率項目", use_container_width=True):
                    new_o_id = len(df_odds) + 1
                    new_odd = pd.DataFrame([{"odd_id": new_o_id, "match_id": target_m_id, "play_type": p_type, "selection": selection_name, "odds_value": odds_val}])
                    df_odds = pd.concat([df_odds, new_odd], ignore_index=True)
                    save_sheet(df_odds, "Odds")
                    st.toast("賠率新增成功！")
                    time.sleep(1)
                    st.rerun()

        # ==================== 🌐 網路賽況半自動同步 (API 串接區) ====================
        st.markdown("---")
        st.markdown("#### 🌐 網路賽況半自動同步 (API 串接區)")
        st.markdown("<p style='font-size:0.85rem; color:#94a3b8;'>點擊下方按鈕，系統將自動模擬從 API 抓取最新比分，並將符合隊伍名單的比賽更新至 Google Sheets。</p>", unsafe_allow_html=True)
        
        def fetch_live_scores_from_api():
            # 💡 未來有真實 API Key 時可替換此處。目前採用模擬數據進行調試：
            return [
                {"home_team": "阿根廷", "away_team": "法國", "status": "已結算", "score_home": 3, "score_away": 3},
                {"home_team": "巴西", "away_team": "德國", "status": "進行中", "score_home": 1, "score_away": 0}
            ]

        if st.button("🔄 一鍵同步最新賽果與比分", type="primary", use_container_width=True):
            with st.spinner('連線至全球體育數據庫中...'):
                try:
                    live_data = fetch_live_scores_from_api()
                    update_count = 0
                    
                    if not df_matches.empty:
                        for match_info in live_data:
                            # 僅針對目前在資料庫中「尚未手動結算」的場次進行更新，防止歷史紀錄被覆寫
                            mask = (df_matches['home_team'] == match_info['home_team']) & \
                                   (df_matches['away_team'] == match_info['away_team']) & \
                                   (df_matches['status'] != '已結算')
                            
                            if not df_matches[mask].empty:
                                m_id = df_matches[mask].iloc[0]['match_id']
                                df_matches.loc[df_matches["match_id"] == m_id, "score_home"] = str(match_info['score_home'])
                                df_matches.loc[df_matches["match_id"] == m_id, "score_away"] = str(match_info['score_away'])
                                df_matches.loc[df_matches["match_id"] == m_id, "status"] = match_info['status']
                                update_count += 1
                        
                        if update_count > 0:
                            save_sheet(df_matches, "Matches")
                            st.success(f"✅ 同步成功！已自動更新 {update_count} 場比賽的即時比分與狀態。")
                            time.sleep(1.5)
                            st.rerun()
                        else:
                            st.info("ℹ️ 目前沒有需要更新的賽事（可能是樹狀圖中的隊伍名稱與 API 資料未對齊，或比賽皆已結算）。")
                except Exception as e:
                    st.error(f"❌ 抓取數據失敗，請檢查 API 連線狀態。錯誤代碼: {e}")

    with tabs[4]:
        st.markdown("### 🏁 賽果與派彩中心")
        if df_matches.empty:
             st.markdown("目前沒有比賽數據。")
        else:
            unsettled_matches = df_matches[df_matches["status"] != "已結算"]
            if unsettled_matches.empty:
                st.markdown("### 🎉 太棒了！所有比賽皆已結算完畢。")
            else:
                with st.container(border=True):
                    sel_unsettled = st.selectbox("📌 選擇準備派彩的完賽場次：", unsettled_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (ID:{r['match_id']})", axis=1))
                    settle_m_id = int(sel_unsettled.split("ID:")[-1].replace(")", ""))
                    
                    st.markdown("⚠️ **重要步驟**：請在下方打勾這場比賽中**『所有贏』**的選項。沒打勾視為未中獎。")
                    match_all_odds = df_odds[df_odds["match_id"] == settle_m_id]
                    
                    if match_all_odds.empty:
                        st.error("此賽事查無賠率。")
                    else:
                        winning_odds_ids = []
                        for idx, row in match_all_odds.iterrows():
                            if st.checkbox(f"[{row['play_type']}] {row['selection']}", key=f"win_{row['odd_id']}"):
                                winning_odds_ids.append(row['odd_id'])
                        
                        st.markdown("#### 填入最終比分")
                        curr_match_data = df_matches[df_matches["match_id"] == settle_m_id].iloc[0]
                        try:
                            default_h = int(float(curr_match_data['score_home'])) if str(curr_match_data['score_home']).strip() != "" else 0
                            default_a = int(float(curr_match_data['score_away'])) if str(curr_match_data['score_away']).strip() != "" else 0
                        except:
                            default_h, default_a = 0, 0
                            
                        sc_home = st.number_input("🏠 主隊最終比分", min_value=0, value=default_h)
                        sc_away = st.number_input("✈️ 客隊最終比分", min_value=0, value=default_a)
                        
                        if st.button("📊 確認比分與勾選項，執行派彩", type="primary", use_container_width=True):
                            with st.spinner('同步資料庫與發放點數中...'):
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
                            st.success("🎉 結算完成！贏家點數已撥款。")
                            time.sleep(1)
                            st.rerun()
