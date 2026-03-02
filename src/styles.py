"""
Estilos unificados para Lobby - Plataforma de Inteligencia Pública
Diseño editorial con navegación horizontal y header fijo
"""

import streamlit as st

def apply_styles():
    """Aplica estilos CSS globales a la app"""
    st.markdown("""
    <style>
    /* ============================================
       FUENTES
       ============================================ */
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* ============================================
       LAYOUT BASE
       ============================================ */
    .stApp {
        background: #FAFAFA;
    }
    
    /* Ocultar sidebar por defecto - usamos navegación horizontal */
    section[data-testid="stSidebar"] {
        display: none;
    }
    
    .main .block-container {
        padding-top: 0 !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 1400px;
    }
    
    /* ============================================
       HEADER PRINCIPAL
       ============================================ */
    .lobby-header {
        background: #0F2240;
        margin: -1rem -2rem 0 -2rem;
        padding: 0.8rem 2rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        position: sticky;
        top: 0;
        z-index: 1000;
    }
    
    .lobby-logo {
        display: flex;
        align-items: center;
        gap: 0.6rem;
    }
    
    .lobby-logo-icon {
        width: 32px;
        height: 32px;
        background: #E8C547;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 700;
        color: #0F2240;
        font-size: 1.1rem;
    }
    
    .lobby-logo-text {
        font-family: 'DM Serif Display', serif;
        font-size: 1.5rem;
        color: white;
        letter-spacing: -0.5px;
    }
    
    .lobby-search {
        flex: 1;
        max-width: 400px;
        margin: 0 2rem;
    }
    
    .lobby-search input {
        width: 100%;
        padding: 0.5rem 1rem;
        border: none;
        border-radius: 6px;
        background: rgba(255,255,255,0.1);
        color: white;
        font-size: 0.9rem;
    }
    
    .lobby-search input::placeholder {
        color: rgba(255,255,255,0.5);
    }
    
    .lobby-meta {
        font-size: 0.75rem;
        color: rgba(255,255,255,0.6);
    }
    
    /* ============================================
       NAVEGACIÓN HORIZONTAL
       ============================================ */
    .lobby-nav {
        background: white;
        border-bottom: 1px solid #E5E7EB;
        margin: 0 -2rem;
        padding: 0 2rem;
        display: flex;
        gap: 0;
        position: sticky;
        top: 56px;
        z-index: 999;
    }
    
    .lobby-nav-item {
        padding: 1rem 1.5rem;
        font-size: 0.9rem;
        font-weight: 500;
        color: #6B7280;
        text-decoration: none;
        border-bottom: 2px solid transparent;
        transition: all 0.15s ease;
        cursor: pointer;
    }
    
    .lobby-nav-item:hover {
        color: #0F2240;
        background: #F9FAFB;
    }
    
    .lobby-nav-item.active {
        color: #0F2240;
        border-bottom-color: #E8C547;
        font-weight: 600;
    }
    
    /* ============================================
       TIPOGRAFÍA
       ============================================ */
    h1 {
        font-family: 'DM Serif Display', serif !important;
        font-size: 2.2rem !important;
        font-weight: 400 !important;
        color: #0F2240 !important;
        margin-bottom: 0.5rem !important;
        letter-spacing: -0.5px;
    }
    
    h2 {
        font-family: 'DM Sans', sans-serif !important;
        font-size: 1.4rem !important;
        font-weight: 600 !important;
        color: #1F2937 !important;
        margin-top: 1.5rem !important;
    }
    
    h3 {
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        color: #374151 !important;
    }
    
    .page-subtitle {
        font-size: 0.95rem;
        color: #6B7280;
        margin-bottom: 1.5rem;
        padding-bottom: 1rem;
        border-bottom: 1px solid #E5E7EB;
    }
    
    /* ============================================
       MÉTRICAS / CARDS
       ============================================ */
    [data-testid="stMetric"] {
        background: white;
        padding: 1.2rem;
        border-radius: 8px;
        border: 1px solid #E5E7EB;
    }
    
    [data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
        font-weight: 500 !important;
        color: #6B7280 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    [data-testid="stMetricValue"] {
        font-size: 1.8rem !important;
        font-weight: 600 !important;
        color: #0F2240 !important;
    }
    
    /* Card genérica */
    .lobby-card {
        background: white;
        border-radius: 8px;
        border: 1px solid #E5E7EB;
        padding: 1.5rem;
        margin-bottom: 1rem;
    }
    
    .lobby-card-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 1rem;
    }
    
    .lobby-card-title {
        font-weight: 600;
        color: #1F2937;
        font-size: 1rem;
    }
    
    .lobby-card-meta {
        font-size: 0.8rem;
        color: #9CA3AF;
    }
    
    /* ============================================
       TABLAS / DATAFRAMES
       ============================================ */
    .stDataFrame {
        border: 1px solid #E5E7EB !important;
        border-radius: 8px !important;
        overflow: hidden;
    }
    
    .stDataFrame thead tr th {
        background: #F9FAFB !important;
        font-weight: 600 !important;
        font-size: 0.8rem !important;
        color: #374151 !important;
        text-transform: uppercase;
        letter-spacing: 0.3px;
        padding: 0.8rem 1rem !important;
    }
    
    .stDataFrame tbody tr td {
        font-size: 0.9rem !important;
        padding: 0.7rem 1rem !important;
        border-bottom: 1px solid #F3F4F6 !important;
    }
    
    .stDataFrame tbody tr:hover {
        background: #F9FAFB !important;
    }
    
    /* ============================================
       EXPANDERS
       ============================================ */
    .streamlit-expanderHeader {
        background: white !important;
        border: 1px solid #E5E7EB !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        color: #1F2937 !important;
        padding: 0.8rem 1rem !important;
    }
    
    .streamlit-expanderHeader:hover {
        background: #F9FAFB !important;
        border-color: #D1D5DB !important;
    }
    
    .streamlit-expanderContent {
        border: 1px solid #E5E7EB !important;
        border-top: none !important;
        border-radius: 0 0 8px 8px !important;
        background: white !important;
        padding: 1rem !important;
    }
    
    /* ============================================
       TABS
       ============================================ */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: transparent;
        border-bottom: 1px solid #E5E7EB;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 0.8rem 1.5rem;
        font-weight: 500;
        color: #6B7280;
        border-bottom: 2px solid transparent;
        background: transparent;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        color: #1F2937;
    }
    
    .stTabs [aria-selected="true"] {
        color: #0F2240 !important;
        border-bottom-color: #E8C547 !important;
        background: transparent !important;
    }
    
    .stTabs [data-baseweb="tab-panel"] {
        padding-top: 1.5rem;
    }
    
    /* ============================================
       INPUTS
       ============================================ */
    .stTextInput input {
        border: 1px solid #D1D5DB !important;
        border-radius: 6px !important;
        padding: 0.6rem 0.8rem !important;
        font-size: 0.9rem !important;
    }
    
    .stTextInput input:focus {
        border-color: #0F2240 !important;
        box-shadow: 0 0 0 2px rgba(15,34,64,0.1) !important;
    }
    
    .stSelectbox > div > div {
        border: 1px solid #D1D5DB !important;
        border-radius: 6px !important;
    }
    
    /* ============================================
       BOTONES
       ============================================ */
    .stButton > button {
        background: #0F2240 !important;
        color: white !important;
        border: none !important;
        border-radius: 6px !important;
        padding: 0.5rem 1rem !important;
        font-weight: 500 !important;
        transition: all 0.15s ease !important;
    }
    
    .stButton > button:hover {
        background: #1a3a5c !important;
        transform: translateY(-1px);
    }
    
    /* Botón secundario */
    .stButton > button[kind="secondary"] {
        background: white !important;
        color: #374151 !important;
        border: 1px solid #D1D5DB !important;
    }
    
    /* ============================================
       BADGES / TAGS
       ============================================ */
    .lobby-badge {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 500;
    }
    
    .lobby-badge-blue {
        background: #DBEAFE;
        color: #1E40AF;
    }
    
    .lobby-badge-green {
        background: #D1FAE5;
        color: #065F46;
    }
    
    .lobby-badge-red {
        background: #FEE2E2;
        color: #991B1B;
    }
    
    .lobby-badge-yellow {
        background: #FEF3C7;
        color: #92400E;
    }
    
    .lobby-badge-gray {
        background: #F3F4F6;
        color: #4B5563;
    }
    
    /* ============================================
       VOTOS INDICADORES
       ============================================ */
    .voto-afirmativo {
        color: #059669;
        font-weight: 600;
    }
    
    .voto-negativo {
        color: #DC2626;
        font-weight: 600;
    }
    
    .voto-abstencion {
        color: #D97706;
        font-weight: 600;
    }
    
    /* ============================================
       RANKING ITEM
       ============================================ */
    .ranking-item {
        background: white;
        border-left: 4px solid #E8C547;
        padding: 0.8rem 1rem;
        margin-bottom: 0.5rem;
        border-radius: 0 8px 8px 0;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    
    .ranking-position {
        font-size: 1.2rem;
        font-weight: 700;
        color: #9CA3AF;
        min-width: 2rem;
    }
    
    .ranking-content {
        flex: 1;
    }
    
    .ranking-name {
        font-weight: 600;
        color: #1F2937;
    }
    
    .ranking-meta {
        font-size: 0.8rem;
        color: #6B7280;
    }
    
    .ranking-value {
        font-weight: 700;
        font-size: 1.1rem;
    }
    
    /* ============================================
       ACTIVITY FEED
       ============================================ */
    .activity-item {
        display: flex;
        gap: 1rem;
        padding: 1rem 0;
        border-bottom: 1px solid #F3F4F6;
    }
    
    .activity-icon {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }
    
    .activity-icon-vote {
        background: #DBEAFE;
        color: #1E40AF;
    }
    
    .activity-icon-session {
        background: #D1FAE5;
        color: #065F46;
    }
    
    .activity-content {
        flex: 1;
    }
    
    .activity-title {
        font-weight: 500;
        color: #1F2937;
        margin-bottom: 0.2rem;
    }
    
    .activity-meta {
        font-size: 0.8rem;
        color: #9CA3AF;
    }
    
    /* ============================================
       FILTROS BAR
       ============================================ */
    .filters-bar {
        background: white;
        border: 1px solid #E5E7EB;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1.5rem;
        display: flex;
        gap: 1rem;
        flex-wrap: wrap;
        align-items: flex-end;
    }
    
    /* ============================================
       RESPONSIVE
       ============================================ */
    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        
        .lobby-header {
            flex-wrap: wrap;
            gap: 0.5rem;
        }
        
        .lobby-search {
            order: 3;
            max-width: 100%;
            margin: 0.5rem 0 0 0;
        }
        
        .lobby-nav {
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }
        
        .lobby-nav-item {
            white-space: nowrap;
            padding: 0.8rem 1rem;
        }
    }
    
    /* ============================================
       OCULTAR ELEMENTOS DEFAULT STREAMLIT
       ============================================ */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] {display: none;}
    
    /* Ocultar el ícono de deploy */
    .stDeployButton {display: none;}
    
    </style>
    """, unsafe_allow_html=True)


def show_header(current_page="inicio"):
    """Muestra el header con logo y navegación"""
    
    # Header principal
    st.markdown("""
    <div class="lobby-header">
        <div class="lobby-logo">
            <div class="lobby-logo-icon">L</div>
            <span class="lobby-logo-text">Lobby</span>
        </div>
        <div class="lobby-meta">
            Plataforma de Inteligencia Pública · Argentina
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Navegación
    nav_items = [
        ("inicio", "Inicio", "Inicio"),
        ("legisladores", "Legisladores", "Legisladores"),
        ("actividad", "Actividad", "Actividad"),
        ("patrimonio", "Patrimonio", "Patrimonio"),
        ("estadisticas", "Estadísticas", "Estadísticas"),
    ]
    
    nav_html = '<div class="lobby-nav">'
    for key, label, _ in nav_items:
        active = "active" if key == current_page else ""
        nav_html += f'<span class="lobby-nav-item {active}">{label}</span>'
    nav_html += '</div>'
    
    st.markdown(nav_html, unsafe_allow_html=True)


def show_logo():
    """Versión legacy - mantiene compatibilidad"""
    pass


def fmt_pesos(val):
    """Formatea un valor en pesos argentinos"""
    if not val or val == 0:
        return "—"
    millones = val / 1_000_000
    if millones >= 1000:
        return f"${millones/1000:,.1f}B"
    return f"${millones:,.1f}M"


def fmt_usd(val):
    """Formatea un valor en dólares"""
    if not val or val == 0:
        return "—"
    miles = val / 1_000
    if miles >= 1000:
        return f"USD {miles/1000:,.1f}M"
    return f"USD {miles:,.0f}K"
