import streamlit as st
import pandas as pd
import sqlite3
import math
import numpy as np
from datetime import datetime

# --- PAGE CONFIG ---
st.set_page_config(page_title="Gate Fantasy", page_icon="⚽", layout="centered")

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('fantasy.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, team TEXT, captain TEXT, 
                  tc_available INTEGER DEFAULT 1, tc_active INTEGER DEFAULT 0, total_points REAL DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS game_state 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, round_name TEXT, subjects TEXT, is_active INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS score_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, round_name TEXT, student TEXT, subject TEXT, mark REAL, points REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS market (name TEXT PRIMARY KEY, price REAL)''')
    
    # NEW: Budget History Table
    c.execute('''CREATE TABLE IF NOT EXISTS budget_history 
                 (username TEXT, round_name TEXT, total_value REAL)''')
    
    # Initial Market Seed (Simplified for space, keep your full list)
    if c.execute("SELECT COUNT(*) FROM market").fetchone()[0] == 0:
        players = [("Ming", 36.0), ("Cirrus", 35.5), ("Forrest", 30.0), ("Geonhee", 27.0), ("Lucas Yiu", 22.0)]
        c.executemany("INSERT INTO market (name, price) VALUES (?,?)", players)
    
    conn.commit()
    return conn

db_conn = init_db()

# --- HELPER FUNCTIONS ---
def get_active_round():
    res = pd.read_sql("SELECT * FROM game_state WHERE is_active=1 LIMIT 1", db_conn)
    return res.iloc[0] if not res.empty else {"round_name": "Pre-Season", "subjects": "None"}

def calculate_fpl_points(mark):
    diff = mark - 70
    return 4 * math.pow(diff, 1.2) if diff >= 0 else -4 * math.pow(abs(diff), 1.2)

# --- BELL CURVE ENGINE ---
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
        # Map Z-Score to Price Change
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

# --- FETCH GLOBAL DATA ---
market_df = pd.read_sql("SELECT * FROM market ORDER BY price DESC", db_conn)
player_prices = dict(zip(market_df['name'], market_df['price']))
player_options = [f"{n} (£{p}m)" for n, p in player_prices.items()]
active_info = get_active_round()

# --- UI STYLING ---
st.markdown("""<style>
    .stApp { background-color: #FFFFFF; }
    .fpl-header { background: #38003c; padding: 20px; border-radius: 10px; border-bottom: 5px solid #00ff87; text-align: center; margin-bottom: 25px; color: white; }
    </style>""", unsafe_allow_html=True)

# --- AUTH LOGIC ---
if 'auth' not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    st.markdown('<div class="fpl-header"><h1>GATE FANTASY</h1></div>', unsafe_allow_html=True)
    mode = st.tabs(["Login", "Sign Up"])
    with mode[0]:
        u, p = st.text_input("User"), st.text_input("Pass", type="password")
        if st.button("Login"):
            res = db_conn.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p)).fetchone()
            if res:
                st.session_state.auth, st.session_state.user = True, u
                st.rerun()
else:
    # Fresh User Data
    u_data = pd.read_sql("SELECT * FROM users WHERE username=?", db_conn, params=(st.session_state.user,)).iloc[0]
    
    page = st.sidebar.radio("Navigation", ["Dashboard", "Leaderboard", "Player Stats", "Grade Portal", "My Squad", "Review Teams", "Admin"])

    if page == "Dashboard":
        st.markdown(f'<div class="fpl-header"><h1>{active_info["round_name"]}</h1></div>', unsafe_allow_html=True)
        st.write(f"**Current Subjects:** {active_info['subjects']}")
        
        # Budget History Chart
        st.subheader("📈 My Team Value Over Time")
        b_hist = pd.read_sql("SELECT round_name, total_value FROM budget_history WHERE username=?", db_conn, params=(st.session_state.user,))
        if not b_hist.empty:
            st.line_chart(b_hist.set_index('round_name'))
        else:
            st.info("History will populate after the first round update.")

    elif page == "Leaderboard":
        st.header("🏆 Global Standings")
        ld_df = pd.read_sql("SELECT username as Manager, total_points as Points FROM users ORDER BY total_points DESC", db_conn)
        # FIX 1: Explicitly convert to float before rounding to prevent TypeError
        ld_df['Points'] = pd.to_numeric(ld_df['Points']).round(2)
        st.dataframe(ld_df, use_container_width=True, hide_index=True)

    elif page == "My Squad":
        st.subheader("Manage Your Team")
        sel = st.multiselect("Pick 5 Players", player_options, max_selections=5)
        s_names = [s.split(" (£")[0] for s in sel]
        total_cost = sum(player_prices.get(n, 0) for n in s_names)
        
        st.metric("Total Value", f"£{total_cost}m", delta=f"{90-total_cost}m Left")
        
        if st.button("Confirm Transfer"):
            if len(s_names) == 5 and total_cost <= 90:
                db_conn.execute("UPDATE users SET team=? WHERE username=?", (", ".join(s_names), st.session_state.user))
                db_conn.commit()
                st.success("Squad Updated!")

    elif page == "Admin":
        if st.text_input("Admin Key", type="password") == st.secrets.get("ADMIN_KEY", "vinodbox43"):
            tab = st.tabs(["Round Control", "Add Scores", "User Tools", "Danger Zone"])
            
            with tab[0]:
                st.subheader("Advance Round")
                next_r = st.text_input("Next Round Name")
                next_s = st.text_input("Next Round Subjects (e.g. Math, Hass)")
                if st.button("Execute Round Transition"):
                    # 1. Update Budget History for everyone before price change
                    managers = db_conn.execute("SELECT username, team FROM users").fetchall()
                    for m_name, m_team in managers:
                        if m_team and m_team != 'None':
                            t_list = m_team.split(", ")
                            val = sum(player_prices.get(p, 0) for p in t_list)
                            db_conn.execute("INSERT INTO budget_history (username, round_name, total_value) VALUES (?,?,?)", (m_name, active_info['round_name'], val))
                    
                    # 2. Bell Curve
                    run_bell_curve(active_info['round_name'])
                    
                    # 3. New Round
                    db_conn.execute("UPDATE game_state SET is_active=0")
                    db_conn.execute("INSERT INTO game_state (round_name, subjects, is_active) VALUES (?,?,1)", (next_r, next_s))
                    db_conn.commit()
                    st.rerun()

            with tab[1]:
                # FIX 2: Separate Subject Logic
                raw_subs = active_info['subjects'].replace(",", " ").split()
                clean_subs = list(set([s.strip() for s in raw_subs]))
                
                st_sel = st.selectbox("Student Name", list(player_prices.keys()), key="score_st")
                sub_sel = st.selectbox("Subject", clean_subs, key="score_sub")
                mark_in = st.number_input("Mark Received", 0.0, 100.0)
                
                if st.button("Apply Score"):
                    pts = calculate_fpl_points(mark_in)
                    db_conn.execute("INSERT INTO score_history (round_name, student, subject, mark, points) VALUES (?,?,?,?,?)", 
                                    (active_info['round_name'], st_sel, sub_sel, mark_in, pts))
                    # Add points to users
                    for u_n, u_t, u_c in db_conn.execute("SELECT username, team, captain FROM users").fetchall():
                        if u_t and st_sel in u_t:
                            m = 2 if st_sel == u_c else 1
                            db_conn.execute("UPDATE users SET total_points = total_points + ? WHERE username=?", (pts * m, u_n))
                    db_conn.commit()
                    st.success("Score Recorded!")

            with tab[2]:
                st.subheader("User Management")
                u_df = pd.read_sql("SELECT username, password FROM users", db_conn)
                st.table(u_df)
                target = st.selectbox("Action Target", u_df['username'].tolist(), key="admin_target")
                if st.button("Kick Player"):
                    db_conn.execute("DELETE FROM users WHERE username=?", (target,))
                    db_conn.commit(); st.rerun()

            with tab[3]:
                if st.button("Reset Current Round Scores"):
                    db_conn.execute("DELETE FROM score_history WHERE round_name=?", (active_info['round_name'],))
                    db_conn.commit(); st.warning("Scores Cleared. Use Recalculate to fix Leaderboard.")
                
                if st.button("Full System Reset"):
                    db_conn.execute("DROP TABLE IF EXISTS users")
                    db_conn.execute("DROP TABLE IF EXISTS score_history")
                    db_conn.execute("DROP TABLE IF EXISTS game_state")
                    db_conn.commit(); st.rerun()
