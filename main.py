import streamlit as st
import pandas as pd
import math

# --- PAGE CONFIG ---
st.set_page_config(page_title="Gate Fantasy", page_icon="⚽", layout="centered")

# --- CUSTOM CSS FOR THE FPL LOOK ---
st.markdown("""
    <style>
    /* Background and Main Colors */
    .stApp { background-color: #121212; }
    
    /* Header Styling */
    .fpl-header {
        background: linear-gradient(90deg, #38003c 0%, #7a00ff 100%);
        padding: 30px;
        border-radius: 15px;
        border-bottom: 5px solid #00ff87;
        text-align: center;
        margin-bottom: 30px;
    }
    
    .fpl-title { color: #00ff87; font-size: 42px; font-weight: 800; margin: 0; }
    .fpl-subtitle { color: white; font-size: 18px; opacity: 0.9; }

    /* Button Styling */
    .stButton>button {
        background-color: #00ff87 !important;
        color: #38003c !important;
        font-weight: bold !important;
        border-radius: 8px !important;
        border: none !important;
        height: 3em !important;
        transition: 0.3s !important;
    }
    .stButton>button:hover { transform: scale(1.02); opacity: 0.9; }

    /* Card Styling */
    .player-card {
        background-color: #1e1e1e;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #333;
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- PLAYER DATA ---
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
df_market = pd.DataFrame(MARKET_DATA)

# --- APP NAVIGATION ---
if 'page' not in st.session_state:
    st.session_state.page = 'Home'

def set_page(page_name):
    st.session_state.page = page_name

# Sidebar Navigation
st.sidebar.markdown("<h2 style='color:#00ff87;'>Gate Fantasy</h2>", unsafe_allow_html=True)
if st.sidebar.button("🏠 Home Screen"): set_page('Home')
if st.sidebar.button("🏃 Build My Team"): set_page('Team')
if st.sidebar.button("🏆 Leaderboard"): set_page('Leader')
if st.sidebar.button("🔑 Admin Access"): set_page('Admin')

# --- PAGES ---

if st.session_state.page == 'Home':
    st.markdown("""
        <div class="fpl-header">
            <p class="fpl-title">GATE FANTASY</p>
            <p class="fpl-subtitle">Season 2025/26 | Every Test Counts</p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 👋 Welcome Manager")
        manager_name = st.text_input("Enter your name to sign in:", placeholder="e.g. Lucas")
        if st.button("Get Started"):
            set_page('Team')
            st.rerun()
            
    with col2:
        st.markdown("### 📊 Gameweek Status")
        st.info("**Next Gameweek:** GW 1\n\n**Deadline:** Sunday 18:00")
        st.success("Registration is currently **OPEN**")

elif st.session_state.page == 'Team':
    st.title("🏃 Build Your Squad")
    st.markdown("Select **5 players** staying within the **£90m** budget.")
    
    selected_names = st.multiselect("Draft your team:", df_market['name'])
    
    if selected_names:
        selected_df = df_market[df_market['name'].isin(selected_names)]
        total_cost = selected_df['price'].sum()
        remaining = 90 - total_cost
        
        c1, c2 = st.columns(2)
        c1.metric("Budget Remaining", f"£{remaining:.1f}m", delta=remaining, delta_color="normal")
        c2.metric("Squad Size", f"{len(selected_names)}/5")

        if len(selected_names) == 5 and remaining >= 0:
            if st.button("🚀 SUBMIT TEAM"):
                st.balloons()
                st.success("Team Locked In!")
        elif remaining < 0:
            st.error("Over budget! You need to release some expensive players.")

elif st.session_state.page == 'Leader':
    st.title("🏆 Global Standings")
    # Placeholder for leaderboard
    leader_df = pd.DataFrame({
        "Rank": [1, 2, 3],
        "Manager": ["Lucas Lau", "Geonhee", "Aravind"],
        "Points": [184.5, 162.1, 145.0]
    })
    st.table(leader_df)

elif st.session_state.page == 'Admin':
    st.title("🔑 Admin Panel")
    pw = st.text_input("Enter Admin Password", type="password")
    if pw == "gate2026":
        st.success("Access Granted.")
        st.write("Update scores for Maths, HASS, and English below.")
        # Score update logic would go here