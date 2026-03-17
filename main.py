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
    # Users & Game State
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, password TEXT, team TEXT, captain TEXT, 
                  tc_available INTEGER DEFAULT 1, tc_active INTEGER DEFAULT 0, total_points REAL DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS game_state 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, round_name TEXT, subjects TEXT, is_active INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS score_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, round_name TEXT, student TEXT, subject TEXT, mark REAL, points REAL)''')
    
    # NEW: Market Table for Player Prices
    c.execute('''CREATE TABLE IF NOT EXISTS market (name TEXT PRIMARY KEY, price REAL)''')
    
    # Seed the market if it's empty (so you don't lose the initial list)
    check_market = c.execute("SELECT COUNT(*) FROM market").fetchone()[0]
    if check_market == 0:
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
    
    # Migration for game_state
    cursor = conn.execute('PRAGMA table_info(game_state)')
    cols = [info[1] for info in cursor.fetchall()]
    if 'is_active' not in cols:
        c.execute('ALTER TABLE game_state ADD COLUMN is_active INTEGER DEFAULT 0')
        
    conn.commit()
    return conn

db_conn = init_db()

# --- ADMIN PASSWORD ---
ADMIN_PASSWORD = st.secrets.get("ADMIN_KEY", "vinodbox43")

# --- FETCH DYNAMIC MARKET DATA ---
market_df = pd.read_sql("SELECT * FROM market ORDER BY price DESC", db_conn)
player_prices = dict(zip(market_df['name'], market_df['price']))
player_options = [f"{row['name']} (£{row['price']}m)" for _, row in market_df.iterrows()]

def calculate_fpl_points(mark):
    diff = mark - 70
    return 4 * math.pow(diff, 1.2) if diff >= 0 else -4 * math.pow(abs(diff), 1.2)

# --- STYLE ---
st.markdown("""<style>
    .stApp { background-color: #FFFFFF; }
    label, p, .stMarkdown { color: #000000 !important; font-weight: 700 !important; }
    .fpl-header { background: #38003c; padding: 20px; border-radius: 10px; border-bottom: 5px solid #00ff87; text-align: center; margin-bottom: 25px; }
    .card { background: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #38003c; margin-bottom: 10px; color: #38003c; }
    </style>""", unsafe_allow_html=True)

if 'auth' not in st.session_state: st.session_state.auth = False
if 'user' not in st.session_state: st.session_state.user = None

# --- AUTH ---
if not st.session_state.auth:
    st.markdown('<div class="fpl-header"><h1 style="color:#00ff87;">GATE FANTASY</h1></div>', unsafe_allow_html=True)
    t1, t2 = st.tabs(["Login", "Sign Up"])
    with t1:
        u_in, p_in = st.text_input("Username"), st.text_input("Password", type="password")
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
    u_data = pd.read_sql("SELECT * FROM users WHERE username=?", db_conn, params=(st.session_state.user,)).iloc[0]
    active_q = pd.read_sql("SELECT * FROM game_state WHERE is_active=1 LIMIT 1", db_conn)
    info = active_q.iloc[0] if not active_q.empty else {"round_name": "Round 1", "subjects": "Maths"}

    page = st.sidebar.radio("Nav", ["Dashboard", "Leaderboard", "Player Stats", "Grade Portal", "My Squad", "Review Teams", "Admin"])

    # ... [Dashboard, Leaderboard, Player Stats, Grade Portal, My Squad, Review Teams logic remains identical to previous version] ...
    # (Note: They all now use the dynamic player_options and player_prices fetched from the DB)

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

    elif page == "My Squad":
        st.markdown(f'<div class="card"><b>Team:</b> {u_data["team"]}<br><b>Captain:</b> {u_data["captain"]}</div>', unsafe_allow_html=True)
        sel = st.multiselect("Select 5 Players", player_options, max_selections=5)
        s_names = [s.split(" (£")[0] for s in sel]
        cost = sum(player_prices.get(n, 0) for n in s_names)
        st.write(f"Budget: £{cost}m / £90m")
        
        cap_choice = st.selectbox("Select Captain (x2)", s_names) if s_names else u_data['captain']
        
        if st.button("Save Squad"):
            if len(s_names) == 5 and cost <= 90:
                c = db_conn.cursor()
                c.execute("UPDATE users SET team=?, captain=? WHERE username=?", (", ".join(s_names), cap_choice, st.session_state.user))
                db_conn.commit(); st.success("Squad Saved!"); st.rerun()

    elif page == "Admin":
        st.header("🔐 Admin Controls")
        if st.text_input("Enter Admin Key", type="password") == ADMIN_PASSWORD:
            t1, t2, t3, t4, t5, t6 = st.tabs(["Set Round", "Round Archives", "Apply Score", "User Tools", "Market Manager", "Reset"])
            
            with t3: # Apply Score
                st.subheader("Add Score")
                st_n = st.selectbox("Student", list(player_prices.keys()))
                sub_list = [s.strip() for s in info['subjects'].replace(",", " ").split(" ") if s.strip()]
                sub_n = st.selectbox("Select Subject", list(set(sub_list)))
                mk = st.number_input("Mark", 0.0, 100.0)
                if st.button("Apply Score"):
                    c = db_conn.cursor()
                    new_pts = calculate_fpl_points(mk)
                    c.execute("INSERT INTO score_history (round_name, student, subject, mark, points) VALUES (?,?,?,?,?)", (info['round_name'], st_n, sub_n, mk, new_pts))
                    # Distribute points...
                    for u_n, u_t, u_c in c.execute("SELECT username, team, captain FROM users").fetchall():
                        if u_t and st_n in u_t:
                            m = 2 if st_n == u_c else 1
                            c.execute("UPDATE users SET total_points = total_points + ? WHERE username=?", (new_pts * m, u_n))
                    db_conn.commit(); st.success(f"Score added!")

            with t5: # Market Manager
                st.subheader("Edit Player Prices")
                st.write("Current Market:")
                st.dataframe(market_df, hide_index=True)
                
                col1, col2 = st.columns(2)
                p_to_edit = col1.selectbox("Select Student to Price Change", market_df['name'].tolist())
                new_price = col2.number_input("New Price (£m)", value=player_prices[p_to_edit])
                
                if st.button("Update Price"):
                    db_conn.execute("UPDATE market SET price=? WHERE name=?", (new_price, p_to_edit))
                    db_conn.commit()
                    st.success(f"Updated {p_to_edit} to £{new_price}m")
                    st.rerun()

            # (Rest of admin tabs t1, t2, t4, t6 remain the same)
