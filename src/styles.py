# src/styles.py

STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Playfair+Display:wght@700&display=swap');

/* ── BASE ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background-color: #F7F7F5;
    color: #1a1a1a;
}

/* ── SIDEBAR ── */
[data-testid="stSidebarContent"] {
    padding-top: 0 !important;
}
[data-testid="stSidebarNav"] {
    padding-top: 0 !important;
}
[data-testid="stSidebar"] {
    background-color: #0F2240;
    color: white;
}
[data-testid="stSidebar"] * {
    color: white !important;
}
[data-testid="stSidebar"] .stRadio label {
    color: white !important;
    font-size: 0.95rem;
}
[data-testid="stSidebar"] h1 {
    font-family: 'Playfair Display', serif;
    font-size: 1.3rem;
    color: white !important;
    border-bottom: 1px solid rgba(255,255,255,0.2);
    padding-bottom: 0.5rem;
    margin-bottom: 0.3rem;
}
[data-testid="stSidebar"] .stSelectbox label {
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: rgba(255,255,255,0.6) !important;
}

/* ── TÍTULOS ── */
h1 {
    font-family: 'Playfair Display', serif !important;
    font-size: 2.2rem !important;
    font-weight: 700 !important;
    color: #0F2240 !important;
    border-bottom: 3px solid #0F2240;
    padding-bottom: 0.4rem;
    margin-bottom: 0.2rem;
}
h2 {
    font-family: 'Inter', sans-serif !important;
    font-size: 1.2rem !important;
    font-weight: 600 !important;
    color: #0F2240 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 1.5rem !important;
}
h3 {
    font-family: 'Inter', sans-serif !important;
    font-size: 1rem !important;
    font-weight: 500 !important;
    color: #444 !important;
}

/* ── MÉTRICAS ── */
[data-testid="metric-container"] {
    background-color: white;
    border: 1px solid #e0e0e0;
    border-left: 4px solid #0F2240;
    border-radius: 4px;
    padding: 1rem 1.2rem !important;
}
[data-testid="metric-container"] label {
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: #666 !important;
    font-weight: 500 !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 2rem !important;
    font-weight: 700 !important;
    color: #0F2240 !important;
}

/* ── DATAFRAME ── */
[data-testid="stDataFrame"] {
    border: 1px solid #e0e0e0 !important;
    border-radius: 4px !important;
}

/* ── INPUTS ── */
[data-testid="stTextInput"] input {
    background-color: white !important;
    border: 1px solid #ccc !important;
    border-radius: 4px !important;
    font-size: 0.95rem !important;
    color: #1a1a1a !important;
}
[data-testid="stSelectbox"] > div {
    background-color: white !important;
    border-radius: 4px !important;
}

/* ── TABS ── */
[data-testid="stTabs"] button {
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: #666 !important;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #0F2240 !important;
    border-bottom: 2px solid #0F2240 !important;
}

/* ── EXPANDERS ── */
[data-testid="stExpander"] {
    border: 1px solid #e0e0e0 !important;
    border-radius: 4px !important;
    background-color: white !important;
}

/* ── DIVIDER ── */
hr {
    border-color: #e0e0e0 !important;
    margin: 1.5rem 0 !important;
}

/* ── BADGES DE VOTO ── */
.voto-afirmativo { color: #1a7a4a; font-weight: 600; }
.voto-negativo   { color: #c0392b; font-weight: 600; }
.voto-abstencion { color: #e67e22; font-weight: 600; }
.voto-ausente    { color: #999;    font-weight: 600; }

/* ── SUBTÍTULO DE PÁGINA ── */
.page-subtitle {
    font-size: 0.9rem;
    color: #666;
    margin-top: -0.8rem;
    margin-bottom: 1.5rem;
    border-bottom: 1px solid #e0e0e0;
    padding-bottom: 1rem;
}
</style>
"""

def show_logo():
    import streamlit as st
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logo_path = os.path.join(base, 'img', 'logo_lobby.png')
    if os.path.exists(logo_path):
        st.sidebar.image(logo_path, use_container_width=True)
    else:
        st.sidebar.markdown("**LOBBY**")
        
def apply_styles():
    import streamlit as st
    st.markdown(STYLES, unsafe_allow_html=True)
    
