"""
Lobby - Plataforma de Inteligencia Pública
Herramienta para periodistas
"""
import streamlit as st

st.set_page_config(
    page_title="Lobby · Inteligencia Pública",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

from streamlit_option_menu import option_menu
from src.styles import apply_styles
from src.pages import home, legisladores, actividad, patrimonio, alertas, estadisticas, comisiones, audiencias

# Aplicar estilos
apply_styles()

# Header
st.markdown("""
<div style="background: #0F2240; margin: -6rem -4rem 1rem -4rem; padding: 1rem 2rem; display: flex; align-items: center; justify-content: space-between;">
    <div style="display: flex; align-items: center; gap: 0.6rem;">
        <div style="width: 36px; height: 36px; background: #E8C547; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-weight: 700; color: #0F2240; font-size: 1.2rem;">L</div>
        <span style="font-family: Georgia, serif; font-size: 1.6rem; color: white;">Lobby</span>
    </div>
    <div style="font-size: 0.8rem; color: rgba(255,255,255,0.6);">
        Inteligencia Pública para Periodistas · Argentina
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================
# NAVEGACIÓN
# ============================================

menu_options = ["Inicio", "Legisladores", "Votaciones", "Comisiones", "Audiencias", "Patrimonio", "Alertas", "Datos"]

if 'current_page' not in st.session_state:
    st.session_state['current_page'] = "Inicio"

if 'menu_selection' in st.session_state:
    st.session_state['current_page'] = st.session_state['menu_selection']
    del st.session_state['menu_selection']

try:
    default_index = menu_options.index(st.session_state['current_page'])
except ValueError:
    default_index = 0

selected = option_menu(
    menu_title=None,
    options=menu_options,
    icons=["house", "person-badge", "check2-square", "people", "calendar-event", "cash-stack", "exclamation-triangle", "download"],
    default_index=default_index,
    orientation="horizontal",
    key="main_menu"
)

st.session_state['current_page'] = selected

st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)

# ============================================
# RENDERIZAR PÁGINA
# ============================================

if selected == "Inicio":
    home.render()
elif selected == "Legisladores":
    legisladores.render()
elif selected == "Votaciones":
    actividad.render()
elif selected == "Comisiones":
    comisiones.render()
elif selected == "Audiencias":
    audiencias.render()
elif selected == "Patrimonio":
    patrimonio.render()
elif selected == "Alertas":
    alertas.render()
elif selected == "Datos":
    estadisticas.render()