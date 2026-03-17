import streamlit as st
import pandas as pd
import sqlite3
import math

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
    c.execute('''CREATE TABLE IF NOT EXISTS budget_history 
                 (username TEXT, round_name TEXT, total_value REAL)''')
    conn.commit()
    return conn

db_conn = init_db()
ADMIN_PASSWORD = st.secrets.get("ADMIN_KEY", "vinodbox43")

# --- BELL CURVE ENGINE ---
def run_bell_curve(round_name):
    df_scores = pd.read_sql("SELECT student, mark FROM score_history WHERE round_name=?", db_conn, params=(round_name,))
    if df_scores.empty: return
    stats = df_scores.groupby('student')['mark'].mean().reset_index()
    mean, std = stats['mark'].mean(), stats['mark'].std() if stats['mark'].std() > 0 else 1 
    c = db_conn.cursor()
    for _, row in stats.iterrows():
        z = (row['mark'] - mean) / std
        change = 5.0 if z > 1.5 else (2.0 if z > 0.5 else (0.0 if z > -0.5 else (-2.0 if z > -1.5 else -5.0)))
        c.execute("UPDATE market SET price = MAX(5.0, price + ?) WHERE name = ?", (change, row['student']))
    db_conn.commit()

def calculate_pts(mark):
    diff = mark - 70
    return 4 * math.pow(diff, 1.2) if diff >= 0 else -4 * math.pow(abs(diff), 1.2)

# --- DATA FETCH ---
market_df = pd.read_sql("SELECT * FROM market ORDER BY price DESC", db_conn)
player_prices = dict(zip(market_df['name'], market_df['price']))
active_q = pd.read_sql("SELECT * FROM game_state WHERE is_active=1 LIMIT 1", db_conn)
info = active_q.iloc[0] if not active_q.empty else {"round_name": "Round 1", "subjects": "Maths"}

# --- UI ---
st.sidebar.title("GATE FANTASY")
if 'auth' not in st.session_state: st.session_state.auth = False

if not st.session_state.auth:
    t1, t2 = st.tabs(["Login", "Sign Up"])
    with t1:
        u, p = st.text_input("User"), st.text_input("Pass", type="password")
        if st.button("Login"):
            res = db_conn.execute("SELECT * FROM users WHERE username=? AND password=?", (u, p)).fetchone()
            if res: st.session_state.auth, st.session_state.user = True, u; st.rerun()
    with t2:
        nu, npw = st.text_input("New User"), st.text_input("New Pass", type="password")
        if st.button("Sign Up"):
            try:
                db_conn.execute("INSERT INTO users (username, password, team, captain) VALUES (?,?,'None','None')", (nu, npw))
                db_conn.commit(); st.success("Created!")
            except: st.error("Taken.")
else:
    u_data = pd.read_sql("SELECT * FROM users WHERE username=?", db_conn, params=(st.session_state.user,)).iloc[0]
    page = st.sidebar.radio("Menu", ["Dashboard", "Leaderboard", "Round History", "Player Stats", "Grade Portal", "My Squad", "Review Teams", "Admin"])

    if page == "Dashboard":
        st.header(f"Current: {info['round_name']}")
        st.subheader("Market Prices")
        st.table(market_df)

    elif page == "Leaderboard":
        st.header("Overall Standings")
        st.dataframe(pd.read_sql("SELECT username, total_points FROM users ORDER BY total_points DESC", db_conn))

    elif page == "Round History":
        st.header("Standings per Round")
        all_rounds = pd.read_sql("SELECT DISTINCT round_name FROM score_history", db_conn)['round_name'].tolist()
        sel_r = st.selectbox("Select Round", all_rounds)
        if sel_r:
            # This calculates round-specific points based on score_history
            round_data = pd.read_sql("SELECT student, points FROM score_history WHERE round_name=?", db_conn, params=(sel_r,))
            st.write(f"Data for {sel_r}")
            st.dataframe(round_data)

    elif page == "Player Stats":
        st.header("Student Performance")
        stats = pd.read_sql("SELECT student, SUM(points) as total_pts_earned FROM score_history GROUP BY student ORDER BY total_pts_earned DESC", db_conn)
        st.dataframe(stats)

    elif page == "Grade Portal":
        st.header("Current Round Grades")
        grades = pd.read_sql("SELECT student, subject, mark FROM score_history WHERE round_name=?", db_conn, params=(info['round_name'],))
        if not grades.empty: st.dataframe(grades.pivot_table(index='student', columns='subject', values='mark'))
        else: st.info("No grades yet.")

    elif page == "My Squad":
        st.header("Squad Management")
        cur_t = u_data['team'].split(", ") if u_data['team'] != 'None' else []
        st.write(f"Current Team: {', '.join(cur_t)}")
        budget = sum(player_prices.get(p, 0) for p in cur_t)
        st.metric("Budget Used", f"£{budget}m", f"{90-budget}m left")
        
        picks = st.multiselect("Pick 5", [f"{n} (£{p}m)" for n,p in player_prices.items()], max_selections=5)
        new_names = [p.split(" (£")[0] for p in picks]
        cap = st.selectbox("Captain", new_names if new_names else (cur_t if cur_t else ["None"]))
        tc = st.checkbox("Use Triple Captain?") if u_data['tc_available'] else False
        
        if st.button("Send for Approval"):
            if len(new_names) == 5 and sum(player_prices.get(n,0) for n in new_names) <= 90:
                db_conn.execute("UPDATE users SET pending_team=?, pending_captain=?, tc_active=? WHERE username=?", (", ".join(new_names), cap, 1 if tc else 0, st.session_state.user))
                db_conn.commit(); st.success("Sent!")

    elif page == "Review Teams":
        st.header("Global Manager Review")
        mgrs = pd.read_sql("SELECT username, team, captain, tc_active FROM users", db_conn)
        for _, r in mgrs.iterrows():
            with st.expander(f"Manager: {r['username']}"):
                st.write(f"Team: {r['team']} | Captain: {r['captain']}")
                if r['tc_active']: st.warning("🚀 TC ACTIVE")

    elif page == "Admin":
        if st.text_input("Key", type="password") == ADMIN_PASSWORD:
            t1, t2, t3, t4, t5 = st.tabs(["Approvals", "Round Control", "Grid Scoring", "User Tools", "Danger Zone"])
            
            with t1: # Approvals
                pend = pd.read_sql("SELECT * FROM users WHERE pending_team IS NOT NULL", db_conn)
                for _, pr in pend.iterrows():
                    st.write(f"{pr['username']} wants {pr['pending_team']}")
                    if st.button("Approve", key=pr['username']):
                        db_conn.execute("UPDATE users SET team=pending_team, captain=pending_captain, pending_team=NULL, pending_captain=NULL WHERE username=?", (pr['username'],))
                        db_conn.commit(); st.rerun()

            with t2: # Round Control + Bell Curve
                nr, ns = st.text_input("Next Round Name"), st.text_input("Subjects")
                if st.button("Activate Bell Curve & Cycle Round"):
                    run_bell_curve(info['round_name'])
                    db_conn.execute("UPDATE users SET tc_available=0 WHERE tc_active=1")
                    db_conn.execute("UPDATE users SET tc_active=0")
                    db_conn.execute("UPDATE game_state SET is_active=0")
                    db_conn.execute("INSERT INTO game_state (round_name, subjects, is_active) VALUES (?,?,1)", (nr, ns))
                    db_conn.commit(); st.rerun()

            with t3: # Grid Scoring
                st.subheader("Grid Input")
                subjects = [s.strip() for s in info['subjects'].split(",")]
                grid_df = pd.DataFrame({'Student': list(player_prices.keys())})
                for s in subjects: grid_df[s] = 0.0
                edited = st.data_editor(grid_df)
                if st.button("Save Scores"):
                    for _, row in edited.iterrows():
                        for s in subjects:
                            if row[s] > 0:
                                p = calculate_pts(row[s])
                                db_conn.execute("INSERT INTO score_history (round_name, student, subject, mark, points) VALUES (?,?,?,?,?)", (info['round_name'], row['Student'], s, row[s], p))
                                for u_n, u_t, u_c, u_tc in db_conn.execute("SELECT username, team, captain, tc_active FROM users").fetchall():
                                    if u_t and row['Student'] in u_t:
                                        m = 3 if (row['Student']==u_c and u_tc) else (2 if row['Student']==u_c else 1)
                                        db_conn.execute("UPDATE users SET total_points = total_points + ? WHERE username=?", (p*m, u_n))
                    db_conn.commit(); st.success("Scores Saved!")

            with t4: # User Tools (Password, TC Target, TC Restore)
                u_m = pd.read_sql("SELECT username, password, tc_available, tc_active, pending_captain FROM users", db_conn)
                st.dataframe(u_m) # TC Target is visible as pending_captain or captain
                target = st.selectbox("Manager", u_m['username'].tolist())
                new_p = st.text_input("New Password")
                if st.button("Update Pass"):
                    db_conn.execute("UPDATE users SET password=? WHERE username=?", (new_p, target))
                    db_conn.commit(); st.success("Changed.")
                if st.button("Restore TC"):
                    db_conn.execute("UPDATE users SET tc_available=1 WHERE username=?", (target,))
                    db_conn.commit(); st.success("Restored.")

            with t5: # Danger Zone
                if st.button("🛠️ Recalculate Scores"):
                    db_conn.execute("UPDATE users SET total_points = 0")
                    for sn, pts in db_conn.execute("SELECT student, points FROM score_history").fetchall():
                        for un, ut, uc, utc in db_conn.execute("SELECT username, team, captain, tc_active FROM users").fetchall():
                            if ut and sn in ut:
                                m = 3 if (sn==uc and utc) else (2 if sn==uc else 1)
                                db_conn.execute("UPDATE users SET total_points = total_points + ? WHERE username=?", (pts*m, un))
                    db_conn.commit(); st.success("Recalculated.")
                if st.button("🔥 TOTAL RESET"):
                    db_conn.execute("DROP TABLE users"); db_conn.execute("DROP TABLE score_history")
                    db_conn.commit(); st.rerun()
