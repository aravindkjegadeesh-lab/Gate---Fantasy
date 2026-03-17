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

# --- CORE LOGIC ---
def calculate_fpl_points(mark):
    diff = mark - 70
    return 4 * math.pow(diff, 1.2) if diff >= 0 else -4 * math.pow(abs(diff), 1.2)

def run_bell_curve_fluctuation(round_name):
    df_scores = pd.read_sql("SELECT student, mark FROM score_history WHERE round_name=?", db_conn, params=(round_name,))
    if df_scores.empty: return []
    stats = df_scores.groupby('student')['mark'].mean().reset_index()
    mean, std = stats['mark'].mean(), stats['mark'].std() if stats['mark'].std() > 0 else 1 
    updates = []
    c = db_conn.cursor()
    for _, row in stats.iterrows():
        z = (row['mark'] - mean) / std
        # Z-Score Map: >1.5=5m, >0.5=2m, >-0.5=0, >-1.5=-2m, else -5m
        change = 5.0 if z > 1.5 else (2.0 if z > 0.5 else (0.0 if z > -0.5 else (-2.0 if z > -1.5 else -5.0)))
        if change != 0:
            c.execute("UPDATE market SET price = MAX(5.0, price + ?) WHERE name = ?", (change, row['student']))
            updates.append(f"{'📈' if change > 0 else '📉'} {row['student']}: {change:+}m")
    db_conn.commit()
    return updates

# --- DATA FETCH ---
market_df = pd.read_sql("SELECT * FROM market ORDER BY price DESC", db_conn)
player_prices = dict(zip(market_df['name'], market_df['price']))
player_options = [f"{n} (£{p}m)" for n, p in player_prices.items()]
active_q = pd.read_sql("SELECT * FROM game_state WHERE is_active=1 LIMIT 1", db_conn)
info = active_q.iloc[0] if not active_q.empty else {"round_name": "Round 1", "subjects": "Maths"}

# --- UI STYLE ---
st.markdown("""<style> .stApp { background-color: #FFFFFF; } .fpl-header { background: #38003c; padding: 20px; border-radius: 10px; text-align: center; color: white; border-bottom: 5px solid #00ff87; } </style>""", unsafe_allow_html=True)

if 'auth' not in st.session_state: st.session_state.auth = False

# --- LOGIN / SIGNUP ---
if not st.session_state.auth:
    st.markdown('<div class="fpl-header"><h1>GATE FANTASY</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["Login", "Sign Up"])
    with t1:
        u_in, p_in = st.text_input("Username"), st.text_input("Password", type="password")
        if st.button("Log In"):
            res = db_conn.execute("SELECT * FROM users WHERE username=? AND password=?", (u_in, p_in)).fetchone()
            if res:
                st.session_state.auth, st.session_state.user = True, u_in
                st.rerun()
    with t2:
        new_u = st.text_input("New Username")
        new_p = st.text_input("New Password", type="password")
        if st.button("Create Account"):
            try:
                db_conn.execute("INSERT INTO users (username, password, team, captain) VALUES (?, ?, 'None', 'None')", (new_u, new_p))
                db_conn.commit(); st.success("Account created!")
            except: st.error("User already exists.")
else:
    u_data = pd.read_sql("SELECT * FROM users WHERE username=?", db_conn, params=(st.session_state.user,)).iloc[0]
    page = st.sidebar.radio("Nav", ["Dashboard", "Leaderboard", "Player Stats", "Grade Portal", "My Squad", "Review Teams", "Admin"])

    if page == "Dashboard":
        st.markdown(f'<div class="fpl-header"><h1>{info["round_name"]}</h1></div>', unsafe_allow_html=True)
        b_hist = pd.read_sql("SELECT round_name, total_value FROM budget_history WHERE username=?", db_conn, params=(st.session_state.user,))
        if not b_hist.empty: st.line_chart(b_hist.set_index('round_name'))
        st.dataframe(market_df, hide_index=True, use_container_width=True)

    elif page == "Review Teams": # FIXED: Review Teams
        st.header("Manager Squads")
        # Fetch all managers except current user (or include all)
        all_managers = pd.read_sql("SELECT username, team, captain, tc_active FROM users", db_conn)
        
        if all_managers.empty:
            st.info("No managers found.")
        else:
            for _, row in all_managers.iterrows():
                with st.expander(f"Manager: {row['username']}"):
                    team_list = row['team'] if row['team'] and row['team'] != 'None' else "No team set"
                    st.write(f"**Current Squad:** {team_list}")
                    st.write(f"**Captain:** {row['captain']}")
                    if row['tc_active'] == 1:
                        st.warning("🚀 Triple Captain Active!")

    elif page == "My Squad":
        st.header("Transfer Center")
        cur_team = u_data['team'].split(", ") if u_data['team'] and u_data['team'] != 'None' else []
        total_val = sum(player_prices.get(p, 0) for p in cur_team)
        st.metric("Budget Used", f"£{total_val}m", f"{90-total_val}m left")
        
        if u_data['pending_team']: st.warning(f"⏳ Waiting for Admin to approve: {u_data['pending_team']}")
        
        sel = st.multiselect("Pick 5 Players", player_options, max_selections=5)
        new_names = [s.split(" (£")[0] for s in sel]
        cap_choice = st.selectbox("Select Captain", new_names if new_names else (cur_team if cur_team else ["None"]))
        tc_on = st.checkbox("Activate Triple Captain?") if u_data['tc_available'] else False
        
        if st.button("Submit Request"):
            if len(new_names) == 5:
                diff = len(set(new_names) - set(cur_team)) if cur_team else 0
                cost = sum(player_prices.get(n, 0) for n in new_names)
                if cost > 90: st.error("Over budget!")
                elif diff > 2: st.error("Max 2 transfers allowed.")
                else:
                    db_conn.execute("UPDATE users SET pending_team=?, pending_captain=?, tc_active=? WHERE username=?", 
                                   (", ".join(new_names), cap_choice, 1 if tc_on else 0, st.session_state.user))
                    db_conn.commit(); st.success("Request sent to Admin!"); st.rerun()

    elif page == "Admin":
        if st.text_input("Admin Key", type="password") == ADMIN_PASSWORD:
            t1, t2, t3, t4, t5 = st.tabs(["Approvals", "Round Transition", "Grid Scoring", "User Tools", "Danger Zone"])
            
            with t3: # GRID SCORING
                st.subheader("Bulk Entry")
                subs = [s.strip() for s in info['subjects'].replace(",", " ").split() if s.strip()]
                grid_df = pd.DataFrame({'Student': list(player_prices.keys())})
                for s in subs: grid_df[s] = 0.0
                
                edited = st.data_editor(grid_df, hide_index=True)
                if st.button("Submit All Scores"):
                    for _, row in edited.iterrows():
                        std_name = row['Student']
                        for sub in subs:
                            val = row[sub]
                            if val > 0:
                                p_pts = calculate_fpl_points(val)
                                db_conn.execute("INSERT INTO score_history (round_name, student, subject, mark, points) VALUES (?,?,?,?,?)", (info['round_name'], std_name, sub, val, p_pts))
                                # Points Update
                                for u_n, u_t, u_c, u_tc in db_conn.execute("SELECT username, team, captain, tc_active FROM users").fetchall():
                                    if u_t and std_name in u_t:
                                        m = 3 if (std_name == u_c and u_tc == 1) else (2 if std_name == u_c else 1)
                                        db_conn.execute("UPDATE users SET total_points = total_points + ? WHERE username=?", (p_pts * m, u_n))
                    db_conn.commit(); st.success("Scores saved!")

            with t1: # APPROVALS
                pending = pd.read_sql("SELECT username, team, pending_team, pending_captain FROM users WHERE pending_team IS NOT NULL", db_conn)
                if pending.empty: st.info("No pending requests.")
                for _, p_row in pending.iterrows():
                    with st.expander(f"Approval for {p_row['username']}"):
                        st.write(f"Old: {p_row['team']} -> New: {p_row['pending_team']}")
                        if st.button("Approve Request", key=f"appr_{p_row['username']}"):
                            db_conn.execute("UPDATE users SET team=pending_team, captain=pending_captain, pending_team=NULL, pending_captain=NULL WHERE username=?", (p_row['username'],))
                            db_conn.commit(); st.rerun()

            with t4: # USER TOOLS (Visible Passwords)
                users_list = pd.read_sql("SELECT username, password, total_points FROM users", db_conn)
                st.dataframe(users_list, use_container_width=True)
                target = st.selectbox("Manage User", users_list['username'].tolist())
                if st.button("Reset TC Chip"):
                    db_conn.execute("UPDATE users SET tc_available=1 WHERE username=?", (target,))
                    db_conn.commit(); st.success("Done.")

            with t5: # DANGER ZONE
                if st.button("🛠️ Full System Recalculate"):
                    db_conn.execute("UPDATE users SET total_points = 0")
                    history = db_conn.execute("SELECT student, points FROM score_history").fetchall()
                    for s_n, pts in history:
                        for u_n, u_t, u_c, u_tc in db_conn.execute("SELECT username, team, captain, tc_active FROM users").fetchall():
                            if u_t and s_n in u_t:
                                m = 3 if (s_n == u_c and u_tc == 1) else (2 if s_n == u_c else 1)
                                db_conn.execute("UPDATE users SET total_points = total_points + ? WHERE username=?", (pts * m, u_n))
                    db_conn.commit(); st.success("Recalculated!")
                if st.button("🔥 DELETE DATABASE"):
                    db_conn.execute("DROP TABLE users"); db_conn.execute("DROP TABLE score_history")
                    db_conn.commit(); st.rerun()
