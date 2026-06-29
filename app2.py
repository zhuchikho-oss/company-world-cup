import streamlit as st
import pandas as pd
import time
import itertools
import gspread
from google.oauth2.service_account import Credentials

# ==================== 0. 辅助函数与预设资料 ====================
def clean_id(x):
    """防止 Pandas 从 Google Sheets 读取数字变成 1.0 的型态问题"""
    s = str(x).strip()
    if s.endswith('.0'): return s[:-2]
    return s

# 32强 (Round of 32) 完整初始赛程
INITIAL_MATCHES = [
    {"match_id": "1", "home_team": "Germany", "away_team": "Paraguay", "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "2", "home_team": "France", "away_team": "Sweden", "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "3", "home_team": "South Africa", "away_team": "Canada", "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "4", "home_team": "Netherlands", "away_team": "Morocco", "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "5", "home_team": "Portugal", "away_team": "Croatia", "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "6", "home_team": "Spain", "away_team": "Austria", "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "7", "home_team": "United States", "away_team": "Bosnia/Herz.", "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "8", "home_team": "Belgium", "away_team": "Senegal", "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "9", "home_team": "Brazil", "away_team": "Japan", "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "10", "home_team": "Ivory Coast", "away_team": "Norway", "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "11", "home_team": "Mexico", "away_team": "Ecuador", "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "12", "home_team": "England", "away_team": "D.R. Congo", "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "13", "home_team": "Argentina", "away_team": "Cape Verde", "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "14", "home_team": "Australia", "away_team": "Egypt", "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "15", "home_team": "Switzerland", "away_team": "Algeria", "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""},
    {"match_id": "16", "home_team": "Colombia", "away_team": "Ghana", "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""}
]
for i in range(17, 32):
    INITIAL_MATCHES.append({"match_id": str(i), "home_team": "", "away_team": "", "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""})

# ==================== 1. 初始化 Google Sheets 资料库 ====================
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
    st.error("❌ 无法连接到 Google Sheets。请检查网址与服务帐号权限。")
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
        st.error(f"❌ 读取【{sheet_name}】失败，请稍候重整网页。详细: {e}")
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
        st.error(f"❌ 写入【{sheet_name}】失败。详细错误代码：{str(e)}")
        st.stop()

# ==================== 2. 全自动对奖与过关拆单引擎 ====================
def auto_evaluate_leg(playstyle, selection, hs, as_, first_goal, home_team, away_team):
    try: hs, as_ = int(hs), int(as_)
    except ValueError: return "未开奖"

    if "独赢盘" in playstyle:
        actual = f"主胜 ({home_team})" if hs > as_ else "和局 (Draw)" if hs == as_ else f"客胜 ({away_team})"
        return "赢" if selection.strip() == actual else "输"
    elif "让分盘" in playstyle:
        try:
            team, hdcp = selection.rsplit(" ", 1)[0].strip(), float(selection.rsplit(" ", 1)[1])
            adj_hs = hs + hdcp if team == home_team else hs
            adj_as = as_ + hdcp if team == away_team else as_
            if team == home_team and adj_hs > adj_as: return "赢"
            if team == away_team and adj_as > adj_hs: return "赢"
            return "输"
        except: return "输"
    elif "大小球" in playstyle:
        total = hs + as_
        try:
            threshold = float(selection.split(" ")[-1])
            is_over = "大球" in selection
            return "赢" if (is_over and total > threshold) or (not is_over and total < threshold) else "输"
        except: return "输"
    elif "正确比分" in playstyle:
        return "赢" if selection.strip() == f"{hs}:{as_}" else "输"
    elif "首名进球" in playstyle:
        if selection.strip() == "无" and first_goal.strip() == "无": return "赢"
        return "赢" if selection.strip() == first_goal.strip() else "输"
    return "未开奖"

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
    if any(leg["status"] == "未开奖" for leg in legs_info): return "未开奖", 0.0
    if bet_mode == "单注":
        if legs_info[0]["status"] == "赢": return "赢", round(stake * legs_info[0]["odds"], 1)
        else: return "输", 0.0

    n_legs = len(legs_info)
    combos = get_parlay_combinations(n_legs, bet_mode)
    unit_stake = float(stake) / len(combos)
    total_win = 0.0

    for combo in combos:
        combo_status = [legs_info[i]["status"] for i in combo]
        if "输" not in combo_status:
            c_odds = 1.0
            for i in combo: c_odds *= legs_info[i]["odds"]
            total_win += unit_stake * c_odds

    return ("赢", round(total_win, 1)) if total_win > 0 else ("输", 0.0)

def calculate_next_stage_advancement(c_id, winner_name):
    if not winner_name or winner_name == "待定": return
    c_id = int(c_id)
    next_id, is_home = None, True
    if 1 <= c_id <= 16: next_id, is_home = 17 + (c_id - 1) // 2, (c_id % 2 != 0)
    elif 17 <= c_id <= 24: next_id, is_home = 25 + (c_id - 17) // 2, (c_id % 2 != 0)
    elif 25 <= c_id <= 28: next_id, is_home = 29 + (c_id - 25) // 2, (c_id % 2 != 0)
    elif 29 <= c_id <= 30: next_id, is_home = 31, (c_id == 29)
        
    if next_id:
        global df_matches
        mask = df_matches['match_id'].astype(str) == str(next_id)
        if not df_matches[mask].empty:
            df_matches.loc[mask, 'home_team' if is_home else 'away_team'] = winner_name
        else:
            new_m = {"match_id": str(next_id), "home_team": winner_name if is_home else "", "away_team": "" if is_home else winner_name, "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""}
            df_matches = pd.concat([df_matches, pd.DataFrame([new_m])], ignore_index=True)

# ==================== 3. 系统初始化与 UI 设定 ====================
st.set_page_config(page_title="2026世界杯竞猜系统", page_icon="🏆", layout="centered")
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
<div class="main-banner"><div class="main-title">🏆 2026 世界杯智能竞猜中心</div><div class="sub-title" style="color:#38bdf8;">【官方 32 强赛程与极净对奖版】</div></div>
""", unsafe_allow_html=True)

is_admin = ("role" in st.query_params and st.query_params["role"] == "boss")
tabs = st.tabs(["📊 财富排行", "📅 赛况树状图", "🎲 快速投注", "⚙️ 赛事管理后台", "🏁 完赛自动结算"] if is_admin else ["📊 财富排行", "📅 赛况树状图", "🎲 快速投注"])

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
    st.markdown("### 📈 财富龙虎榜")
    df_users["balance"] = pd.to_numeric(df_users["balance"], errors="coerce").fillna(0)
    df_ranking = df_users.sort_values(by="balance", ascending=False).reset_index(drop=True)
    if len(df_ranking) >= 3:
        st.markdown(f"#### 🥇 榜首：{df_ranking.iloc[0]['name']} — **{df_ranking.iloc[0]['balance']:.1f} pts**")
        st.markdown(f"#### 🥈 亚军：{df_ranking.iloc[1]['name']} — **{df_ranking.iloc[1]['balance']:.1f} pts**")
        st.markdown(f"#### 🥉 季军：{df_ranking.iloc[2]['name']} — **{df_ranking.iloc[2]['balance']:.1f} pts**")
    st.markdown("---")
    df_ranking.index = df_ranking.index + 1
    st.dataframe(df_ranking.rename(columns={"name": "同事姓名", "balance": "积分余额"})[["同事姓名", "积分余额"]], use_container_width=True)

# ==================== TAB 2: 动态树状图 ====================
with tabs[1]:
    st.markdown("### 🏆 32强淘汰赛动态晋级线路图")
    def get_route_text(m_id):
        m = int(m_id)
        if 1 <= m <= 16: return f"➡️ 晋级：16强 (场次 {17 + (m - 1) // 2})"
        elif 17 <= m <= 24: return f"➡️ 晋级：八强 (场次 {25 + (m - 17) // 2})"
        elif 25 <= m <= 28: return f"➡️ 晋级：四强 (场次 {29 + (m - 25) // 2})"
        elif 29 <= m <= 30: return "🏆 前进总决赛 (场次 31)"
        elif m == 31: return "👑 争夺世界之巅"
        return "➡️ 常规自订赛事"

    def get_match_card_html(m_id, title_name):
        m_rows = df_matches[df_matches['match_id'].astype(str) == str(m_id)]
        if m_rows.empty: return ""
        row = m_rows.iloc[0]
        h = str(row['home_team']).strip() or "待定"
        a = str(row['away_team']).strip() or "待定"
        s = row['status']
        s_h = str(row['score_home']).strip() if "结算" in s else "-"
        s_a = str(row['score_away']).strip() if "结算" in s else "-"
        
        badge = f'<span class="status-badge {"settled" if "结算" in s else "live" if s=="进行中" else "upcoming"}">{s if "结算" not in s else "已完赛"}</span>'
        cls = "match-card final-card" if m_id == 31 else "match-card"
        if s == "未开赛" and m_id > 16: cls += " border-gray"
        
        h_style = ' style="border-color: #fbbf24;"' if m_id == 31 else ''
        t_style = ' style="color:#fbbf24 !important; font-weight:900;"' if m_id == 31 else ''
        html = f"""<div class="{cls}"><div class="match-header"{h_style}><span{t_style}>{title_name} (M{m_id})</span>{badge}</div><div class="team-row"><span class="team-name">🏠 {h}</span><span class="team-score">{s_h}</span></div><div class="team-row"><span class="team-name">✈️ {a}</span><span class="team-score">{s_a}</span></div>"""
        if str(row.get('first_goal_player', '')).strip(): html += f'<div style="font-size:0.75rem; color:#fef3c7;">⚽ 首名进球：{row["first_goal_player"]}</div>'
        html += f'<div class="{"final-winner" if m_id==31 else "next-route"}">{get_route_text(m_id)}</div></div>'
        return html

    bracket_html = f"""<div class="bracket-wrapper">
    {"<div class='bracket-round'><div class='round-title'>⚔️ 32强赛</div>" + "".join([get_match_card_html(i, "32强") for i in range(1, 17)]) + "</div>"}
    {"<div class='bracket-round'><div class='round-title'>🔥 16强赛</div>" + "".join([get_match_card_html(i, "16强") for i in range(17, 25)]) + "</div>"}
    {"<div class='bracket-round'><div class='round-title'>⚡ 半准决赛</div>" + "".join([get_match_card_html(i, "八强") for i in range(25, 29)]) + "</div>"}
    {"<div class='bracket-round'><div class='round-title'>🌟 准决赛</div>" + "".join([get_match_card_html(i, "四强") for i in range(29, 31)]) + "</div>"}
    {"<div class='bracket-round'><div class='round-title' style='color:#fbbf24;'>👑 总决赛</div>" + get_match_card_html(31, "FINAL") + "</div>"}
    </div>"""
    st.markdown(bracket_html, unsafe_allow_html=True)

# ==================== TAB 3: 投注中心 ====================
with tabs[2]:
    st.markdown("### 🎲 员工自选赔率下注区")
    open_matches = df_matches[df_matches['status'].isin(['未开赛', '进行中'])]
    
    with st.container(border=True):
        active_user = st.selectbox("👤 请选择身分：", df_users["name"].tolist())
        user_row = df_users[df_users["name"] == active_user].iloc[0]
        u_id = clean_id(user_row["user_id"])
        st.markdown(f"### 💰 你的可用积分：**{float(user_row['balance']):.1f} pts**")
        
    with st.expander("📜 查看历史投注纪录", expanded=False):
        my_bets = df_bets[df_bets["user_id"].astype(str) == str(u_id)] if not df_bets.empty else pd.DataFrame()
        if my_bets.empty: st.info("无下注历史。")
        else:
            history = []
            for _, b in my_bets.iterrows():
                legs = df_details[df_details["bet_id"].astype(str) == str(b["bet_id"])]
                summ = [f"M{d['match_id']} [{d.get('playstyle', '')}] {d['selection']}(@{d['odds_value']}) [{d['status']}]" for _, d in legs.iterrows()]
                history.append({"单号": b["bet_id"], "模式": b["bet_mode"], "内容": " ✖️ ".join(summ), "本金": f"{b['stake']}", "状态": b["status"], "赢得": f"{b['win_amount']}"})
            st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)
                
    st.markdown("---")
    if open_matches.empty: st.markdown("#### 📭 无开放赛事。")
    else:
        bet_mode = st.radio("🎯 选择下注模式：", ["单注下注", "过关串关"], horizontal=True)
        
        def render_ps(m_row, key):
            h, a = m_row['home_team'], m_row['away_team']
            ps = st.selectbox("🎰 选择玩法", ["① 独赢盘", "② 让分盘", "③ 大小球", "④ 正确比分", "⑤ 首名进球"], key=f"ps_{key}")
            if "独赢盘" in ps: sel = st.selectbox("🎯 选项", [f"主胜 ({h})", "和局 (Draw)", f"客胜 ({a})"], key=f"sel_{key}")
            elif "让分盘" in ps: sel = st.text_input("✍️ 让分 (例: Brazil -1.5)", value=f"{h} -0.5", key=f"sel_{key}")
            elif "大小球" in ps: sel = f"{st.selectbox('🎯', ['大球 (Over)', '小球 (Under)'], key=f"bs_{key}")} {st.text_input('门槛', value='2.5', key=f"th_{key}")}"
            elif "正确比分" in ps: sel = st.text_input("✍️ 比分 (例: 2:1)", value="2:1", key=f"sel_{key}")
            else: sel = st.text_input("✍️ 球员名字", value="梅西", key=f"sel_{key}")
            return ps, sel

        if bet_mode == "单注下注":
            sel_m = st.selectbox("⚽ 赛事：", open_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (ID:{r['match_id']})", axis=1))
            m_id = clean_id(sel_m.split("ID:")[-1].replace(")", ""))
            t_row = df_matches[df_matches['match_id'].astype(str) == m_id].iloc[0]
            ps, sel = render_ps(t_row, "sgl")
            odd = st.number_input("📈 赔率：", min_value=1.01, value=2.00, step=0.01)
            stk = st.number_input("💵 本金：", min_value=1.0, max_value=float(user_row['balance']), value=100.0)
            
            if st.button("📱 确认下注", type="primary"):
                df_users.loc[df_users["user_id"].astype(str) == str(u_id), "balance"] -= stk
                b_id = str(int(pd.to_numeric(df_bets["bet_id"], errors='coerce').max() + 1)) if not df_bets.empty else "1"
                df_bets = pd.concat([df_bets, pd.DataFrame([{"bet_id": b_id, "user_id": u_id, "bet_mode": "单注", "stake": stk, "status": "未开奖", "win_amount": 0.0}])], ignore_index=True)
                d_id = str(int(pd.to_numeric(df_details["detail_id"], errors='coerce').max() + 1)) if not df_details.empty else "1"
                df_details = pd.concat([df_details, pd.DataFrame([{"detail_id": d_id, "bet_id": b_id, "match_id": m_id, "playstyle": ps, "selection": sel.strip(), "odds_value": odd, "status": "未开奖"}])], ignore_index=True)
                save_sheet(df_users, "Users"); save_sheet(df_bets, "Bets"); save_sheet(df_details, "BetDetails")
                st.toast("✅ 单注成功！", icon="🎉"); time.sleep(1); st.rerun()
        else:
            sel_ms = st.multiselect("⚽ 挑选过关赛事 (最多5场)：", open_matches.apply(lambda r: f"{r['home_team']} VS {r['away_team']} (ID:{r['match_id']})", axis=1))
            if 2 <= len(sel_ms) <= 5:
                fmls = [f"{len(sel_ms)}串1"]
                if len(sel_ms) == 3: fmls += ["3串3", "3串4", "3串7"]
                elif len(sel_ms) == 4: fmls += ["4串6", "4串11", "4串15"]
                elif len(sel_ms) == 5: fmls += ["5串10", "5串26", "5串31"]
                fml = st.selectbox("🎯 选择过关公式：", fmls)
                
                legs = []
                for i, m_str in enumerate(sel_ms):
                    m_id = clean_id(m_str.split("ID:")[-1].replace(")", ""))
                    t_row = df_matches[df_matches['match_id'].astype(str) == m_id].iloc[0]
                    st.markdown(f"**第 {i+1} 关：{t_row['home_team']} VS {t_row['away_team']}**")
                    ps, sel = render_ps(t_row, f"p_{m_id}")
                    odd = st.number_input(f"赔率", min_value=1.01, value=2.00, key=f"po_{m_id}")
                    legs.append({"m": m_id, "p": ps, "s": sel, "o": odd})
                stk = st.number_input("💵 本金：", min_value=1.0, max_value=float(user_row['balance']), value=100.0)
                if st.button("🚀 确认串关", type="primary"):
                    df_users.loc[df_users["user_id"].astype(str) == str(u_id), "balance"] -= stk
                    b_id = str(int(pd.to_numeric(df_bets["bet_id"], errors='coerce').max() + 1)) if not df_bets.empty else "1"
                    df_bets = pd.concat([df_bets, pd.DataFrame([{"bet_id": b_id, "user_id": u_id, "bet_mode": fml, "stake": stk, "status": "未开奖", "win_amount": 0.0}])], ignore_index=True)
                    for l in legs:
                        d_id = str(int(pd.to_numeric(df_details["detail_id"], errors='coerce').max() + 1)) if not df_details.empty else "1"
                        df_details = pd.concat([df_details, pd.DataFrame([{"detail_id": d_id, "bet_id": b_id, "match_id": l["m"], "playstyle": l["p"], "selection": l["s"].strip(), "odds_value": l["o"], "status": "未开奖"}])], ignore_index=True)
                    save_sheet(df_users, "Users"); save_sheet(df_bets, "Bets"); save_sheet(df_details, "BetDetails")
                    st.toast("🎉 串关成功！", icon="🎉"); time.sleep(1); st.rerun()

# ==================== TAB 4: 管理后台 ====================
if is_admin:
    with tabs[3]:
        st.markdown("### ⚙️ 赛事名单增删管理后台")
        m_mode = st.radio("动作：", ["✏️ 编辑赛事", "➕ 新增赛事"], horizontal=True)
        if m_mode == "✏️ 编辑赛事" and not df_matches.empty:
            sel_m = st.selectbox("赛事", df_matches.apply(lambda r: f"ID:{r['match_id']} | {r['home_team']} VS {r['away_team']}", axis=1))
            m_id = str(sel_m.split("ID:")[1].split(" |")[0])
            t_row = df_matches[df_matches['match_id'].astype(str) == m_id].iloc[0]
            with st.form("e_m"):
                c1, c2, c3 = st.columns(3)
                nh = c1.text_input("主队", value=str(t_row['home_team']))
                na = c2.text_input("客队", value=str(t_row['away_team']))
                ns = c3.selectbox("状态", ["未开赛", "进行中", "已结算"], index=["未开赛", "进行中", "已结算"].index(t_row['status']) if t_row['status'] in ["未开赛", "进行中", "已结算"] else 0)
                if st.form_submit_button("💾 储存"):
                    df_matches.loc[df_matches['match_id'].astype(str) == m_id, ['home_team', 'away_team', 'status']] = [nh.strip(), na.strip(), ns]
                    save_sheet(df_matches, "Matches"); st.toast("✅ 赛事已储存！", icon="✅"); time.sleep(1); st.rerun()
        elif m_mode == "➕ 新增赛事":
            with st.form("a_m"):
                nid = st.text_input("自订ID (建议32以上)", value="32")
                h, a = st.text_input("主队"), st.text_input("客队")
                if st.form_submit_button("➕ 新增"):
                    df_matches = pd.concat([df_matches, pd.DataFrame([{"match_id": str(nid), "home_team": h, "away_team": a, "status": "未开赛", "score_home": "", "score_away": "", "first_goal_player": ""}])], ignore_index=True)
                    save_sheet(df_matches, "Matches"); st.toast("✅ 成功新增赛事！", icon="🎉"); time.sleep(1); st.rerun()

# ==================== TAB 5: 全自动对奖与派彩中心 ====================
if is_admin:
    with tabs[4]:
        st.markdown("### 🏁 赛果登录与全自动结算中心")
        st.info("💡 **一键智能派彩**：您不需手动判定注单！只需输入最终比分，系统将自动校对所有玩法，并根据马会规则执行「过关容错派彩计算」，同时将获胜队伍自动前推晋级！")
        
        unsettled = df_matches[~df_matches["status"].str.contains("结算")]
        if unsettled.empty: st.markdown("### 🎉 所有赛事皆已结算完毕！")
        else:
            with st.container(border=True):
                sel_u = st.selectbox("📌 选择完赛场次：", unsettled.apply(lambda r: f"ID:{r['match_id']} | {r['home_team']} VS {r['away_team']}", axis=1))
                s_mid = str(sel_u.split("ID:")[1].split(" |")[0])
                c_m = df_matches[df_matches["match_id"].astype(str) == s_mid].iloc[0]
                
                c1, c2, c3 = st.columns(3)
                
                # 修复核心点：将变量名由 sh, sa 改为 score_h, score_a 以防与 gspread 的 sh 变量冲突！
                score_h = c1.number_input("🏠 主队进球", min_value=0, value=0)
                score_a = c2.number_input("✈️ 客队进球", min_value=0, value=0)
                fg = c3.text_input("⚽ 首名进球员 (无请填:无)", value="无")
                
                tc = [t for t in [str(c_m['home_team']), str(c_m['away_team'])] if t.strip()] or ["主队", "客队"]
                win_t = st.selectbox("🥇 实际晋级队伍 (防PK赛)：", tc)
                
                if st.button("📊 一键自动对奖、发送派彩并晋级球队", type="primary", use_container_width=True):
                    with st.spinner('引擎高速运算中...'):
                        # 1. 更新赛果
                        df_matches.loc[df_matches["match_id"].astype(str) == s_mid, ["status", "score_home", "score_away", "first_goal_player"]] = ["已结算", str(score_h), str(score_a), fg.strip()]
                        
                        # 2. 自动晋级
                        if int(s_mid) <= 30: calculate_next_stage_advancement(s_mid, win_t)
                            
                        # 3. 自动批改这场比赛的所有注单 (Detail)
                        if not df_details.empty:
                            mask = df_details["match_id"].astype(str) == s_mid
                            for i, row in df_details[mask].iterrows():
                                if row["status"] == "未开奖":
                                    df_details.loc[i, "status"] = auto_evaluate_leg(row["playstyle"], row["selection"], score_h, score_a, fg, c_m['home_team'], c_m['away_team'])
                        save_sheet(df_details, "BetDetails")
                        save_sheet(df_matches, "Matches")
                        
                        # 4. 进行过关容错总结算 (Bet)
                        if not df_bets.empty:
                            df_users["balance"] = pd.to_numeric(df_users["balance"], errors="coerce")
                            for i, bet in df_bets[df_bets["status"] == "未开奖"].iterrows():
                                legs = df_details[df_details["bet_id"].astype(str) == str(bet["bet_id"])]
                                if not any(legs["status"] == "未开奖"):  # 该单全部赛事都开奖了才结算
                                    infos = [{"status": r["status"], "odds": float(r["odds_value"])} for _, r in legs.iterrows()]
                                    ns, amt = evaluate_bet_payout(bet["bet_mode"], float(bet["stake"]), infos)
                                    df_bets.loc[i, ["status", "win_amount"]] = [ns, amt]
                                    if ns == "赢" and amt > 0:
                                        df_users.loc[df_users["user_id"].astype(str) == str(bet["user_id"]).strip(), "balance"] += amt
                            save_sheet(df_bets, "Bets")
                            save_sheet(df_users, "Users")
                    st.success(f"🎉 结算成功！已依容错规则派发奖金！【{win_t}】已自动推向下一轮。")
                    time.sleep(2); st.rerun()
