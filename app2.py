import streamlit as st
import pandas as pd
import time
import itertools
import gspread
from google.oauth2.service_account import Credentials

# ==================== 0. 輔助函數與預設資料 ====================
def clean_id(x):
    """防止 Pandas 從 Google Sheets 讀取數字變成 1.0 的型態問題"""
    s = str(x).strip()
    if s.endswith('.0'): return s[:-2]
    return s

# 32強 (Round of 32) 完整初始賽程
INITIAL_MATCHES = [
    {"match_id": "1", "home_team": "Germany", "away_team": "Paraguay", "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "2", "home_team": "France", "away_team": "Sweden", "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "3", "home_team": "South Africa", "away_team": "Canada", "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "4", "home_team": "Netherlands", "away_team": "Morocco", "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "5", "home_team": "Portugal", "away_team": "Croatia", "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "6", "home_team": "Spain", "away_team": "Austria", "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "7", "home_team": "United States", "away_team": "Bosnia/Herz.", "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "8", "home_team": "Belgium", "away_team": "Senegal", "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "9", "home_team": "Brazil", "away_team": "Japan", "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "10", "home_team": "Ivory Coast", "away_team": "Norway", "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "11", "home_team": "Mexico", "away_team": "Ecuador", "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "12", "home_team": "England", "away_team": "D.R. Congo", "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "13", "home_team": "Argentina", "away_team": "Cape Verde", "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "14", "home_team": "Australia", "away_team": "Egypt", "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "15", "home_team": "Switzerland", "away_team": "Algeria", "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "16", "home_team": "Colombia", "away_team": "Ghana", "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""}
]
for i in range(17, 32):
    INITIAL_MATCHES.append({"match_id": str(i), "home_team": "", "away_team": "", "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""})

# ==================== 1. 初始化 Google Sheets 資料庫 ====================
SHEET_URL = "https://docs.google.com/spreadsheets/d/1l7LZxRIv-WeApoVloQv0sLxFagDHclyeNJiRffTbB1E/edit?gid=0#gid=0"

@st.cache_resource
def get_spreadsheet_client():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    skey = dict(st.secrets["gcp_service_account"])
    credentials = Credentials.from_service_account_info(skey, scopes=scopes)
    return gspread.authorize(credentials).open_by_url(SHEET_URL)

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
        if not data: return pd.DataFrame(columns=columns_map.get(sheet_name, []))
        df = pd.DataFrame(data)
        
        for col in ["user_id", "match_id", "bet_id", "detail_id"]:
            if col in df.columns: df[col] = df[col].apply(clean_id)
            
        if sheet_name == "Matches":
            for col in ["score_home", "score_away", "first_goal_player", "status"]:
                if col in df.columns: df[col] = df[col].astype(str).replace("nan", "")
        return df
    except Exception as e:
        st.error(f"❌ 讀取【{sheet_name}】失敗，請稍候重整網頁。詳細: {e}")
        st.stop()

def save_sheet(df, sheet_name):
    try:
        worksheet = sh.worksheet(sheet_name)
        worksheet.clear()
        columns_map = {
            "Users": ["user_id", "name", "balance"],
            "Matches": ["match_id", "home_team", "away_team", "status", "score_home", "score_away", "first_goal_player"],
            "Bets": ["bet_id", "user_id", "bet_mode", "stake", "status", "win_amount"],
            "BetDetails": ["detail_id", "bet_id", "match_id", "playstyle", "selection", "odds_value", "status"]
        }
        
        if not df.empty:
            if sheet_name in columns_map:
                valid_cols = [c for c in columns_map[sheet_name] if c in df.columns]
                df = df[valid_cols]
                
            df_to_save = df.fillna("")
            df_to_save = df_to_save.astype(str)
            
            data_to_write = [df_to_save.columns.values.tolist()] + df_to_save.values.tolist()
            try:
                worksheet.update(values=data_to_write, range_name="A1")
            except TypeError:
                worksheet.update(data_to_write, "A1")
        else:
            headers = columns_map.get(sheet_name, df.columns.values.tolist())
            try:
                worksheet.update(values=[headers], range_name="A1")
            except TypeError:
                worksheet.update([headers], "A1")
                
        st.cache_data.clear()
    except Exception as e:
        st.error(f"❌ 寫入【{sheet_name}】失敗。詳細錯誤代碼：{str(e)}")
        st.stop()

# ==================== 2. 全自動對獎與過關拆單引擎 ====================
def auto_evaluate_leg(playstyle, selection, hs, as_, first_goal, home_team, away_team):
    """根據輸入的比分，自動判斷單注輸贏"""
    try: hs, as_ = int(hs), int(as_)
    except ValueError: return "未開獎"

    if "獨贏盤" in playstyle:
        actual = f"主勝 ({home_team})" if hs > as_ else "和局 (Draw)" if hs == as_ else f"客勝 ({away_team})"
        return "贏" if selection.strip() == actual else "輸"
    elif "讓分盤" in playstyle:
        try:
            team, hdcp = selection.rsplit(" ", 1)[0].strip(), float(selection.rsplit(" ", 1)[1])
            adj_hs = hs + hdcp if team == home_team else hs
            adj_as = as_ + hdcp if team == away_team else as_
            if team == home_team and adj_hs > adj_as: return "贏"
            if team == away_team and adj_as > adj_hs: return "贏"
            return "輸"
        except: return "輸"
    elif "大小球" in playstyle:
        total = hs + as_
        try:
            threshold = float(selection.split(" ")[-1])
            is_over = "大球" in selection
            return "贏" if (is_over and total > threshold) or (not is_over and total < threshold) else "輸"
        except: return "輸"
    elif "正確比分" in playstyle:
        return "贏" if selection.strip() == f"{hs}:{as_}" else "輸"
    elif "首名進球" in playstyle:
        if selection.strip() == "無" and first_goal.strip() == "無": return "贏"
        return "贏" if selection.strip() == first_goal.strip() else "輸"
    return "未開獎"

def get_parlay_combinations(n_legs, mode_str):
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
    if any("未開" in leg["status"] or "未开" in leg["status"] for leg in legs_info):
        return "未開獎", 0.0
    
    if bet_mode == "單注":
        if "贏" in legs_info[0]["status"] or "赢" in legs_info[0]["status"]: 
            return "贏", round(stake * legs_info[0]["odds"], 1)
        else: 
            return "輸", 0.0

    n_legs = len(legs_info)
    combos = get_parlay_combinations(n_legs, bet_mode)
    unit_stake = float(stake) / len(combos)
    total_win = 0.0

    for combo in combos:
        combo_status = [legs_info[i]["status"] for i in combo]
        if not any("輸" in s or "输" in s for s in combo_status):
            c_odds = 1.0
            for i in combo: 
                c_odds *= legs_info[i]["odds"]
            total_win += unit_stake * c_odds

    return ("贏", round(total_win, 1)) if total_win > 0 else ("輸", 0.0)

# ==================== 3. 系統初始化與 UI 設定 ====================
st.set_page_config(page_title="2026世界盃競猜系統", page_icon="🏆", layout="centered")
st.markdown("""
<style>
.stApp { background-color: #0c1328 !important; }
p, label, h1, h2, h3, h4, h5, h6 { color: #fef3c7 !important; font-weight: 700 !important; }
div[data-baseweb="select"] *, div[role="listbox"] *, ul[data-baseweb="menu"] *, input { color: #000000 !important; font-weight: 800 !important; }
.main-banner { background-color: #0c1328; padding: 15px; border-radius: 8px; border: 2px solid #fef3c7; text-align: center; margin-bottom: 20px; }
.main-title { font-size: 1.8rem; font-weight: 900; color: #fef3c7 !important; margin-bottom: 5px; } 
.bracket-wrapper { display: flex; flex-direction: row; overflow-x: auto; padding: 20px 5px; gap: 25px; white-space: nowrap; }
.bracket-wrapper::-webkit-scrollbar { height: 6px; }
.bracket-wrapper::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
.bracket-round { display: flex; flex-direction: column; justify-content: space-around; gap: 20px; min-width: 230px; }
.round-title { font-size: 0.85rem; color: #fef3c7 !important; font-weight: 800; text-align: center; background: #1e293b; padding: 6px 12px; border-radius: 20px; border: 1px solid #475569; margin-bottom: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }
.match-card { background: linear-gradient(135deg, #131a35, #1e294b); border: 2px solid #38bdf8; border-radius: 12px; padding: 14px; box-shadow: 0 10px 20px rgba(0,0,0,0.4); display: flex; flex-direction: column; gap: 8px; }
.border-gray { border-color: #475569 !important; }
.final-card { border: 3px solid #fbbf24 !important; background: linear-gradient(135deg, #1c1917, #292524) !important; box-shadow: 0 0 15px rgba(251, 191, 36, 0.3); }
.match-header { display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; color: #94a3b8 !important; border-bottom: 1px solid #334155; padding-bottom: 6px; font-weight: bold; }
.team-row { display: flex; justify-content: space-between; align-items: center; }
.team-name { font-size: 0.95rem; font-weight: 800; color: #f8fafc !important; }
.team-score { font-size: 1.05rem; font-weight: 900; color: #fbbf24 !important; background: #0f172a; padding: 2px 10px; border-radius: 6px; min-width: 32px; text-align: center; border: 1px solid #334155; }
.status-badge { font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; font-weight: 900 !important; color: #ffffff !important; }
.status-badge.settled { background-color: #059669; }
.status-badge.live { background-color: #dc2626; animation: pulse 1.5s infinite; }
.status-badge.upcoming { background-color: #475569; }
.next-route { font-size: 0.75rem; color: #38bdf8 !important; background: #0f172a; padding: 4px 8px; border-radius: 6px; text-align: center; font-weight: bold; margin-top: 4px; border: 1px solid #1e293b; }
@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.6; } 100% { opacity: 1; } }
</style>
<div class="main-banner"><div class="main-title">🏆 2026 世界盃智能競猜中心</div><div class="sub-title" style="color:#38bdf8;">【官方 32 強賽程與繁體極淨對獎版】</div></div>
""", unsafe_allow_html=True)

is_admin = ("role" in st.query_params and st.query_params["role"] == "boss")
tabs = st.tabs(["📊 財富排行", "📅 賽況樹狀圖", "🎲 快速投注", "⚙️ 賽事管理後台", "📝 投注管理後台", "🏁 完賽自動結算"] if is_admin else ["📊 財富排行", "📅 賽況樹狀圖", "🎲 快速投注"])

df_users = read_sheet("Users")
if df_users.empty:
    df_users = pd.DataFrame({"user_id": [str(i) for i in range(1, 11)], "name": [f"同事 {i}" for i in range(1, 11)], "balance": [2000.0] * 10})
    save_sheet(df_users, "Users")

df_matches = read_sheet("Matches")
if df_matches.empty:
    df_matches = pd.DataFrame(INITIAL_MATCHES)
    save_sheet(df_matches, "Matches")

df_bets = read_sheet("Bets")
df_details = read_sheet("BetDetails")

# ==================== TAB 1: 排行榜 ====================
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
    st.dataframe(df_ranking.rename(columns={"name": "同事姓名", "balance": "積分餘額"})[["同事姓名", "積分餘額"]], use_container_width=True)

# ==================== TAB 2: 動態樹狀圖 ====================
with tabs[1]:
    st.markdown("### 🏆 32強淘汰賽動態晉級線路圖")
    def get_route_text(m_id):
        m = int(m_id)
        if 1 <= m <= 16: return f"➡️ 晉級：16強 (場次 {17 + (m - 1) // 2})"
        elif 17 <= m <= 24: return f"➡️ 晉級：八強 (場次 {25 + (m - 17) // 2})"
        elif 25 <= m <= 28: return f"➡️ 晉級：四強 (場次 {29 + (m - 25) // 2})"
        elif 29 <= m <= 30: return "🏆 前進總決賽 (場次 31)"
        elif m == 31: return "👑 爭奪世界之巔"
        return "➡️ 常規自訂賽事"

    def get_match_card_html(m_id, title_name):
        m_rows = df_matches[df_matches['match_id'].astype(str) == str(m_id)]
        if m_rows.empty: return ""
        row = m_rows.iloc[0]
        h = str(row['home_team']).strip() or "待定"
        a = str(row['away_team']).strip() or "待定"
        s = row['status']
        s_h = str(row['score_home']).strip() if "結算" in s else "-"
        s_a = str(row['score_away']).strip() if "結算" in s else "-"
        
        badge = f'<span class="status-badge {"settled" if "結算" in s else "live" if s=="進行中" else "upcoming"}">{s if "結算" not in s else "已完賽"}</span>'
        cls = "match-card final-card" if m_id == 31 else "match-card"
        if s == "未開賽" and m_id > 16: cls += " border-gray"
        
        h_style = ' style="border-color: #fbbf24;"' if m_id == 31 else ''
        t_style = ' style="color:#fbbf24 !important; font-weight:900;"' if m_id == 31 else ''
        html = f"""<div class="{cls}"><div class="match-header"{h_style}><span{t_style}>{title_name} (M{m_id})</span>{badge}</div><div class="team-row"><span class="team-name">🏠 {h}</span><span class="team-score">{s_h}</span></div><div class="team-row"><span class="team-name">✈️ {a}</span><span class="team-score">{s_a}</span></div>"""
        if str(row.get('first_goal_player', '')).strip(): html += f'<div style="font-size:0.75rem; color:#fef3c7;">⚽ 首名進球：{row["first_goal_player"]}</div>'
        html += f'<div class="{"final-winner" if m_id==31 else "next-route"}">{get_route_text(m_id)}</div></div>'
        return html

    bracket_html = f"""<div class="bracket-wrapper">
    {"<div class='bracket-round'><div class='round-title'>⚔️ 32強賽</div>" + "".join([get_match_card_html(i, "32強") for i in range(1, 17)]) + "</div>"}
    {"<div class='bracket-round'><div class='round-title'>🔥 16強賽</div>" + "".join([get_match_card_html(i, "16強") for i in range(17, 25)]) + "</div>"}
    {"<div class='bracket-round'><div class='round-title'>⚡ 半準決賽</div>" + "".join([get_match_card_html(i, "八強") for i in range(25, 29)]) + "</div>"}
    {"<div class='bracket-round'><div class='round-title'>🌟 準決賽</div>" + "".join([get_match_card_html(i, "四強") for i in range(29, 31)]) + "</div>"}
    {"<div class='bracket-round'><div class='round-title' style='color:#fbbf24;'>👑 總決賽</div>" + get_match_card_html(31, "FINAL") + "</div>"}
    </div>"""
    st.markdown(bracket_html, unsafe_allow_html=True)

# ==================== TAB 3: 投注中心 ====================
with tabs[2]:
    st.markdown("### 🎲 員工自選賠率下注區")
    open_matches = df_matches[df_matches['status'].isin(['未開賽', '進行中'])]
    
    with st.container(border=True):
        active_user = st.selectbox("👤 請選擇身分：", df_users["name"].tolist())
        user_row = df_users[df_users["name"] == active_user].iloc[0]
        u_id = clean_id(user_row["user_id"])
        st.markdown(f"### 💰 你的可用積分：**{float(user_row['balance']):.1f} pts**")
        
    with st.expander("📜 查看歷史投注紀錄", expanded=False):
        my_bets = df_bets[df_bets["user_id"].astype(str) == str(u_id)] if not df_bets.empty else pd.DataFrame()
        if my_bets.empty: st.info("無下注歷史。")
        else:
            history = []
            for _, b in my_bets.iterrows():
                legs = df_details[df_details["bet_id"].astype(str) == str(b["bet_id"])]
                summ = [f"M{d['match_id']} [{d.get('playstyle', '')}] {d['selection']}(@{d['odds_value']}) [{d['status']}]" for _, d in legs.iterrows()]
                history.append({"單號": b["bet_id"], "模式": b["bet_mode"], "內容": " ✖️ ".join(summ), "本金": f"{b['stake']}", "狀態": b["status"], "贏得": f"{b['win_amount']}"})
            st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)
                
    st.markdown("---")
    if open_matches.empty: st.markdown("#### 📭 無開放賽事。")
    else:
        bet_mode = st.radio("🎯 選擇下注模式：", ["單注下注", "過關串關"], horizontal=True)
        
        def render_ps(m_row, key):
            h, a = m_row['home_team'], m_row['away_team']
            ps = st.selectbox("🎰 選擇玩法", ["① 獨贏盤", "② 讓分盤", "③ 大小球", "④ 正確比分", "⑤ 首名進球"], key=f"ps_{key}")
            if "獨贏盤" in ps: sel = st.selectbox("🎯 選項", [f"主勝 ({h})", "和局 (Draw)", f"客勝 ({a})"], key=f"sel_{key}")
            elif "讓分盤" in ps: sel = st.text_input("✍️ 讓分 (例: Brazil -1.5)", value=f"{h} -0.5", key=f"sel_{key}")
            elif "大小球" in ps: sel = f"{st.selectbox('🎯', ['大球 (Over)', '小球 (Under)'], key=f"bs_{key}")} {st.text_input('門檻', value='2.5', key=f"th_{key}")}"
            elif "正確比分" in ps: sel = st.text_input("✍️ 比分 (例: 2:1)", value="2:1", key=f"sel_{key}")
            else: sel = st.text_input("✍️ 球員名字", value="梅西", key=f"sel_{key}")
            return ps, sel

        if bet_mode == "單注下注":
            sel_m = st.selectbox("⚽ 賽事：", open_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (ID:{r['match_id']})", axis=1))
            m_id = clean_id(sel_m.split("ID:")[-1].replace(")", ""))
            t_row = df_matches[df_matches['match_id'].astype(str) == m_id].iloc[0]
            ps, sel = render_ps(t_row, "sgl")
            odd = st.number_input("📈 賠率：", min_value=1.01, value=2.00, step=0.01)
            stk = st.number_input("💵 本金：", min_value=1.0, max_value=float(user_row['balance']), value=100.0)
            
            if st.button("📱 確認下注", type="primary"):
                df_users.loc[df_users["user_id"].astype(str) == str(u_id), "balance"] -= stk
                b_id = str(int(pd.to_numeric(df_bets["bet_id"], errors='coerce').max() + 1)) if not df_bets.empty else "1"
                df_bets = pd.concat([df_bets, pd.DataFrame([{"bet_id": b_id, "user_id": u_id, "bet_mode": "單注", "stake": stk, "status": "未開獎", "win_amount": 0.0}])], ignore_index=True)
                d_id = str(int(pd.to_numeric(df_details["detail_id"], errors='coerce').max() + 1)) if not df_details.empty else "1"
                df_details = pd.concat([df_details, pd.DataFrame([{"detail_id": d_id, "bet_id": b_id, "match_id": m_id, "playstyle": ps, "selection": sel.strip(), "odds_value": odd, "status": "未開獎"}])], ignore_index=True)
                save_sheet(df_users, "Users"); save_sheet(df_bets, "Bets"); save_sheet(df_details, "BetDetails")
                st.toast("✅ 單注成功！", icon="🎉"); time.sleep(1); st.rerun()
        else:
            sel_ms = st.multiselect("⚽ 挑選過關賽事 (最多5場)：", open_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (ID:{r['match_id']})", axis=1))
            if 2 <= len(sel_ms) <= 5:
                fmls = [f"{len(sel_ms)}串1"]
                if len(sel_ms) == 3: fmls += ["3串3", "3串4", "3串7"]
                elif len(sel_ms) == 4: fmls += ["4串6", "4串11", "4串15"]
                elif len(sel_ms) == 5: fmls += ["5串10", "5串26", "5串31"]
                fml = st.selectbox("🎯 選擇過關公式：", fmls)
                
                legs = []
                for i, m_str in enumerate(sel_ms):
                    m_id = clean_id(m_str.split("ID:")[-1].replace(")", ""))
                    t_row = df_matches[df_matches['match_id'].astype(str) == m_id].iloc[0]
                    st.markdown(f"**第 {i+1} 關：{t_row['home_team']} VS {t_row['away_team']}**")
                    ps, sel = render_ps(t_row, f"p_{m_id}")
                    odd = st.number_input(f"賠率", min_value=1.01, value=2.00, key=f"po_{m_id}")
                    legs.append({"m": m_id, "p": ps, "s": sel, "o": odd})
                stk = st.number_input("💵 本金：", min_value=1.0, max_value=float(user_row['balance']), value=100.0)
                if st.button("🚀 確認串關", type="primary"):
                    df_users.loc[df_users["user_id"].astype(str) == str(u_id), "balance"] -= stk
                    b_id = str(int(pd.to_numeric(df_bets["bet_id"], errors='coerce').max() + 1)) if not df_bets.empty else "1"
                    df_bets = pd.concat([df_bets, pd.DataFrame([{"bet_id": b_id, "user_id": u_id, "bet_mode": fml, "stake": stk, "status": "未開獎", "win_amount": 0.0}])], ignore_index=True)
                    for l in legs:
                        d_id = str(int(pd.to_numeric(df_details["detail_id"], errors='coerce').max() + 1)) if not df_details.empty else "1"
                        df_details = pd.concat([df_details, pd.DataFrame([{"detail_id": d_id, "bet_id": b_id, "match_id": l["m"], "playstyle": l["p"], "selection": l["s"].strip(), "odds_value": l["o"], "status": "未開獎"}])], ignore_index=True)
                    save_sheet(df_users, "Users"); save_sheet(df_bets, "Bets"); save_sheet(df_details, "BetDetails")
                    st.toast("🎉 串關成功！", icon="🎉"); time.sleep(1); st.rerun()

# ==================== TAB 4: 動態賽事池與手動分配後台 ====================
if is_admin:
    with tabs[3]:
        st.markdown("### ⚙️ 動態賽事池與對戰分配後台")
        
        # 1. 動態計算「球隊存活池」
        all_teams_ever = set(df_matches["home_team"].tolist() + df_matches["away_team"].tolist())
        all_teams_ever = {t for t in all_teams_ever if str(t).strip() and str(t).strip() != "待定"}
        
        # 獲取所有已淘汰的球隊
        eliminated_teams = set()
        settled_matches = df_matches[df_matches["status"].str.contains("結算", na=False)]
        for _, row in settled_matches.iterrows():
            h, a = str(row["home_team"]), str(row["away_team"])
            try:
                sh = int(float(row["score_home"])) if str(row["score_home"]).strip() else 0
                sa = int(float(row["score_away"])) if str(row["score_away"]).strip() else 0
                if sh > sa:
                    eliminated_teams.add(a)
                elif sa > sh:
                    eliminated_teams.add(h)
            except ValueError:
                pass
        
        # 存活池 = 全部球隊 - 已淘汰球隊
        alive_teams = list(all_teams_ever - eliminated_teams)
        
        # 找出存活池中「當前尚未被分配到 未開賽/進行中」比賽的待命球隊
        active_matches = df_matches[df_matches["status"].isin(["未開賽", "進行中"])]
        busy_teams = set(active_matches["home_team"].tolist() + active_matches["away_team"].tolist())
        idle_teams = [t for t in alive_teams if t not in busy_teams]

        st.markdown("#### 🏊‍♂️ 當前待命球隊池 (未淘汰且未安排比賽)")
        if idle_teams:
            st.info("、".join(idle_teams))
        else:
            st.warning("目前池中沒有空閒的存活球隊。")
            
        st.markdown("---")
        m_mode = st.radio("動作：", ["➕ 手動分配下一場對戰 (從存活池挑選)", "✏️ 編輯已有賽事"], horizontal=True)
        
        if m_mode == "➕ 手動分配下一場對戰 (從存活池挑選)":
            with st.form("a_m"):
                nid = st.text_input("自訂賽事 ID (例如: 17 代表16強第一場)", value=str(len(df_matches) + 1))
                
                c1, c2 = st.columns(2)
                # 下拉選單只會顯示還活著的球隊
                h = c1.selectbox("🏠 選擇主隊", ["待定"] + idle_teams)
                a = c2.selectbox("✈️ 選擇客隊", ["待定"] + idle_teams)
                
                if st.form_submit_button("➕ 確認生成此對戰"):
                    if h != "待定" and h == a:
                        st.error("❌ 主客隊不能是同一支球隊！")
                    else:
                        new_match = {"match_id": str(nid).strip(), "home_team": h, "away_team": a, "status": "未開賽", "score_home": "", "score_away": "", "first_goal_player": ""}
                        df_matches = pd.concat([df_matches, pd.DataFrame([new_match])], ignore_index=True)
                        save_sheet(df_matches, "Matches")
                        st.toast("✅ 成功從存活池分配新賽事！", icon="🎉")
                        time.sleep(1)
                        st.rerun()
                        
        elif m_mode == "✏️ 編輯已有賽事" and not df_matches.empty:
            sel_m = st.selectbox("選擇要修改的賽事", df_matches.apply(lambda r: f"ID:{r['match_id']} | {r['home_team']} VS {r['away_team']}", axis=1))
            m_id = str(sel_m.split("ID:")[1].split(" |")[0])
            t_row = df_matches[df_matches['match_id'].astype(str) == m_id].iloc[0]
            with st.form("e_m"):
                c1, c2, c3 = st.columns(3)
                nh = c1.text_input("主隊", value=str(t_row['home_team']))
                na = c2.text_input("客隊", value=str(t_row['away_team']))
                ns = c3.selectbox("狀態", ["未開賽", "進行中", "已結算"], index=["未開賽", "進行中", "已結算"].index(t_row['status']) if t_row['status'] in ["未開賽", "進行中", "已結算"] else 0)
                if st.form_submit_button("💾 儲存修改"):
                    df_matches.loc[df_matches['match_id'].astype(str) == m_id, ['home_team', 'away_team', 'status']] = [nh.strip(), na.strip(), ns]
                    save_sheet(df_matches, "Matches")
                    st.toast("✅ 賽事已儲存！", icon="✅")
                    time.sleep(1)
                    st.rerun()

# ==================== TAB 5: 投注管理後台 ====================
if is_admin:
    with tabs[4]:
        st.markdown("### 📝 投注管理後台")
        st.info("管理員可以在此修改未開獎的注單（調整本金、修改賠率），或直接作廢注單並退款給員工。")
        
        open_bets = df_bets[df_bets["status"].str.contains("未開|未开", na=False)] if not df_bets.empty else pd.DataFrame()
        
        if open_bets.empty:
            st.warning("目前沒有「未開獎」的注單可供管理。")
        else:
            with st.container(border=True):
                bet_options = open_bets.apply(
                    lambda r: f"單號: {r['bet_id']} | 員工: {df_users[df_users['user_id'].astype(str) == str(r['user_id'])]['name'].iloc[0] if not df_users[df_users['user_id'].astype(str) == str(r['user_id'])].empty else '未知'} | 模式: {r['bet_mode']} | 本金: {r['stake']}", axis=1
                )
                selected_bet_str = st.selectbox("🔍 選擇要管理的注單", bet_options.tolist())
                sel_b_id = selected_bet_str.split("單號: ")[1].split(" |")[0]
                
                target_bet = open_bets[open_bets["bet_id"].astype(str) == sel_b_id].iloc[0]
                target_details = df_details[df_details["bet_id"].astype(str) == sel_b_id]
                bet_u_id = str(target_bet["user_id"]).strip()
                
                manage_action = st.radio("🛠️ 執行動作：", ["✏️ 修改本金與賠率", "🗑️ 刪除注單並退還本金"], horizontal=True)
                
                st.markdown("---")
                
                if manage_action == "✏️ 修改本金與賠率":
                    with st.form("edit_bet_form"):
                        new_stake = st.number_input("💵 修改投注本金 ( pts )", min_value=1.0, value=float(target_bet["stake"]), step=50.0)
                        
                        st.markdown("**📊 修改各關卡賠率**")
                        new_odds_dict = {}
                        for idx, d_row in target_details.iterrows():
                            m_row = df_matches[df_matches["match_id"].astype(str) == str(d_row["match_id"])]
                            m_text = f"{m_row.iloc[0]['home_team']} VS {m_row.iloc[0]['away_team']}" if not m_row.empty else f"場次ID:{d_row['match_id']}"
                            label = f"M{d_row['match_id']}【{m_text}】 {d_row['playstyle']} - {d_row['selection']}"
                            new_odds_dict[d_row["detail_id"]] = st.number_input(label, min_value=1.01, value=float(d_row["odds_value"]), step=0.01, key=f"odd_{d_row['detail_id']}")
                            
                        if st.form_submit_button("💾 確認儲存修改", type="primary"):
                            diff = float(new_stake) - float(target_bet["stake"])
                            df_users["balance"] = pd.to_numeric(df_users["balance"], errors="coerce").fillna(0.0)
                            user_bal = df_users.loc[df_users["user_id"].astype(str) == bet_u_id, "balance"].values[0]
                            
                            if diff > 0 and user_bal < diff:
                                st.error(f"❌ 該員工餘額不足以增加本金！(尚需 {diff} pts，但帳戶僅剩 {user_bal} pts)")
                            else:
                                df_users.loc[df_users["user_id"].astype(str) == bet_u_id, "balance"] -= diff
                                df_bets.loc[df_bets["bet_id"].astype(str) == sel_b_id, "stake"] = float(new_stake)
                                for d_id, nv in new_odds_dict.items():
                                    df_details.loc[df_details["detail_id"].astype(str) == str(d_id), "odds_value"] = float(nv)
                                    
                                save_sheet(df_users, "Users")
                                save_sheet(df_bets, "Bets")
                                save_sheet(df_details, "BetDetails")
                                st.toast("✅ 注單本金與賠率修改成功！", icon="✅")
                                time.sleep(1)
                                st.rerun()
                                
                elif manage_action == "🗑️ 刪除注單並退還本金":
                    st.warning("⚠️ 確定要作廢此注單，並將本金全額退還給該員工嗎？此動作無法復原。")
                    if st.button("🗑️ 確認刪除並退款", type="primary"):
                        df_users["balance"] = pd.to_numeric(df_users["balance"], errors="coerce").fillna(0.0)
                        df_users.loc[df_users["user_id"].astype(str) == bet_u_id, "balance"] += float(target_bet["stake"])
                        
                        df_bets = df_bets[df_bets["bet_id"].astype(str) != sel_b_id]
                        df_details = df_details[df_details["bet_id"].astype(str) != sel_b_id]
                        
                        save_sheet(df_users, "Users")
                        save_sheet(df_bets, "Bets")
                        save_sheet(df_details, "BetDetails")
                        st.toast("🗑️ 注單已成功作廢，本金已退還！", icon="✅")
                        time.sleep(1)
                        st.rerun()

# ==================== TAB 6: 全自動對獎與派彩中心 ====================
if is_admin:
    with tabs[5]:
        st.markdown("### 🏁 賽果登錄與全自動結算中心")
        st.info("💡 **一鍵智能派彩**：您不需手動判定注單！只需輸入最終比分，系統將自動校對所有玩法，並根據馬會規則執行「過關容錯派彩計算」。")
        
        unsettled = df_matches[~df_matches["status"].str.contains("結算", na=False)]
        if unsettled.empty: st.markdown("### 🎉 所有賽事皆已結算完畢！")
        else:
            with st.container(border=True):
                sel_u = st.selectbox("📌 選擇完賽場次：", unsettled.apply(lambda r: f"ID:{r['match_id']} | {r['home_team']} VS {r['away_team']}", axis=1))
                s_mid = str(sel_u.split("ID:")[1].split(" |")[0])
                c_m = df_matches[df_matches["match_id"].astype(str) == s_mid].iloc[0]
                
                c1, c2, c3 = st.columns(3)
                
                score_h = c1.number_input("🏠 主隊進球", min_value=0, value=0)
                score_a = c2.number_input("✈️ 客隊進球", min_value=0, value=0)
                fg = c3.text_input("⚽ 首名進球員 (無請填:無)", value="無")
                
                tc = [t for t in [str(c_m['home_team']), str(c_m['away_team'])] if t.strip()] or ["主隊", "客隊"]
                win_t = st.selectbox("🥇 實際晉級隊伍 (防PK賽)：", tc)
                
                if st.button("📊 一鍵自動對獎並發送派彩", type="primary", use_container_width=True):
                    with st.spinner('引擎高速運算中...'):
                        # 1. 更新賽果
                        df_matches.loc[df_matches["match_id"].astype(str) == s_mid, ["status", "score_home", "score_away", "first_goal_player"]] = ["已結算", str(score_h), str(score_a), fg.strip()]
                        
                        # (這裡已移除自動晉級代碼，改由後台 Tab 4 手動分配)
                            
                        # 2. 自動批改這場比賽的所有注單 (Detail)
                        if not df_details.empty:
                            mask = df_details["match_id"].astype(str) == s_mid
                            for i, row in df_details[mask].iterrows():
                                if "未開" in str(row["status"]) or "未开" in str(row["status"]):
                                    df_details.loc[i, "status"] = auto_evaluate_leg(row["playstyle"], row["selection"], score_h, score_a, fg, c_m['home_team'], c_m['away_team'])
                        save_sheet(df_details, "BetDetails")
                        save_sheet(df_matches, "Matches")
                        
                        # 3. 進行過關容錯總結算 (Bet)
                        if not df_bets.empty:
                            df_users["balance"] = pd.to_numeric(df_users["balance"], errors="coerce").fillna(0.0)
                            unsettled_bets = df_bets[df_bets["status"].str.contains("未開|未开", na=False)]
                            
                            for i, bet in unsettled_bets.iterrows():
                                legs = df_details[df_details["bet_id"].astype(str) == str(bet["bet_id"])]
                                if not legs.empty and not legs["status"].str.contains("未開|未开").any():  
                                    infos = [{"status": r["status"], "odds": float(r["odds_value"])} for _, r in legs.iterrows()]
                                    ns, amt = evaluate_bet_payout(bet["bet_mode"], float(bet["stake"]), infos)
                                    df_bets.loc[i, ["status", "win_amount"]] = [ns, amt]
                                    if ns in ["贏", "赢"] and amt > 0:
                                        u_id = str(bet["user_id"]).strip()
                                        df_users.loc[df_users["user_id"].astype(str) == u_id, "balance"] += float(amt)
                            save_sheet(df_bets, "Bets")
                            save_sheet(df_users, "Users")
                    st.success(f"🎉 結算成功！已依容錯規則派發獎金！請至「賽事管理後台」手動為【{win_t}】安排下一輪賽事。")
                    time.sleep(2); st.rerun()
                    time.sleep(2); st.rerun()
