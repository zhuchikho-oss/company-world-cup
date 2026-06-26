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

@st.cache_data(ttl=5)
def read_sheet(sheet_name):
    try:
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        
        columns_map = {
            "Users": ["user_id", "name", "balance"],
            "Matches": ["match_id", "home_team", "away_team", "status", "score_home", "score_away", "first_goal_player"],
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
<div class="sub-title">【內部專屬隨選賠率簡化版】</div>
</div>
""", unsafe_allow_html=True)

# 🚨 隱藏後台管理權限
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

# ==================== TAB 3: 賽事投注中心（含個人紀錄） ====================
with tabs[2]:
    st.markdown("### 🎲 員工自選賠率下注區")
    open_matches = df_matches[df_matches['status'] != '已結算']
    
    with st.container(border=True):
        active_user = st.selectbox("👤 請選擇你的名字（身分）：", df_users["name"].tolist())
        user_row = df_users[df_users["name"] == active_user].iloc[0]
        u_id = user_row["user_id"]
        st.markdown(f"### 💰 你的可用積分：**{user_row['balance']:.1f} pts**")
        
    # ====== 🌟 核心新功能：每個同事專屬的歷史投注紀錄看板 ======
    with st.expander("📜 點擊展開查看【我的歷史投注紀錄】", expanded=False):
        if df_bets.empty or df_details.empty:
            st.info("您目前沒有任何下注歷史。")
        else:
            my_bets = df_bets[df_bets["user_id"] == u_id]
            if my_bets.empty:
                st.info("您目前沒有任何下注歷史。")
            else:
                user_history = []
                for _, b_row in my_bets.iterrows():
                    b_id = b_row["bet_id"]
                    b_details = df_details[df_details["bet_id"] == b_id]
                    
                    legs_summary = []
                    for _, d_row in b_details.iterrows():
                        m_row = df_matches[df_matches["match_id"] == d_row["match_id"]]
                        m_text = f"{m_row.iloc[0]['home_team']} VS {m_row.iloc[0]['away_team']}" if not m_row.empty else f"場次{d_row['match_id']}"
                        legs_summary.append(f"【{m_text}】{d_row['selection']}(@{d_row['odds_value']}) [{d_row['status']}]")
                    
                    user_history.append({
                        "單號": b_id,
                        "模式": b_row["bet_mode"],
                        "詳細投注內容": " 串 ".join(legs_summary),
                        "本金": f"{b_row['stake']} pts",
                        "總狀態": b_row["status"],
                        "已獲积分": f"{b_row['win_amount']} pts"
                    })
                st.dataframe(pd.DataFrame(user_history), use_container_width=True, hide_index=True)
                
    st.markdown("---")
    
    if df_matches.empty or open_matches.empty:
        st.markdown("#### 📭 目前暫時沒有進行中或開盤的賽事。")
    else:
        bet_mode = st.radio("🎯 選擇下注玩法：", ["單注下注", "過關串關"], horizontal=True)
        
        if bet_mode == "單注下注":
            with st.container(border=True):
                selected_match = st.selectbox("⚽ 選擇比賽場次：", open_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (ID:{r['match_id']})", axis=1))
                m_id = int(selected_match.split("ID:")[-1].replace(")", ""))
                
                custom_selection = st.text_input("🎯 輸入你的下注內容（例：主勝 / 客隊+1 / 波膽 2:1）：", value="主勝")
                custom_odds = st.number_input("📈 請自訂輸入當前外部商業賠率：", min_value=1.01, value=2.00, step=0.01, format="%.2f")
                stake = st.number_input("💵 輸入下注金額：", min_value=1.0, max_value=float(user_row['balance']), value=100.0, step=50.0)
                
                if st.button("📱 確認送出單注", type="primary", use_container_width=True):
                    df_users.loc[df_users["user_id"] == u_id, "balance"] -= stake
                    save_sheet(df_users, "Users")
                    
                    new_bet_id = int(df_bets["bet_id"].max() + 1) if not df_bets.empty else 1
                    new_bet = pd.DataFrame([{"bet_id": new_bet_id, "user_id": u_id, "bet_mode": "單注", "stake": stake, "status": "未開獎", "win_amount": 0.0}])
                    df_bets = pd.concat([df_bets, new_bet], ignore_index=True)
                    save_sheet(df_bets, "Bets")
                    
                    new_detail_id = int(df_details["detail_id"].max() + 1) if not df_details.empty else 1
                    new_detail = pd.DataFrame([{"detail_id": new_detail_id, "bet_id": new_bet_id, "match_id": m_id, "odd_id": 0, "selection": custom_selection.strip(), "odds_value": custom_odds, "status": "未開獎"}])
                    df_details = pd.concat([df_details, new_detail], ignore_index=True)
                    save_sheet(df_details, "BetDetails")
                    
                    st.toast(f"🎉 投注成功！扣除 {stake} 點積分。", icon="✅")
                    time.sleep(1)
                    st.rerun()
                        
        else:
            st.markdown("#### 🔗 自由過關串關組合")
            selected_matches = st.multiselect("⚽ 請挑選 2 場以上的比賽進行串關：", open_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (ID:{r['match_id']})", axis=1))
            
            if len(selected_matches) < 2:
                st.warning("⚠️ 串關模式至少需要勾選 2 場不同的賽事項目。")
            else:
                legs_data = []
                total_odds = 1.0
                
                for idx, mat_str in enumerate(selected_matches):
                    m_id = int(mat_str.split("ID:")[-1].replace(")", ""))
                    with st.container(border=True):
                        st.markdown(f"**🔥 串關第 {idx+1} 關：{mat_str}**")
                        sel = st.text_input(f"輸入該場下注內容", value="主勝", key=f"parlay_sel_{m_id}_{idx}")
                        odd = st.number_input(f"輸入該場盤口賠率", min_value=1.01, value=2.00, step=0.01, format="%.2f", key=f"parlay_odd_{m_id}_{idx}")
                        total_odds *= odd
                        legs_data.append({"match_id": m_id, "selection": sel, "odds_value": odd})
                
                st.markdown(f"### 📈 串關總預計賠率: **{total_odds:.2f} 倍**")
                stake = st.number_input("💵 串關下注總金額：", min_value=1.0, max_value=float(user_row['balance']), value=100.0, step=50.0)
                
                if st.button("🚀 確認執行串關下單", type="primary", use_container_width=True):
                    df_users.loc[df_users["user_id"] == u_id, "balance"] -= stake
                    save_sheet(df_users, "Users")
                    
                    new_bet_id = int(df_bets["bet_id"].max() + 1) if not df_bets.empty else 1
                    new_bet = pd.DataFrame([{"bet_id": new_bet_id, "user_id": u_id, "bet_mode": "過關", "stake": stake, "status": "未開獎", "win_amount": 0.0}])
                    df_bets = pd.concat([df_bets, new_bet], ignore_index=True)
                    save_sheet(df_bets, "Bets")
                    
                    for leg in legs_data:
                        new_detail_id = int(df_details["detail_id"].max() + 1) if not df_details.empty else 1
                        new_detail = pd.DataFrame([{"detail_id": new_detail_id, "bet_id": new_bet_id, "match_id": leg["match_id"], "odd_id": 0, "selection": leg["selection"].strip(), "odds_value": leg["odds_value"], "status": "未開獎"}])
                        df_details = pd.concat([df_details, new_detail], ignore_index=True)
                    save_sheet(df_details, "BetDetails")
                    
                    st.toast("🎉 自由過關串關下單成功！", icon="🎉")
                    time.sleep(1)
                    st.rerun()

# ==================== ⚙️ TAB 4: 管理後台（大幅簡化版） ====================
if is_admin:
    with tabs[3]:
        st.markdown("### ⚙️ 賽事名單管理後台")
        st.markdown("<p style='color:#94a3b8; font-size:0.85rem;'>⚠️ 已取消賠率控盤區。管理員只需確保隊伍名稱與賽況圖正確即可。</p>", unsafe_allow_html=True)
