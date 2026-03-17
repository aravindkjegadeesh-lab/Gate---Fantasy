import streamlit as st
import pandas as pd
import sqlite3
import math

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
    
    # MIGRATION: Keeps your data safe while fixing structure
    cursor = conn.execute('PRAGMA table_info(game_state)')
    cols = [info[1] for info in cursor.fetchall()]
    if 'is_active' not in cols:
        c.execute('ALTER TABLE game_state ADD COLUMN is_active INTEGER DEFAULT 0')
    conn.commit()
    return conn

db_conn = init_db()

# --- ADMIN PASSWORD SECURITY ---
# Forrest can't see this on GitHub if you put it in Streamlit Secrets
ADMIN_PASSWORD = st.secrets.get("ADMIN_KEY", "vinodbox43")

def calculate_fpl_points(mark):
    diff = mark - 70
    return 4 * math.pow(diff, 1.2) if diff >= 0 else -4 * math.pow(abs(diff), 1.2)

MARKET_DATA = [
    {"name": "Ming", "price": 36.0}, {"name": "Cirrus", "price": 35.5}, {"name": "Gautham", "price": 33.0}, 
    {"name": "Dev", "price": 32.5}, {"name": "Forrest", "price": 30.0}, {"name": "Talal", "price": 28.5}, 
    {"name": "Geonhee", "price": 27.0}, {"name": "Hardy", "price": 23.0}, {"name": "Ethan Yuen", "price": 22.5}, 
    {"name": "Abdul", "price": 22.0}, {"name": "Lucas Yiu", "price": 22.0}, {"name": "Adhvik", "price": 21.0}, 
    {"name": "Sid", "price": 20.0}, {"name": "Barnabas", "price": 20.0}, {"name": "Komron", "price": 20.0}, 
    {"name": "Michael", "price": 20.0}, {"name": "Nathan", "price": 20.0}, {"name": "Ethan Wang", "price": 19.5}, 
    {"name": "Josh", "price": 19.0}, {"name": "Daren", "price": 17.5}, {"name": "Aravind", "price": 17.0}, 
    {"name": "Alfie", "price": 16.0}, {"name": "Musa", "price": 15.0}, {"name": "Maxwell", "price": 14.0}, 
    {"name": "Andre", "price": 14.0}, {"name": "Inesh", "price": 14.0}, {"name": "Maximus", "price": 13.0}, 
    {"name": "Jared", "price": 13.0}, {"name": "Lucas Lau", "price": 12.0}, {"name": "Alden", "price": 11.0}, 
    {"name": "Sanjit", "price": 10.5}, {"name": "Yashwant", "price": 10.5}, {"name": "Maxi", "price": 10.0}, 
    {"name": "Raymond", "price": 9.5}, {"name": "Hassan", "price": 9.0}, {"name": "Lucas Kong", "price": 8.0}
]
player_prices = {p['name']: p['price'] for p in MARKET_DATA}
player_options = [f"{p['name']} (£{p['price']}m)" for p in MARKET_DATA]

# --- STYLE ---
st.markdown("""<style>
    .stApp { background-color: #FFFFFF; }
    label, p, .stMarkdown { color: #000000 !important; font-weight: 700 !important; }
    .fpl-header { background: #38003c; padding: 20px; border-radius: 10px; border-bottom: 5px solid #00ff87; text-align: center; margin-bottom: 25px; }
    .card { background: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #38003c; margin-bottom: 10px; color: #38003c; }
    </style>""", unsafe_allow_html=True)

if 'auth' not in st.session_state: st.session_state.auth = False
if 'user' not in st.session_state: st.session_state.user = None

# --- APP LOGIC ---
if not st.session_state.auth:
    st.markdown('<div class="fpl-header"><h1 style="color:#00ff87;">GATE FANTASY</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["Login", "Sign Up"])
    with t1:
        u_in = st.text_input("Username")
        p_in = st.text_input("Password", type="password")
        if st.button("Log In", type="primary"):
            res = db_conn.execute("SELECT * FROM users WHERE username=? AND password=?", (u_in, p_in)).fetchone()
            if res:
                st.session_state.auth, st.session_state.user = True, u_in
                st.rerun()
    with t2:
        nu, np = st.text_input("New User"), st.text_input("New Pass", type="password")
        if st.button("Register"):
            try:
                db_conn.execute("INSERT INTO users (username, password, team, captain) VALUES (?, ?, 'None', 'None')", (nu, np))
                db_conn.commit()
                st.success("Registered!")
            except: st.error("User exists.")
else:
    # Get fresh user data every time to prevent "Broken" session exploits
    u_data = pd.read_sql("SELECT * FROM users WHERE username=?", db_conn, params=(st.session_state.user,)).iloc[0]
    active_q = pd.read_sql("SELECT * FROM game_state WHERE is_active=1 LIMIT 1", db_conn)
    info = active_q.iloc[0] if not active_q.empty else {"round_name": "Round 1", "subjects": "Maths"}

    st.sidebar.title(f"Hi, {st.session_state.user}")
    st.sidebar.write(f"Points: {round(float(u_data['total_points']), 2)}")
    
    page = st.sidebar.radio("Nav", ["Dashboard", "Leaderboard", "Player Stats", "Grade Portal", "My Squad", "Review Teams", "Admin"])

    if page == "Dashboard":
        st.markdown('<div class="fpl-header"><h1 style="color:#00ff87;">GATE FANTASY</h1></div>', unsafe_allow_html=True)
        st.metric("Current Round", info['round_name'])
        st.info(f"📍 Active Subjects: {info['subjects']}")
        hist = pd.read_sql("SELECT student, subject, mark, points FROM score_history ORDER BY id DESC LIMIT 5", db_conn)
        if not hist.empty: st.table(hist)

    elif page == "Leaderboard":
        st.header("🏆 Standings")
        ld_df = pd.read_sql("SELECT username as Manager, total_points as Points FROM users ORDER BY total_points DESC", db_conn)
        if not ld_df.empty:
            ld_df['Points'] = pd.to_numeric(ld_df['Points']).round(2)
            st.dataframe(ld_df, use_container_width=True, hide_index=True)

    elif page == "Player Stats":
        st.header("📊 Total Student Points")
        stats = pd.read_sql("SELECT student as Name, SUM(points) as Total_Points FROM score_history GROUP BY student ORDER BY Total_Points DESC", db_conn)
        if not stats.empty:
            stats['Total_Points'] = pd.to_numeric(stats['Total_Points']).round(2)
            st.dataframe(stats, use_container_width=True, hide_index=True)

    elif page == "Grade Portal":
        st.header("📝 Grade History")
        raw = pd.read_sql("SELECT student, subject, mark FROM score_history", db_conn)
        if not raw.empty:
            # Pivot fix to prevent "Object" errors in tables
            pivot_table = raw.pivot_table(index='student', columns='subject', values='mark', aggfunc='first').fillna("-")
            st.dataframe(pivot_table, use_container_width=True)

    elif page == "My Squad":
        st.markdown(f'<div class="card"><b>Team:</b> {u_data["team"]}<br><b>Captain:</b> {u_data["captain"]}</div>', unsafe_allow_html=True)
        sel = st.multiselect("Select 5 Players", player_options, max_selections=5)
        s_names = [s.split(" (£")[0] for s in sel]
        cost = sum(player_prices[n] for n in s_names)
        st.write(f"Budget: £{cost}m / £90m")
        
        cap_choice = st.selectbox("Select Captain (x2)", s_names) if s_names else u_data['captain']
        
        tc_active_val = u_data['tc_active']
        if u_data['tc_available'] == 1:
            st.markdown("### 🚀 Triple Captain Chip")
            use_tc = st.checkbox("Activate Triple Captain?", value=bool(u_data['tc_active']))
            if use_tc:
                tc_target = st.selectbox("Target for TC x3:", s_names)
                tc_active_val, cap_choice = 1, tc_target
            else: tc_active_val = 0
        
        if st.button("Save Squad"):
            if len(s_names) == 5 and cost <= 90:
                c = db_conn.cursor()
                # Catch-up logic
                round_scores = c.execute("SELECT student, points FROM score_history WHERE round_name=?", (info['round_name'],)).fetchall()
                total_catchup = 0
                for s_n, s_p in round_scores:
                    if s_n in s_names:
                        mult = 3 if (s_n == cap_choice and tc_active_val == 1) else (2 if s_n == cap_choice else 1)
                        total_catchup += (s_p * mult)
                
                c.execute("UPDATE users SET team=?, captain=?, tc_active=? WHERE username=?", 
                                (", ".join(s_names), cap_choice, tc_active_val, st.session_state.user))
                
                if u_data['team'] == 'None' or u_data['team'] == '': 
                    c.execute("UPDATE users SET total_points = total_points + ? WHERE username=?", (total_catchup, st.session_state.user))
                
                if tc_active_val == 1:
                    c.execute("UPDATE users SET tc_available=0, tc_active=0 WHERE username=?", (st.session_state.user,))
                
                db_conn.commit(); st.success("Squad Saved!"); st.rerun()

    elif page == "Review Teams":
        st.header("👀 Manager Teams")
        others = pd.read_sql("SELECT username, team, captain, tc_active FROM users WHERE team != 'None'", db_conn)
        for _, row in others.iterrows():
            tc_tag = " (🚀 TC)" if row['tc_active'] == 1 else ""
            with st.expander(f"{row['username']}{tc_tag}"):
                st.write(f"**Team:** {row['team']} | **Captain:** {row['captain']}")

    elif page == "Admin":
        st.header("🔐 Admin Controls")
        if st.text_input("Enter Admin Key", type="password") == ADMIN_PASSWORD:
            t1, t2, t3, t4, t5 = st.tabs(["Set Round", "Round Archives", "Apply Score", "User Tools", "Reset"])
            
            with t1:
                st.subheader("Start New Round")
                nr = st.text_input("Round Name")
                ns = st.text_input("Active Subjects (Comma separated)")
                if st.button("Start Round"):
                    c = db_conn.cursor()
                    c.execute("UPDATE game_state SET is_active=0")
                    c.execute("INSERT INTO game_state (round_name, subjects, is_active) VALUES (?,?,1)", (nr, ns))
                    db_conn.commit(); st.success(f"{nr} Started!"); st.rerun()

            with t2:
                st.subheader("📚 Archive")
                rds = pd.read_sql("SELECT round_name, subjects, is_active FROM game_state", db_conn)
                st.table(rds)
                switch = st.selectbox("Activate Old Round?", rds['round_name'].tolist())
                if st.button("Switch"):
                    c = db_conn.cursor()
                    c.execute("UPDATE game_state SET is_active=0")
                    c.execute("UPDATE game_state SET is_active=1 WHERE round_name=?", (switch,))
                    db_conn.commit(); st.rerun()

            with t3:
                st.subheader("Add Score")
                st_n = st.selectbox("Student", [p['name'] for p in MARKET_DATA])
                
                # FIXED: This splits the subject string so they aren't clumped together
                subject_string = info['subjects'] if info['subjects'] else "General"
                # Split by space OR comma to be safe
                sub_list = [s.strip() for s in subject_string.replace(",", " ").split(" ") if s.strip()]
                sub_n = st.selectbox("Select Subject", list(set(sub_list)))
                
                mk = st.number_input("Mark", 0.0, 100.0)
                if st.button("Apply Score"):
                    c = db_conn.cursor()
                    new_pts = calculate_fpl_points(mk)
                    c.execute("INSERT INTO score_history (round_name, student, subject, mark, points) VALUES (?,?,?,?,?)", (info['round_name'], st_n, sub_n, mk, new_pts))
                    # Point distribution logic
                    for u_n, u_t, u_c, u_tc_act in c.execute("SELECT username, team, captain, tc_active FROM users").fetchall():
                        if u_t and st_n in u_t:
                            m = 3 if (st_n == u_c and u_tc_act == 1) else (2 if st_n == u_c else 1)
                            c.execute("UPDATE users SET total_points = total_points + ? WHERE username=?", (new_pts * m, u_n))
                    db_conn.commit(); st.success(f"Score added!")

            with t4:
                # View Passwords still visible here for you
                u_df = pd.read_sql("SELECT username, password, total_points, tc_available FROM users", db_conn)
                st.dataframe(u_df, use_container_width=True)
                target = st.selectbox("User", u_df['username'].tolist())
                new_p = st.text_input("New Password")
                if st.button("Update Pass"):
                    db_conn.execute("UPDATE users SET password=? WHERE username=?", (new_p, target))
                    db_conn.commit(); st.success("Updated!")
                if st.button("Restore TC"):
                    db_conn.execute("UPDATE users SET tc_available=1, tc_active=0 WHERE username=?", (target,))
                    db_conn.commit(); st.success("TC Refilled")

            with t5:
                if st.button("🛠️ RECALCULATE LEADERBOARD"):
                    c = db_conn.cursor()
                    c.execute("UPDATE users SET total_points = 0")
                    history = c.execute("SELECT student, points FROM score_history").fetchall()
                    for s_name, s_pts in history:
                        for u_n, u_t, u_c, u_tc_av in c.execute("SELECT username, team, captain, tc_available FROM users").fetchall():
                            if u_t and s_name in u_t:
                                m = 3 if (s_name == u_c and u_tc_av == 0) else (2 if s_name == u_c else 1)
                                c.execute("UPDATE users SET total_points = total_points + ? WHERE username=?", (s_pts * m, u_n))
                    db_conn.commit(); st.success("Rebuilt!"); st.rerun()
