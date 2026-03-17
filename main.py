import streamlit as st
import pandas as pd
import sqlite3
import math
import numpy as np

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('fantasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, team TEXT, pending_team TEXT, 
                  captain TEXT, pending_captain TEXT, tc_available INTEGER DEFAULT 1, 
                  tc_active INTEGER DEFAULT 0, total_points REAL DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS game_state 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, round_name TEXT, subjects TEXT, is_active INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS score_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, round_name TEXT, student TEXT, subject TEXT, mark REAL, points REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS market (name TEXT PRIMARY KEY, price REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS budget_history (username TEXT, round_name TEXT, total_value REAL)''')
    conn.commit()
    return conn

db_conn = init_db()
ADMIN_PASSWORD = st.secrets.get("ADMIN_KEY", "vinodbox43")

# --- BELL CURVE ENGINE (RESTORED) ---
def run_bell_curve_fluctuation(round_name):
    df_scores = pd.read_sql("SELECT student, mark FROM score_history WHERE round_name=?", db_conn, params=(round_name,))
    if df_scores.empty:
        return ["No scores found for bell curve."]

    # Calculate average mark per student for the round
    stats = df_scores.groupby('student')['mark'].mean().reset_index()
    marks = stats['mark']
    mean = marks.mean()
    std = marks.std() if marks.std() > 0 else 1 
    
    updates = []
    c = db_conn.cursor()

    for _, row in stats.iterrows():
        name = row['student']
        z = (row['mark'] - mean) / std # Z-Score calculation
        
        # Bell Curve Mapping (Lucas & Geonhee's +/- 5m Balanced scale)
        if z > 1.5: change = 5.0
        elif z > 0.5: change = 2.0
        elif z > -0.5: change = 0.0
        elif z > -1.5: change = -2.0
        else: change = -5.0
        
        if change != 0:
            c.execute("UPDATE market SET price = MAX(5.0, price + ?) WHERE name = ?", (change, name))
            updates.append(f"{'📈' if change > 0 else '📉'} {name}: {change:+}m (Z: {z:.2f})")
    
    db_conn.commit()
    return updates

def calculate_fpl_points(mark):
    diff = mark - 70
    return 4 * math.pow(diff, 1.2) if diff >= 0 else -4 * math.pow(abs(diff), 1.2)

# --- DATA REFRESH ---
market_df = pd.read_sql("SELECT * FROM market ORDER BY price DESC", db_conn)
player_prices = dict(zip(market_df['name'], market_df['price']))
player_options = [f"{n} (£{p}m)" for n, p in player_prices.items()]
active_q = pd.read_sql("SELECT * FROM game_state WHERE is_active=1 LIMIT 1", db_conn)
info = active_q.iloc[0] if not active_q.empty else {"round_name": "Round 1", "subjects": "Maths"}

# --- UI ---
st.markdown("""<style> .stApp { background-color: #FFFFFF; } .fpl-header { background: #38003c; padding: 20px; border-radius: 10px; text-align: center; color: white; border-bottom: 5px solid #00ff87; } </style>""", unsafe_allow_html=True)

if 'auth' not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.markdown('<div class="fpl-header"><h1>GATE FANTASY</h1></div>', unsafe_allow_html=True)
    u_in, p_in = st.text_input("Username"), st.text_input("Password", type="password")
    if st.button("Log In"):
        res = db_conn.execute("SELECT * FROM users WHERE username=? AND password=?", (u_in, p_in)).fetchone()
        if res:
            st.session_state.auth, st.session_state.user = True, u_in
            st.rerun()
else:
    u_data = pd.read_sql("SELECT * FROM users WHERE username=?", db_conn, params=(st.session_state.user,)).iloc[0]
    page = st.sidebar.radio("Nav", ["Dashboard", "Leaderboard", "Player Stats", "Grade Portal", "My Squad", "Review Teams", "Admin"])

    if page == "Dashboard":
        st.markdown(f'<div class="fpl-header"><h1>{info["round_name"]}</h1></div>', unsafe_allow_html=True)
        b_hist = pd.read_sql("SELECT round_name, total_value FROM budget_history WHERE username=?", db_conn, params=(st.session_state.user,))
        if not b_hist.empty: st.line_chart(b_hist.set_index('round_name'))
        st.dataframe(market_df, hide_index=True, use_container_width=True)

    elif page == "Grade Portal":
        st.header("📝 Grade Portal")
        raw_grades = pd.read_sql("SELECT student, subject, mark FROM score_history", db_conn)
        if not raw_grades.empty:
            pivot = raw_grades.pivot_table(index='student', columns='subject', values='mark', aggfunc='mean').fillna("-")
            st.dataframe(pivot, use_container_width=True)

    elif page == "My Squad":
        st.header("Transfer Center")
        cur_team = u_data['team'].split(", ") if u_data['team'] and u_data['team'] != 'None' else []
        st.write(f"**Current Team:** {', '.join(cur_team)}")
        if u_data['pending_team']: st.warning(f"⏳ Pending: {u_data['pending_team']}")
        sel = st.multiselect("Pick 5 Players", player_options, max_selections=5)
        new_names = [s.split(" (£")[0] for s in sel]
        cap_choice = st.selectbox("Select Captain", new_names if new_names else (cur_team if cur_team else ["None"]))
        tc_on = st.checkbox("Activate Triple Captain?") if u_data['tc_available'] else False
        if st.button("Submit Request"):
            if len(new_names) == 5:
                diff = len(set(new_names) - set(cur_team)) if cur_team else 0
                if diff > 2: st.error("Max 2 transfers allowed.")
                else:
                    db_conn.execute("UPDATE users SET pending_team=?, pending_captain=?, tc_active=? WHERE username=?", 
                                   (", ".join(new_names), cap_choice, 1 if tc_on else 0, st.session_state.user))
                    db_conn.commit(); st.success("Request sent!"); st.rerun()

    elif page == "Admin":
        if st.text_input("Admin Key", type="password") == ADMIN_PASSWORD:
            tabs = st.tabs(["Approvals", "Round Archives", "Apply Score", "User Tools", "Reset"])
            
            with tabs[1]: # ROUND ARCHIVES & BELL CURVE
                nr, ns = st.text_input("Next Round Name"), st.text_input("Subjects")
                if st.button("Start New Round (Apply Bell Curve)"):
                    for m_n, m_t in db_conn.execute("SELECT username, team FROM users").fetchall():
                        if m_t and m_t != 'None':
                            val = sum(player_prices.get(p, 0) for p in m_t.split(", "))
                            db_conn.execute("INSERT INTO budget_history (username, round_name, total_value) VALUES (?,?,?)", (m_n, info['round_name'], val))
                    db_conn.execute("UPDATE users SET tc_available=0 WHERE tc_active=1")
                    db_conn.execute("UPDATE users SET tc_active=0")
                    # TRIGGER BELL CURVE
                    reports = run_bell_curve_fluctuation(info['round_name'])
                    for r in reports: st.info(r)
                    db_conn.execute("UPDATE game_state SET is_active=0")
                    db_conn.execute("INSERT INTO game_state (round_name, subjects, is_active) VALUES (?,?,1)", (nr, ns))
                    db_conn.commit(); st.rerun()

            with tabs[3]: # USER TOOLS
                u_df = pd.read_sql("SELECT username, password, tc_available, total_points FROM users", db_conn)
                st.dataframe(u_df, use_container_width=True)
                target = st.selectbox("Select User", u_df['username'].tolist())
                new_p = st.text_input("Change Password")
                if st.button("Save New Password"):
                    db_conn.execute("UPDATE users SET password=? WHERE username=?", (new_p, target))
                    db_conn.commit(); st.success("Changed!")
                if st.button("Restore TC Chip"):
                    db_conn.execute("UPDATE users SET tc_available=1 WHERE username=?", (target,))
                    db_conn.commit(); st.success("TC Restored.")

            with tabs[4]: # RESET & RECALCULATE
                if st.button("🛠️ Full System Recalculate"):
                    db_conn.execute("UPDATE users SET total_points = 0")
                    history = db_conn.execute("SELECT round_name, student, points FROM score_history").fetchall()
                    for r_n, s_n, pts in history:
                        for u_n, u_t, u_c, u_tc in db_conn.execute("SELECT username, team, captain, tc_active FROM users").fetchall():
                            if u_t and s_n in u_t:
                                mult = 3 if (s_n == u_c and u_tc == 1) else (2 if s_n == u_c else 1)
                                db_conn.execute("UPDATE users SET total_points = total_points + ? WHERE username=?", (pts * mult, u_n))
                    db_conn.commit(); st.success("Recalculated!")
