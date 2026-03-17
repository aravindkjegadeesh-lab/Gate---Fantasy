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

# --- AUTOMATED POINT LOGIC ---
def calculate_pts(mark):
    diff = mark - 70
    return 4 * math.pow(diff, 1.2) if diff >= 0 else -4 * math.pow(abs(diff), 1.2)

def sync_all_points():
    """Wipes and recalculates all user points based on score history and team rosters."""
    c = db_conn.cursor()
    c.execute("UPDATE users SET total_points = 0")
    # Fetch every score ever recorded
    scores = c.execute("SELECT round_name, student, points FROM score_history").fetchall()
    # Fetch every user's current team/captain
    users = c.execute("SELECT username, team, captain, tc_active FROM users").fetchall()
    
    for r_name, student, pts in scores:
        for u_name, team, cap, tc in users:
            if team and student in team.split(", "):
                multiplier = 1
                if student == cap:
                    multiplier = 3 if tc == 1 else 2
                c.execute("UPDATE users SET total_points = total_points + ? WHERE username = ?", (pts * multiplier, u_name))
    db_conn.commit()

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
        st.header(f"Active Round: {info['round_name']}")
        st.table(market_df)

    elif page == "Leaderboard":
        st.header("Overall Standings")
        st.dataframe(pd.read_sql("SELECT username, total_points FROM users ORDER BY total_points DESC", db_conn), use_container_width=True)

    elif page == "Round History":
        st.header("Round Leaderboards")
        all_rounds = pd.read_sql("SELECT DISTINCT round_name FROM score_history", db_conn)['round_name'].tolist()
        sel_r = st.selectbox("Select Round to View Standings", all_rounds)
        if sel_r:
            # Logic: Cross-reference users' teams with scores from that specific round
            scores = pd.read_sql("SELECT student, points FROM score_history WHERE round_name=?", db_conn, params=(sel_r,))
            users = pd.read_sql("SELECT username, team, captain, tc_active FROM users", db_conn)
            
            rd_results = []
            for _, u in users.iterrows():
                u_pts = 0
                if u['team'] and u['team'] != 'None':
                    for _, s in scores.iterrows():
                        if s['student'] in u['team'].split(", "):
                            mult = 1
                            if s['student'] == u['captain']: mult = 3 if u['tc_active'] else 2
                            u_pts += (s['points'] * mult)
                rd_results.append({"Manager": u['username'], "Round Points": round(u_pts, 2)})
            
            st.dataframe(pd.DataFrame(rd_results).sort_values(by="Round Points", ascending=False), use_container_width=True)

    elif page == "Player Stats":
        st.header("Player Points Earned")
        st.dataframe(pd.read_sql("SELECT student, SUM(points) as points_total FROM score_history GROUP BY student ORDER BY points_total DESC", db_conn))

    elif page == "Grade Portal":
        st.header(f"Inputted Grades: {info['round_name']}")
        grades = pd.read_sql("SELECT student, subject, mark FROM score_history WHERE round_name=?", db_conn, params=(info['round_name'],))
        if not grades.empty: st.dataframe(grades.pivot_table(index='student', columns='subject', values='mark'))

    elif page == "My Squad":
        st.header("Build Your Squad")
        cur_t = u_data['team'].split(", ") if u_data['team'] != 'None' else []
        budget = sum(player_prices.get(p, 0) for p in cur_t)
        st.metric("Budget", f"£{budget}m", f"{90-budget}m left")
        
        picks = st.multiselect("Select 5 Players", [f"{n} (£{p}m)" for n,p in player_prices.items()], max_selections=5)
        new_names = [p.split(" (£")[0] for p in picks]
        cap = st.selectbox("Captain", new_names if new_names else (cur_t if cur_t else ["None"]))
        tc = st.checkbox("Use Triple Captain?") if u_data['tc_available'] else False
        
        if st.button("Submit Squad for Approval"):
            if len(new_names) == 5 and sum(player_prices.get(n,0) for n in new_names) <= 90:
                db_conn.execute("UPDATE users SET pending_team=?, pending_captain=?, tc_active=? WHERE username=?", (", ".join(new_names), cap, 1 if tc else 0, st.session_state.user))
                db_conn.commit(); st.success("Request sent to Admin!")

    elif page == "Review Teams":
        st.header("Manager Review")
        mgrs = pd.read_sql("SELECT username, team, captain, tc_active FROM users", db_conn)
        for _, r in mgrs.iterrows():
            with st.expander(f"Manager: {r['username']}"):
                st.write(f"Team: {r['team']} | Captain: {r['captain']}")
                if r['tc_active']: st.warning("🚀 TC ACTIVE")

    elif page == "Admin":
        if st.text_input("Key", type="password") == ADMIN_PASSWORD:
            t1, t2, t3, t4, t5 = st.tabs(["Approvals", "Round Control", "Grid Scoring", "User Tools", "Danger Zone"])
            
            with t1: # Approvals (Automatic point sync on approve)
                pend = pd.read_sql("SELECT * FROM users WHERE pending_team IS NOT NULL", db_conn)
                for _, pr in pend.iterrows():
                    st.write(f"{pr['username']} -> {pr['pending_team']}")
                    if st.button("Approve", key=pr['username']):
                        db_conn.execute("UPDATE users SET team=pending_team, captain=pending_captain, pending_team=NULL, pending_captain=NULL WHERE username=?", (pr['username'],))
                        db_conn.commit()
                        sync_all_points() # AUTO SYNC
                        st.rerun()

            with t2: # Round Control (Bell Curve)
                nr, ns = st.text_input("Next Round Name"), st.text_input("Subjects")
                if st.button("Cycle Round & Bell Curve"):
                    run_bell_curve(info['round_name'])
                    db_conn.execute("UPDATE users SET tc_available=0 WHERE tc_active=1")
                    db_conn.execute("UPDATE users SET tc_active=0")
                    db_conn.execute("UPDATE game_state SET is_active=0")
                    db_conn.execute("INSERT INTO game_state (round_name, subjects, is_active) VALUES (?,?,1)", (nr, ns))
                    db_conn.commit(); st.rerun()

            with t3: # Grid Scoring (Automatic point sync on save)
                subjects = [s.strip() for s in info['subjects'].split(",")]
                grid_df = pd.DataFrame({'Student': list(player_prices.keys())})
                for s in subjects: grid_df[s] = 0.0
                edited = st.data_editor(grid_df)
                if st.button("Save & Sync Points"):
                    for _, row in edited.iterrows():
                        for s in subjects:
                            if row[s] > 0:
                                p = calculate_pts(row[s])
                                db_conn.execute("INSERT INTO score_history (round_name, student, subject, mark, points) VALUES (?,?,?,?,?)", (info['round_name'], row['Student'], s, row[s], p))
                    db_conn.commit()
                    sync_all_points() # AUTO SYNC
                    st.success("Points Automated!")

            with t4: # User Tools (Visible Pass, Target, TC Restore)
                u_m = pd.read_sql("SELECT username, password, team, captain, tc_available FROM users", db_conn)
                st.dataframe(u_m) 
                target = st.selectbox("Manager", u_m['username'].tolist())
                new_p = st.text_input("New Password")
                if st.button("Update"):
                    db_conn.execute("UPDATE users SET password=? WHERE username=?", (new_p, target))
                    db_conn.commit(); st.success("Updated.")
                if st.button("Restore TC"):
                    db_conn.execute("UPDATE users SET tc_available=1 WHERE username=?", (target,))
                    db_conn.commit(); st.success("Restored.")

            with t5: # Danger Zone
                if st.button("🛠️ Full Recalculate"):
                    sync_all_points()
                    st.success("Leaderboard Refreshed.")
                if st.button("🔥 TOTAL SYSTEM RESET"):
                    db_conn.execute("DROP TABLE users"); db_conn.execute("DROP TABLE score_history")
                    db_conn.commit(); st.rerun()
