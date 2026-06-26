import streamlit as st
import pandas as pd
import time
import itertools
import gspread
from google.oauth2.service_account import Credentials

# 為了徹底防止 Pandas 與 Google Sheets 間的型態問題，建立全域清理函數
def clean_id(x):
    s = str(x).strip()
    if s.endswith('.0'):
        return s[:-2]
    return s

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

@st.cache_data(ttl=2)
def read_sheet(sheet_name):
    try:
        worksheet = sh.worksheet(sheet_name)
        data = worksheet.get_all_records()
        
        columns_map = {
            "Users": ["user_id", "name", "balance"],
            "Matches": ["match_id", "home_team", "away_team", "status", "score_home", "score_away", "first_goal_player"],
            "Bets": ["bet_id", "user_id", "bet_mode", "stake", "status", "win_amount"],
            "BetDetails": ["detail_id", "bet_id", "match_id", "playstyle", "selection", "odds_value", "status"]
        }
        
        if not data:
            return pd.DataFrame(columns=columns_map.get(sheet_name, []))
            
        df = pd.DataFrame(data)
        
        # 強制清理所有 ID 欄位，保證後續運算 100% 精準匹配
        id_cols = ["user_id", "match_id", "bet_id", "detail_id"]
        for col in id_cols:
            if col in df.columns:
                df[col] = df[col].apply(clean_id)
                
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

# ==================== 2. 全自動對獎與過關拆單演算法 ====================

def auto_evaluate_leg(playstyle, selection, hs, as_, first_goal, home_team, away_team):
    """根據比賽的實際比分，自動判斷該注單是贏還是輸"""
    try:
        hs = int(hs)
        as_ = int(as_)
    except ValueError:
        return "未開獎"

    if "獨贏盤" in playstyle:
        actual = f"主勝 ({home_team})" if hs > as_ else "和局 (Draw)" if hs == as_ else f"客勝 ({away_team})"
        return "贏" if selection.strip() == actual else "輸"
        
    elif "讓分盤" in playstyle:
        try:
            parts = selection.rsplit(" ", 1)
            team, hdcp = parts[0].strip(), float(parts[1])
            adj_hs = hs + hdcp if team == home_team else hs
            adj_as = as_ + hdcp if team == away_team else as_
            if team == home_team and adj_hs > adj_as: return "贏"
            if team == away_team and adj_as > adj_hs: return "贏"
            return "輸"
        except:
            return "輸"
            
    elif "大小球" in playstyle:
        total = hs + as_
        try:
            threshold = float(selection.split(" ")[-1])
            is_over = "大球" in selection
            if is_over and total > threshold: return "贏"
            if not is_over and total < threshold: return "贏"
            return "輸"
        except:
            return "輸"
            
    elif "正確比分" in playstyle:
        return "贏" if selection.strip() == f"{hs}:{as_}" else "輸"
        
    elif "首名進球" in playstyle:
        # 如果兩邊都填無，算贏
        if selection.strip() == "無" and first_goal.strip() == "無": return "贏"
        return "贏" if selection.strip() == first_goal.strip() else "輸"
        
    return "未開獎"

def get_parlay_combinations(n_legs, mode_str):
    """回傳複式過關的子注單組合 (回傳 index tuple 的 list)"""
    idx_list = list(range(n_legs))
    if mode_str == f"{n_legs}串1": return [tuple(idx_list)]
    
    if n_legs == 3:
        if mode_str == "3串3": return list(itertools.combinations(idx_list, 2))
        if mode_str == "3串4": return list(itertools.combinations(idx_list, 2)) + list(itertools.combinations(idx_list, 3))
        if mode_str == "3串7": return list(itertools.combinations(idx_list, 1)) + list(itertools.combinations(idx_list, 2)) + list(itertools.combinations(idx_list, 3))
    elif n_legs == 4:
        if mode_str == "4串6": return list(itertools.combinations(idx_list, 2))
        if mode_str == "4串11": return list(itertools.combinations(idx_list, 2)) + list(itertools.combinations(idx_list, 3)) + list(itertools.combinations(idx_list, 4))
        if mode_str == "4串15": return list(itertools.combinations(idx_list, 1)) + list(itertools.combinations(idx_list, 2)) + list(itertools.combinations(idx_list, 3)) + list(itertools.combinations(idx_list, 4))
    elif n_legs == 5:
        if mode_str == "5串10": return list(itertools.combinations(idx_list, 2))
        if mode_str == "5串26": return list(itertools.combinations(idx_list, 2)) + list(itertools.combinations(idx_list, 3)) + list(itertools.combinations(idx_list, 4)) + list(itertools.combinations(idx_list, 5))
        if mode_str == "5串31": return list(itertools.combinations(idx_list, 1)) + list(itertools.combinations(idx_list, 2)) + list(itertools.combinations(idx_list, 3)) + list(itertools.combinations(idx_list, 4)) + list(itertools.combinations(idx_list, 5))
    
    return [tuple(idx_list)]

def evaluate_bet_payout(bet_mode, stake, legs_info):
    """計算整張注單 (包含複式過關) 的最終派彩"""
    # 如果有任何一場未開獎，代表大單還不能結算
    if any(leg["status"] == "未開獎" for leg in legs_info):
        return "未開獎", 0.0

    if bet_mode == "單注":
        if legs_info[0]["status"] == "贏": return "贏", round(stake * legs_info[0]["odds"], 1)
        else: return "輸", 0.0

    n_legs = len(legs_info)
    combos = get_parlay_combinations(n_legs, bet_mode)
    num_units = len(combos)
    unit_stake = float(stake) / num_units
    total_win = 0.0

    for combo in combos:
        combo_status = [legs_info[i]["status"] for i in combo]
        if "輸" not in combo_status:  # 該子組合全過
            combo_odds = 1.0
            for i in combo: combo_odds *= legs_info[i]["odds"]
            total_win += unit_stake * combo_odds

    if total_win > 0:
        return "贏", round(total_win, 1)
    else:
        return "輸", 0.0

def calculate_next_stage_advancement(current_match_id, winner_name):
    """計算淘汰賽下一場的 ID 以及它是主隊還是客隊，並直接寫入 DataFrame"""
    if not winner_name or winner_name == "待定": return
    next_id = None
    is_home = True
    c_id = int(current_match_id)
    
    if 1 <= c_id <= 16:
        next_id = 17 + (c_id - 1) // 2
        is_home = (c_id % 2 != 0)
    elif 17 <= c_id <= 24:
        next_id = 25 + (c_id - 17) // 2
        is_home = (c_id % 2 != 0)
    elif 25 <= c_id <= 28:
        next_id = 29 + (c_id - 25) // 2
        is_home = (c_id % 2 != 0)
    elif 29 <= c_id <= 30:
        next_id = 31
        is_home = (c_id == 29)
        
    if next_id:
        global df_matches
        mask = df_matches['match_id'].astype(str) == str(next_id)
        if not df_matches[mask].empty:
            if is_home: df_matches.loc[mask, 'home_team'] = winner_name
            else: df_matches.loc[mask, 'away_team'] = winner_name
        else:
            new_m = { "match_id": str(next_id), "home_team": winner_name if is_home else "", "away_team": "" if is_home else winner_name, "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": "" }
            df_matches = pd.concat([df_matches, pd.DataFrame([new_m])], ignore_index=True)


# ==================== 3. Streamlit 頁面全局視覺設定 ====================
st.set_page_config(page_title="2026世界盃競猜系統", page_icon="🏆", layout="centered")

st.markdown("""
<style>
.stApp { background-color: #0c1328 !important; }
p, label, h1, h2, h3, h4, h5, h6 { color: #fef3c7 !important; font-weight: 700 !important; }
div[data-baseweb="select"] *, div[role="listbox"] *, ul[data-baseweb="menu"] *, input {
    color: #000000 !important; font-weight: 800 !important; }
.main-banner {
    background-color: #0c1328; padding: 15px; border-radius: 8px;
    border: 2px solid #fef3c7; text-align: center; margin-bottom: 20px; }
.main-title { font-size: 1.8rem; font-weight: 900; color: #fef3c7 !important; margin-bottom: 5px; } 
.sub-title { font-size: 1.1rem; color: #38bdf8 !important; font-weight: 800; }
.bracket-wrapper {
    display: flex; flex-direction: row; overflow-x: auto; padding: 20px 5px; gap: 25px; white-space: nowrap; }
.bracket-wrapper::-webkit-scrollbar { height: 6px; }
.bracket-wrapper::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
.bracket-round { display: flex; flex-direction: column; justify-content: space-around; gap: 20px; min-width: 230px; }
.round-title {
    font-size: 0.85rem; color: #fef3c7 !important; font-weight: 800; text-align: center;
    background: #1e293b; padding: 6px 12px; border-radius: 20px; border: 1px solid #475569;
    margin-bottom: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }
.match-card {
    background: linear-gradient(135deg, #131a35, #1e294b); border: 2px solid #38bdf8;
    border-radius: 12px; padding: 14px; box-shadow: 0 10px 20px rgba(0,0,0,0.4);
    display: flex; flex-direction: column; gap: 8px; }
.border-gray { border-color: #475569 !important; }
.final-card {
    border: 3px solid #fbbf24 !important; background: linear-gradient(135deg, #1c1917, #292524) !important;
    box-shadow: 0 0 15px rgba(251, 191, 36, 0.3); }
.match-header {
    display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem;
    color: #94a3b8 !important; border-bottom: 1px solid #334155; padding-bottom: 6px; font-weight: bold; }
.team-row { display: flex; justify-content: space-between; align-items: center; }
.team-name { font-size: 0.95rem; font-weight: 800; color: #f8fafc !important; }
.text-muted { color: #64748b !important; font-weight: 600; }
.team-score {
    font-size: 1.05rem; font-weight: 900; color: #fbbf24 !important; background: #0f172a;
    padding: 2px 10px; border-radius: 6px; min-width: 32px; text-align: center; border: 1px solid #334155; }
.status-badge { font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; font-weight: 900 !important; color: #ffffff !important; }
.status-badge.settled { background-color: #059669; }
.status-badge.live { background-color: #dc2626; animation: pulse 1.5s infinite; }
.status-badge.upcoming { background-color: #475569; }
.next-route {
    font-size: 0.75rem; color: #38bdf8 !important; background: #0f172a; padding: 4px 8px;
    border-radius: 6px; text-align: center; font-weight: bold; margin-top: 4px; border: 1px solid #1e293b; }
.final-winner { font-size: 0.8rem; color: #fbbf24 !important; text-align: center; font-weight: 900; letter-spacing: 0.1em; margin-top: 4px; }
@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.6; } 100% { opacity: 1; } }
</style>

<div class="main-banner">
<div class="main-title">🏆 2026 世界盃智能競猜中心</div>
<div class="sub-title">【智慧全自動對獎與容錯派彩精裝版】</div>
</div>
""", unsafe_allow_html=True)

is_admin = False
if "role" in st.query_params and st.query_params["role"] == "boss":
    is_admin = True

if is_admin:
    tabs = st.tabs(["📊 財富排行", "📅 賽況樹狀圖", "🎲 快速投注", "⚙️ 賽事管理後台", "🏁 完賽自動結算"])
else:
    tabs = st.tabs(["📊 財富排行", "📅 賽況樹狀圖", "🎲 快速投注"])

# ==================== 4. 提取與初始化資料 (修復點) ====================
df_users = read_sheet("Users")
if df_users.empty:
    df_users = pd.DataFrame({"user_id": [str(i) for i in range(1, 11)], "name": [f"同事 {i}" for i in range(1, 11)], "balance": [2000.0] * 10})
    save_sheet(df_users, "Users")

df_matches = read_sheet("Matches")
df_bets = read_sheet("Bets")
df_details = read_sheet("BetDetails")


# ==================== TAB 1: 資產排行榜 ====================
with tabs[0]:
    st.markdown("### 📈 財富龍虎榜")
    df_users["balance"] = pd.to_numeric(df_users["balance"], errors="coerce").fillna(0)
    df_ranking = df_users.sort_values(by="balance", ascending=False).reset_index(drop=True)
    if len(df_ranking) >= 3:
        st.markdown(f"#### 🥇 榜首：{df_ranking.iloc[0]['name']} — **{df_ranking.iloc[0]['balance']:.1f} pts**")
        st.markdown(f"#### 🥈 亞軍：{df_ranking.iloc[1]['name']} — **{df_ranking.iloc[1]['balance']:.1f} pts**")
        st.markdown(f"#### 🥉 季軍：{df_ranking.iloc[2]['name']} — **{df_ranking.iloc[2]['balance']:.1f} pts**")
    st.markdown("---")
    df_ranking.index = df_ranking.index + 1
    df_ranking = df_ranking.rename(columns={"name": "同事姓名", "balance": "積分餘額"})
    st.dataframe(df_ranking[["同事姓名", "積分餘額"]], use_container_width=True)

# ==================== TAB 2: 高級動態淘汰賽樹狀圖 ====================
with tabs[1]:
    st.markdown("### 🏆 32強淘汰賽動態晉級線路圖")
    def get_route_text(m_id):
        m_id = int(m_id)
        if 1 <= m_id <= 16: return f"➡️ 晉級：16強 (場次 {17 + (m_id - 1) // 2})"
        elif 17 <= m_id <= 24: return f"➡️ 晉級：八強 (場次 {25 + (m_id - 17) // 2})"
        elif 25 <= m_id <= 28: return f"➡️ 晉級：四強 (場次 {29 + (m_id - 25) // 2})"
        elif 29 <= m_id <= 30: return "🏆 前進總決賽 (場次 31)"
        elif m_id == 31: return "👑 爭奪世界之巔"
        else: return "➡️ 常規自訂賽事"

    def get_match_card_html(m_id, title_name):
        route_text = get_route_text(m_id)
        if df_matches.empty: return ""
        m_rows = df_matches[df_matches['match_id'].astype(str) == str(m_id)]
        if m_rows.empty: return ""
            
        row = m_rows.iloc[0]
        home = str(row['home_team']).strip() if str(row['home_team']).strip() != "" else "待定"
        away = str(row['away_team']).strip() if str(row['away_team']).strip() != "" else "待定"
        status = row['status']
        s_home = str(row['score_home']).strip() if (status == "已結算" and str(row['score_home']).strip() != "") else "-"
        s_away = str(row['score_away']).strip() if (status == "完賽" or status == "已結算" and str(row['score_away']).strip() != "") else "-"
        
        if status == "已結算": badge = '<span class="status-badge settled">已完賽</span>'
        elif status == "進行中": badge = '<span class="status-badge live">LIVE</span>'
        else: badge = '<span class="status-badge upcoming">未開賽</span>'
            
        is_final = (m_id == 31)
        card_class = "match-card final-card" if is_final else "match-card"
        if status == "未開賽" and m_id > 16: card_class += " border-gray"
            
        header_style = ' style="border-color: #fbbf24;"' if is_final else ''
        title_style = ' style="color:#fbbf24 !important; font-weight:900;"' if is_final else ''
        score_style = ' style="color:#fbbf24;"' if is_final else ''
        
        html = f"""<div class="{card_class}"><div class="match-header"{header_style}><span{title_style}>{title_name} (M{m_id})</span>{badge}</div><div class="team-row"><span class="team-name">🏠 {home}</span><span class="team-score"{score_style}>{s_home}</span></div><div class="team-row"><span class="team-name">✈️ {away}</span><span class="team-score"{score_style}>{s_away}</span></div>"""
        if str(row.get('first_goal_player', '')).strip(): html += f'<div style="font-size:0.75rem; color:#fef3c7;">⚽ 首名進球：{row["first_goal_player"]}</div>'
        if is_final: html += f'<div class="final-winner">{route_text}</div></div>'
        else: html += f'<div class="next-route">{route_text}</div></div>'
        return html

    ro32_html = "".join([get_match_card_html(i, "32強賽") for i in range(1, 17)])
    ro16_html = "".join([get_match_card_html(i, "十六強賽") for i in range(17, 25)])
    qf_html = "".join([get_match_card_html(i, "半準決賽") for i in range(25, 29)])
    sf_html = "".join([get_match_card_html(i, "準決賽") for i in range(29, 31)])
    final_html = get_match_card_html(31, "🏆 FINAL 總決賽")

    bracket_html = f"""<div class="bracket-wrapper">{"<div class='bracket-round'><div class='round-title'>⚔️ 32強淘汰賽</div>" + ro32_html + "</div>" if ro32_html else ""}{"<div class='bracket-round'><div class='round-title'>🔥 16強淘汰賽</div>" + ro16_html + "</div>" if ro16_html else ""}{"<div class='bracket-round'><div class='round-title'>⚡ 八強半準決賽</div>" + qf_html + "</div>" if qf_html else ""}{"<div class='bracket-round'><div class='round-title'>🌟 四強準決賽</div>" + sf_html + "</div>" if sf_html else ""}{"<div class='bracket-round'><div class='round-title' style='color:#fbbf24;'>👑 冠軍總決賽</div>" + final_html + "</div>" if final_html else ""}</div>"""
    st.markdown(bracket_html, unsafe_allow_html=True)
    
    other_matches = df_matches[pd.to_numeric(df_matches['match_id'], errors='coerce') > 31]
    if not other_matches.empty:
        st.markdown("### 📅 其他加開自訂賽事")
        for _, r in other_matches.iterrows(): st.info(f" 場次 ID:{r['match_id']} | 🏠 {r['home_team']} VS ✈️ {r['away_team']} | 狀態：{r['status']} (比分：{r['score_home'] or '-'}:{r['score_away'] or '-'})")

# ==================== TAB 3: 賽事投注中心 ====================
with tabs[2]:
    st.markdown("### 🎲 員工自選賠率下注區")
    open_matches = df_matches[df_matches['status'] != '已結算']
    
    with st.container(border=True):
        active_user = st.selectbox("👤 請選擇你的名字（身分）：", df_users["name"].tolist())
        user_row = df_users[df_users["name"] == active_user].iloc[0]
        u_id = clean_id(user_row["user_id"])
        st.markdown(f"### 💰 你的可用積分：**{float(user_row['balance']):.1f} pts**")
        
    with st.expander("📜 查看我的歷史投注紀錄與派彩狀態", expanded=False):
        if df_bets.empty or df_details.empty: st.info("您目前沒有任何下注歷史。")
        else:
            my_bets = df_bets[df_bets["user_id"].astype(str) == str(u_id)]
            if my_bets.empty: st.info("您目前沒有任何下注歷史。")
            else:
                user_history = []
                for _, b_row in my_bets.iterrows():
                    b_id = b_row["bet_id"]
                    b_details = df_details[df_details["bet_id"].astype(str) == str(b_id)]
                    legs_summary = []
                    for _, d_row in b_details.iterrows():
                        m_row = df_matches[df_matches["match_id"].astype(str) == str(d_row["match_id"])]
                        m_text = f"{m_row.iloc[0]['home_team']} VS {m_row.iloc[0]['away_team']}" if not m_row.empty else f"場次{d_row['match_id']}"
                        p_style = d_row.get('playstyle', '未填')
                        legs_summary.append(f"【{m_text}】[{p_style}] {d_row['selection']}(@{d_row['odds_value']}) [{d_row['status']}]")
                    
                    user_history.append({"單號": b_id, "模式": b_row["bet_mode"], "詳細投注內容": " ✖️ ".join(legs_summary), "本金": f"{b_row['stake']} pts", "總狀態": b_row["status"], "已獲積分": f"{b_row['win_amount']} pts"})
                st.dataframe(pd.DataFrame(user_history), use_container_width=True, hide_index=True)
                
    st.markdown("---")
    if df_matches.empty or open_matches.empty: st.markdown("#### 📭 目前暫時沒有進行中或開放下注的賽事。")
    else:
        bet_mode = st.radio("🎯 選擇下注模式：", ["單注下注", "過關串關"], horizontal=True)
        
        def render_playstyle_selector(m_row, key_suffix):
            h = m_row['home_team']
            a = m_row['away_team']
            p_style = st.selectbox("🎰 選擇玩法種類", ["① 獨贏盤 (不讓分)", "② 讓分盤", "③ 大小球 (總進球)", "④ 正確比分 (波膽)", "⑤ 首名進球球員"], key=f"ps_{key_suffix}")
            
            if p_style == "① 獨贏盤 (不讓分)": sel = st.selectbox("🎯 投注選項", [f"主勝 ({h})", "和局 (Draw)", f"客勝 ({a})"], key=f"sel_{key_suffix}")
            elif p_style == "② 讓分盤": sel = st.text_input(f"✍️ 輸入讓分內容 (例如: {h} -1.5 或 {a} +0.5)", value=f"{h} -0.5", key=f"sel_{key_suffix}")
            elif p_style == "③ 大小球 (總進球)":
                bs = st.selectbox("🎯 大小球預測", ["大球 (Over)", "小球 (Under)"], key=f"sel_bs_{key_suffix}")
                th = st.text_input("📈 輸入大小球門檻 (例如: 2.5 或 3.5)", value="2.5", key=f"sel_th_{key_suffix}")
                sel = f"{bs} {th}"
            elif p_style == "④ 正確比分 (波膽)": sel = st.text_input("✍️ 輸入精確比分 (例如: 2:1 或 0:0)", value="2:1", key=f"sel_{key_suffix}")
            else: sel = st.text_input("✍️ 輸入預測首名進球球員名字", value="梅西", key=f"sel_{key_suffix}")
            return p_style, sel

        if bet_mode == "單注下注":
            with st.container(border=True):
                selected_match = st.selectbox("⚽ 選擇比賽場次：", open_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (ID:{r['match_id']})", axis=1))
                m_id = clean_id(selected_match.split("ID:")[-1].replace(")", ""))
                target_m_row = df_matches[df_matches['match_id'].astype(str) == str(m_id)].iloc[0]
                chosen_style, chosen_selection = render_playstyle_selector(target_m_row, "single")
                custom_odds = st.number_input("📈 自行填入外部商業盤口賠率：", min_value=1.01, value=2.00, step=0.01, format="%.2f")
                stake = st.number_input("💵 輸入投注本金：", min_value=1.0, max_value=float(user_row['balance']), value=100.0, step=50.0)
                
                if st.button("📱 確認送出單注", type="primary", use_container_width=True):
                    df_users["balance"] = pd.to_numeric(df_users["balance"], errors="coerce")
                    df_users.loc[df_users["user_id"].astype(str) == str(u_id), "balance"] -= stake
                    save_sheet(df_users, "Users")
                    new_bet_id = str(int(pd.to_numeric(df_bets["bet_id"], errors='coerce').max() + 1)) if not df_bets.empty else "1"
                    new_bet = pd.DataFrame([{"bet_id": new_bet_id, "user_id": u_id, "bet_mode": "單注", "stake": stake, "status": "未開獎", "win_amount": 0.0}])
                    df_bets = pd.concat([df_bets, new_bet], ignore_index=True)
                    save_sheet(df_bets, "Bets")
                    new_detail_id = str(int(pd.to_numeric(df_details["detail_id"], errors='coerce').max() + 1)) if not df_details.empty else "1"
                    new_detail = pd.DataFrame([{"detail_id": new_detail_id, "bet_id": new_bet_id, "match_id": m_id, "playstyle": chosen_style, "selection": chosen_selection.strip(), "odds_value": custom_odds, "status": "未開獎"}])
                    df_details = pd.concat([df_details, new_detail], ignore_index=True)
                    save_sheet(df_details, "BetDetails")
                    st.toast(f"✅ 單注下單成功！扣除 {stake} pts", icon="🎉")
                    time.sleep(1)
                    st.rerun()
        else:
            st.markdown("#### 🔗 馬會標準過關組合")
            selected_matches = st.multiselect("⚽ 請挑選 2 場以上的比賽進行過關 (最多支援5場)：", open_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (ID:{r['match_id']})", axis=1))
            n_legs = len(selected_matches)
            
            if n_legs < 2: st.warning("⚠️ 串關模式至少需要勾選 2 場以上的不同賽事。")
            elif n_legs > 5: st.error("❌ 目前最高僅支援 5 場賽事串關。")
            else:
                def get_available_formulas(n):
                    formulas = [f"{n}串1"]
                    if n == 3: formulas.extend(["3串3", "3串4", "3串7"])
                    elif n == 4: formulas.extend(["4串6", "4串11", "4串15"])
                    elif n == 5: formulas.extend(["5串10", "5串26", "5串31"])
                    return formulas
                    
                sel_formula = st.selectbox("🎯 選擇過關公式：", get_available_formulas(n_legs))
                legs_data = []
                for idx, mat_str in enumerate(selected_matches):
                    m_id = clean_id(mat_str.split("ID:")[-1].replace(")", ""))
                    target_m_row = df_matches[df_matches['match_id'].astype(str) == str(m_id)].iloc[0]
                    with st.container(border=True):
                        st.markdown(f"**🔥 串關第 {idx+1} 關：{target_m_row['home_team']} VS {target_m_row['away_team']}**")
                        chosen_style, chosen_selection = render_playstyle_selector(target_m_row, f"parlay_{m_id}_{idx}")
                        odd = st.number_input(f"填入此場盤口賠率", min_value=1.01, value=2.00, step=0.01, format="%.2f", key=f"parlay_odd_{m_id}_{idx}")
                        legs_data.append({"match_id": m_id, "playstyle": chosen_style, "selection": chosen_selection, "odds_value": odd})
                
                stake = st.number_input("💵 串關投注總本金：", min_value=1.0, max_value=float(user_row['balance']), value=100.0, step=50.0)
                
                if st.button("🚀 確認執行過關下單", type="primary", use_container_width=True):
                    df_users["balance"] = pd.to_numeric(df_users["balance"], errors="coerce")
                    df_users.loc[df_users["user_id"].astype(str) == str(u_id), "balance"] -= stake
                    save_sheet(df_users, "Users")
                    new_bet_id = str(int(pd.to_numeric(df_bets["bet_id"], errors='coerce').max() + 1)) if not df_bets.empty else "1"
                    new_bet = pd.DataFrame([{"bet_id": new_bet_id, "user_id": u_id, "bet_mode": sel_formula, "stake": stake, "status": "未開獎", "win_amount": 0.0}])
                    df_bets = pd.concat([df_bets, new_bet], ignore_index=True)
                    save_sheet(df_bets, "Bets")
                    for leg in legs_data:
                        new_detail_id = str(int(pd.to_numeric(df_details["detail_id"], errors='coerce').max() + 1)) if not df_details.empty else "1"
                        new_detail = pd.DataFrame([{"detail_id": new_detail_id, "bet_id": new_bet_id, "match_id": leg["match_id"], "playstyle": leg["playstyle"], "selection": leg["selection"].strip(), "odds_value": leg["odds_value"], "status": "未開獎"}])
                        df_details = pd.concat([df_details, new_detail], ignore_index=True)
                    save_sheet(df_details, "BetDetails")
                    st.toast("🎉 串關下單成功！", icon="🎉")
                    time.sleep(1)
                    st.rerun()

# ==================== ⚙️ TAB 4: 管理後台 ====================
if is_admin:
    with tabs[3]:
        st.markdown("### ⚙️ 賽事名單增刪管理後台")
        with st.container(border=True):
            manage_mode = st.radio("🛠️ 請選取後台管理動作：", ["✏️ 編輯或刪除現有賽事", "➕ 手動建立新賽事項目"], horizontal=True)
            if manage_mode == "✏️ 編輯或刪除現有賽事":
                if df_matches.empty: st.warning("資料庫中目前沒有任何賽事。")
                else:
                    match_list = df_matches.apply(lambda r: f"ID:{r['match_id']} | {r['home_team']} VS {r['away_team']} ({r['status']})", axis=1).tolist()
                    sel_match_str = st.selectbox("🔍 選擇要操作的賽事", match_list)
                    sel_m_id = str(sel_match_str.split("ID:")[1].split(" |")[0])
                    target_row = df_matches[df_matches['match_id'].astype(str) == sel_m_id].iloc[0]
                    with st.form("edit_match_form"):
                        c1, c2, c3 = st.columns(3)
                        new_home = c1.text_input("🏠 主隊名稱", value=str(target_row['home_team']))
                        new_away = c2.text_input("✈️ 客隊名稱", value=str(target_row['away_team']))
                        new_status = c3.selectbox("📊 賽事狀態", ["未開賽", "進行中"], index=0)
                        col_btn1, col_btn2 = st.columns(2)
                        if col_btn1.form_submit_button("💾 儲存修改基本資料", type="primary", use_container_width=True):
                            df_matches.loc[df_matches['match_id'].astype(str) == sel_m_id, 'home_team'] = new_home.strip()
                            df_matches.loc[df_matches['match_id'].astype(str) == sel_m_id, 'away_team'] = new_away.strip()
                            df_matches.loc[df_matches['match_id'].astype(str) == sel_m_id, 'status'] = new_status
                            save_sheet(df_matches, "Matches")
                            st.toast("✅ 賽事已儲存！", icon="✅")
                            time.sleep(1); st.rerun()
                        if col_btn2.form_submit_button("🗑️ 徹底刪除此場賽事", use_container_width=True):
                            df_matches = df_matches[df_matches['match_id'].astype(str) != sel_m_id]
                            save_sheet(df_matches, "Matches")
                            st.toast("🗑️ 賽事已移除！", icon="✅")
                            time.sleep(1); st.rerun()
            elif manage_mode == "➕ 手動建立新賽事項目":
                with st.form("add_match_form"):
                    custom_id = st.number_input("設定場次 ID", min_value=1, value=int(pd.to_numeric(df_matches['match_id'], errors='coerce').max() + 1) if not df_matches.empty else 1)
                    c3, c4 = st.columns(2)
                    add_home = c3.text_input("🏠 主隊名稱")
                    add_away = c4.text_input("✈️ 客隊名稱")
                    if st.form_submit_button("➕ 發布新賽事", type="primary", use_container_width=True):
                        if not df_matches[df_matches['match_id'].astype(str) == str(custom_id)].empty: st.error("❌ ID 已經存在")
                        else:
                            new_m = pd.DataFrame([{"match_id": str(custom_id), "home_team": add_home.strip(), "away_team": add_away.strip(), "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""}])
                            df_matches = pd.concat([df_matches, new_m], ignore_index=True)
                            save_sheet(df_matches, "Matches")
                            st.toast("✅ 成功新增賽事！", icon="🎉")
                            time.sleep(1); st.rerun()

# ==================== 🏁 TAB 5: 完賽智慧全自動結算中心 ====================
if is_admin:
    with tabs[4]:
        st.markdown("### 🏁 賽果登錄與全自動對獎中心")
        st.info("💡 **全新智慧結算**：您現在只需輸入最終比分，系統將會**自動校對**所有員工的單注與過關盤，並進行**過關容錯派彩計算**，無需再手動點選輸贏！")
        
        unsettled_matches = df_matches[df_matches["status"] != "已結算"]
        if unsettled_matches.empty:
            st.markdown("### 🎉 目前所有賽事皆已順利結算完畢！")
        else:
            with st.container(border=True):
                sel_unsettled = st.selectbox("📌 選擇準備要結算賽果的完賽場次：", unsettled_matches.apply(lambda r: f"場次ID:{r['match_id']} | {r['home_team']} VS {r['away_team']}", axis=1))
                settle_m_id = str(sel_unsettled.split("場次ID:")[1].split(" |")[0])
                curr_match_data = df_matches[df_matches["match_id"].astype(str) == settle_m_id].iloc[0]
                
                st.markdown("#### 1. 登錄比賽結束實際結果（系統將以此自動對獎）：")
                c_sc1, c_sc2, c_sc3 = st.columns(3)
                sc_home = c_sc1.number_input("🏠 主隊最終進球數", min_value=0, value=0)
                sc_away = c_sc2.number_input("✈️ 客隊最終進球數", min_value=0, value=0)
                fg_player = c_sc3.text_input("⚽ 首名進球球員名字（若無進球請填：無）", value="無")
                
                st.markdown("#### 🏆 2. 設定此場淘汰賽最終晉級者（樹狀圖前推用）：")
                team_choices = []
                if str(curr_match_data['home_team']).strip(): team_choices.append(str(curr_match_data['home_team']))
                if str(curr_match_data['away_team']).strip(): team_choices.append(str(curr_match_data['away_team']))
                if not team_choices: team_choices = ["主隊", "客隊"]
                advance_winner = st.selectbox("🥇 請勾選實際獲勝晉級的隊伍（防範踢到PK賽）：", team_choices)
                
                st.markdown("---")
                
                if st.button("📊 一鍵自動對獎、計算過關容錯並派彩", type="primary", use_container_width=True):
                    with st.spinner('引擎運算中：自動對獎與過關容錯派彩...'):
                        
                        # 1. 寫入賽果並關閉比賽
                        df_matches.loc[df_matches["match_id"].astype(str) == settle_m_id, "status"] = "已結算"
                        df_matches.loc[df_matches["match_id"].astype(str) == settle_m_id, "score_home"] = str(sc_home)
                        df_matches.loc[df_matches["match_id"].astype(str) == settle_m_id, "score_away"] = str(sc_away)
                        df_matches.loc[df_matches["match_id"].astype(str) == settle_m_id, "first_goal_player"] = fg_player.strip()
                        
                        # 2. 自動前推晉級
                        if int(settle_m_id) <= 30:
                            calculate_next_stage_advancement(settle_m_id, advance_winner)
                            
                        # 3. 自動對獎此場比賽的所有注單明細 (BetDetails)
                        if not df_details.empty:
                            target_mask = df_details["match_id"].astype(str) == settle_m_id
                            for idx, row in df_details[target_mask].iterrows():
                                if row["status"] == "未開獎":
                                    res = auto_evaluate_leg(row["playstyle"], row["selection"], sc_home, sc_away, fg_player, curr_match_data['home_team'], curr_match_data['away_team'])
                                    df_details.loc[idx, "status"] = res
                        save_sheet(df_details, "BetDetails")
                        save_sheet(df_matches, "Matches")
                        
                        # 4. 掃描總注單，執行包含「過關容錯」在內的最終派彩結算
                        if not df_bets.empty:
                            df_users["balance"] = pd.to_numeric(df_users["balance"], errors="coerce")
                            for idx, bet in df_bets[df_bets["status"] == "未開獎"].iterrows():
                                b_id = bet["bet_id"]
                                bet_legs = df_details[df_details["bet_id"].astype(str) == str(b_id)]
                                
                                # 必須等該大單的【所有比賽】都結算，才進行最終計算
                                if not any(bet_legs["status"] == "未開獎"):
                                    legs_info = [{"status": row["status"], "odds": float(row["odds_value"])} for _, row in bet_legs.iterrows()]
                                    
                                    new_status, win_amt = evaluate_bet_payout(bet["bet_mode"], bet["stake"], legs_info)
                                    
                                    df_bets.loc[idx, "status"] = new_status
                                    df_bets.loc[idx, "win_amount"] = win_amt
                                    
                                    if new_status == "贏" and win_amt > 0:
                                        u_id = str(bet["user_id"]).strip()
                                        df_users.loc[df_users["user_id"].astype(str) == u_id, "balance"] += win_amt
                                        
                            save_sheet(df_bets, "Bets")
                            save_sheet(df_users, "Users")
                            
                    st.success(f"🎉 自動結算完美執行！已成功對獎所有相關單注與過關單，並依容錯率發放獎金！晉級隊伍【{advance_winner}】也已送入下一輪。")
                    time.sleep(2)
                    st.rerun()
