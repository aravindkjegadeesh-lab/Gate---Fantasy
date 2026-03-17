import streamlit as st
import pandas as pd
import sqlite3
import math
import numpy as np

# --- PAGE CONFIG ---
st.set_page_config(page_title="Gate Fantasy", page_icon="⚽", layout="centered")

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('fantasy.db', check_same_thread=False)
    c = conn.cursor()
    # Users Table
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, team TEXT, pending_team TEXT, 
                  captain TEXT, total_points REAL DEFAULT 0)''')
    # Game State Table
    c.execute('''CREATE TABLE IF NOT EXISTS game_state 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, round_name TEXT, subjects TEXT, is_active INTEGER DEFAULT 0)''')
    # History Table
    c.execute('''CREATE TABLE IF NOT EXISTS score_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, round_name TEXT, student TEXT, subject TEXT, mark REAL, points REAL)''')
    # Market Table
    c.execute('''CREATE TABLE IF NOT EXISTS market (name TEXT PRIMARY KEY, price REAL)''')
    # Budget History Table
    c.execute('''CREATE TABLE IF NOT EXISTS budget_history 
                 (username TEXT, round_name TEXT, total_value REAL)''')
    
    # Check for pending_team column (Migration)
    cursor = conn.execute('PRAGMA table_info(users)')
    cols = [info[1] for info in cursor.fetchall()]
    if 'pending_team' not in cols:
        c.execute('ALTER TABLE users ADD COLUMN pending_team TEXT')

    # Seed Market if empty
    if c.execute("SELECT COUNT(*) FROM market").fetchone()[0] == 0:
        initial_players = [
            ("Ming", 36.0), ("Cirrus", 35.5), ("Gautham", 33.0), ("Dev", 32.5), ("Forrest", 30.0), 
            ("Talal", 28.5), ("Geonhee", 27.0), ("Hardy", 23.0), ("Ethan Yuen", 22.5), ("Abdul", 22.0), 
            ("Lucas Yiu", 22.0), ("Adhvik", 21.0), ("Sid", 20.0), ("Barnabas", 20.0), ("Komron", 20.0), 
            ("Michael", 20.0), ("Nathan", 20.0), ("Ethan Wang", 19.5), ("Josh", 19.0), ("Daren", 17.5), 
            ("Aravind", 17.0), ("Alfie", 16.0), ("Musa", 15.0), ("Maxwell", 14.0), ("Andre", 14.0), 
            ("Inesh", 14.0), ("Maximus", 13.0), ("Jared", 13.0), ("Lucas Lau", 12.0), ("Alden", 11.0), 
            ("Sanjit", 10.5), ("Yashwant", 10.5), ("Maxi", 10.0), ("Raymond", 9.5), ("Hassan", 9.0), ("Lucas Kong", 8.0)
        ]
        c.executemany("INSERT INTO market (name, price) VALUES (?,?)", initial_players)
    conn.commit()
    return conn

db_conn = init_db()

# --- ADMIN SECURITY ---
ADMIN_PASSWORD = st.secrets.get("ADMIN_KEY", "vinodbox43")

# --- HELPERS ---
def calculate_fpl_points(mark):
    diff = mark - 70
    return 4 * math.pow(diff, 1.2) if diff >= 0 else -4 * math.pow(abs(diff), 1.2)

def run_bell_curve(round_name):
    df_scores = pd.read_sql("SELECT student, mark FROM score_history WHERE round_name=?", db_conn, params=(round_name,))
    if df_scores.empty: return []
    stats = df_scores.groupby('student')['mark'].mean().reset_index()
    mean, std = stats['mark'].mean(), stats['mark'].std()
    if std == 0 or pd.isna(std): std = 1
    
    updates = []
    c = db_conn.cursor()
    for _, row in stats.iterrows():
        z = (row['mark'] - mean) / std
        if z > 1.5: change = 5.0
        elif z > 0.5: change = 2.0
        elif z > -0.5: change = 0.0
        elif z > -1.5: change = -2.0
        else: change = -5.0
        
        if change != 0:
            c.execute("UPDATE market SET price = MAX(5.0, price + ?) WHERE name = ?", (change, row['student']))
            updates.append(f"{'📈' if change > 0 else '📉'} {row['student']}: {change:+}m")
    db_conn.commit()
    return updates

# --- DATA REFRESH ---
market_df = pd.read_sql("SELECT * FROM market ORDER BY price DESC", db_conn)
player_prices = dict(zip(market_df['name'], market_df['price']))
player_options = [f"{n} (£{p}m)" for n, p in player_prices.items()]
active_q = pd.read_sql("SELECT * FROM game_state WHERE is_active=1 LIMIT 1", db_conn)
info = active_q.iloc[0] if not active_q.empty else {"round_name": "Round 1", "subjects": "Maths"}

# --- STYLE ---
st.markdown("""<style>
    .stApp { background-color: #FFFFFF; }
    .fpl-header { background: #38003c; padding: 20px; border-radius: 10px; text-align: center; color: white; border-bottom: 5px solid #00ff87; }
    .card { background: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #38003c; margin-bottom: 10px; color: #38003c; }
    </style>""", unsafe_allow_html=True)

if 'auth' not in st.session_state: st.session_state.auth = False

# --- APP ---
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
else:
    u_data = pd.read_sql("SELECT * FROM users WHERE username=?", db_conn, params=(st.session_state.user,)).iloc[0]
    page = st.sidebar.radio("Nav", ["Dashboard", "Leaderboard", "Player Stats", "Grade Portal", "My Squad", "Review Teams", "Admin"])

    if page == "Dashboard":
        st.markdown(f'<div class="fpl-header"><h1>{info["round_name"]}</h1></div>', unsafe_allow_html=True)
        st.subheader("Budget History")
        b_hist = pd.read_sql("SELECT round_name, total_value FROM budget_history WHERE username=?", db_conn, params=(st.session_state.user,))
        if not b_hist.empty: st.line_chart(b_hist.set_index('round_name'))
        st.subheader("Market Prices")
        st.dataframe(market_df, use_container_width=True, hide_index=True)

    elif page == "Leaderboard":
        st.header("🏆 Standings")
        ld_df = pd.read_sql("SELECT username as Manager, total_points as Points FROM users ORDER BY total_points DESC", db_conn)
        ld_df['Points'] = pd.to_numeric(ld_df['Points']).round(2)
        st.dataframe(ld_df, use_container_width=True, hide_index=True)

    elif page == "My Squad":
        st.header("Transfer Center")
        cur_team = u_data['team'].split(", ") if u_data['team'] and u_data['team'] != 'None' else []
        st.write(f"**Current Squad:** {', '.join(cur_team)}")
        
        if u_data['pending_team']:
            st.warning(f"⏳ Pending Approval: {u_data['pending_team']}")
            
        sel = st.multiselect("Select New Squad (Max 2 changes)", player_options, max_selections=5)
        new_names = [s.split(" (£")[0] for s in sel]
        
        if st.button("Submit Transfer Request"):
            if len(new_names) == 5:
                diff = len(set(new_names) - set(cur_team)) if cur_team else 0
                cost = sum(player_prices.get(n, 0) for n in new_names)
                if cost > 90: st.error("Over budget (£90m max)")
                elif diff > 2: st.error(f"Transfer limit is 2. You tried {diff}.")
                else:
                    db_conn.execute("UPDATE users SET pending_team=? WHERE username=?", (", ".join(new_names), st.session_state.user))
                    db_conn.commit(); st.success("Request Sent!"); st.rerun()

    elif page == "Admin":
        if st.text_input("Admin Key", type="password") == ADMIN_PASSWORD:
            t1, t2, t3, t4, t5 = st.tabs(["Transfers", "Rounds", "Scoring", "Users", "Danger"])
            
            with t1: # TRANSFER DESK
                pending = pd.read_sql("SELECT username, team, pending_team FROM users WHERE pending_team IS NOT NULL", db_conn)
                for _, row in pending.iterrows():
                    with st.expander(f"Review: {row['username']}"):
                        st.write(f"Old: {row['team']} -> New: {row['pending_team']}")
                        if st.button("Approve", key=f"app_{row['username']}"):
                            db_conn.execute("UPDATE users SET team=?, pending_team=NULL WHERE username=?", (row['pending_team'], row['username']))
                            db_conn.commit(); st.rerun()
                        if st.button("Reject", key=f"rej_{row['username']}"):
                            db_conn.execute("UPDATE users SET pending_team=NULL WHERE username=?", (row['username'],))
                            db_conn.commit(); st.rerun()

            with t2: # ROUNDS
                nr, ns = st.text_input("New Round Name"), st.text_input("New Subjects")
                if st.button("End Round & Run Bell Curve"):
                    # Record Budget Values
                    for m_n, m_t in db_conn.execute("SELECT username, team FROM users").fetchall():
                        if m_t and m_t != 'None':
                            val = sum(player_prices.get(p, 0) for p in m_t.split(", "))
                            db_conn.execute("INSERT INTO budget_history (username, round_name, total_value) VALUES (?,?,?)", (m_n, info['round_name'], val))
                    run_bell_curve(info['round_name'])
                    db_conn.execute("UPDATE game_state SET is_active=0")
                    db_conn.execute("INSERT INTO game_state (round_name, subjects, is_active) VALUES (?,?,1)", (nr, ns))
                    db_conn.commit(); st.rerun()

            with t3: # SCORING
                st_n = st.selectbox("Student", list(player_prices.keys()))
                subs = [s.strip() for s in info['subjects'].replace(",", " ").split() if s.strip()]
                sub_n = st.selectbox("Subject", list(set(subs)))
                mk = st.number_input("Mark", 0.0, 100.0)
                if st.button("Apply Score"):
                    pts = calculate_fpl_points(mk)
                    db_conn.execute("INSERT INTO score_history (round_name, student, subject, mark, points) VALUES (?,?,?,?,?)", (info['round_name'], st_n, sub_n, mk, pts))
                    for u_n, u_t, u_c in db_conn.execute("SELECT username, team, captain FROM users").fetchall():
                        if u_t and st_n in u_t:
                            m = 2 if st_n == u_c else 1
                            db_conn.execute("UPDATE users SET total_points = total_points + ? WHERE username=?", (pts * m, u_n))
                    db_conn.commit(); st.success("Score Added!")

            with t4: # USERS
                u_df = pd.read_sql("SELECT username, password FROM users", db_conn)
                st.table(u_df)
                target = st.selectbox("Manager", u_df['username'].tolist())
                if st.button("Kick Player"):
                    db_conn.execute("DELETE FROM users WHERE username=?", (target,))
                    db_conn.commit(); st.rerun()

            with t5: # DANGER
                if st.button("Reset Current Round Scores"):
                    db_conn.execute("DELETE FROM score_history WHERE round_name=?", (info['round_name'],))
                    db_conn.commit(); st.warning("Wiped. Use Recalculate to fix Leaderboard.")
                
                if st.button("Full System Recalculate"):
                    db_conn.execute("UPDATE users SET total_points = 0")
                    history = db_conn.execute("SELECT student, points FROM score_history").fetchall()
                    for s_n, pts in history:
                        for u_n, u_t, u_c in db_conn.execute("SELECT username, team, captain FROM users").fetchall():
                            if u_t and s_n in u_t:
                                m = 2 if s_n == u_c else 1
                                db_conn.execute("UPDATE users SET total_points = total_points + ? WHERE username=?", (pts * m, u_n))
                    db_conn.commit(); st.success("Leaderboard Rebuilt!")
