"""
Lobby - Plataforma de Inteligencia Pública
Archivo principal con navegación horizontal
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
from src.pages import home, legisladores, actividad, patrimonio, estadisticas

# Aplicar estilos
apply_styles()

# Header manual
st.markdown("""
<div style="background: #0F2240; margin: -6rem -4rem 1rem -4rem; padding: 1rem 2rem; display: flex; align-items: center; justify-content: space-between;">
    <div style="display: flex; align-items: center; gap: 0.6rem;">
        <div style="width: 36px; height: 36px; background: #E8C547; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-weight: 700; color: #0F2240; font-size: 1.2rem;">L</div>
        <span style="font-family: Georgia, serif; font-size: 1.6rem; color: white;">Lobby</span>
    </div>
    <div style="font-size: 0.8rem; color: rgba(255,255,255,0.6);">
        Plataforma de Inteligencia Pública · Argentina
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================
# NAVEGACIÓN HORIZONTAL
# ============================================

menu_options = ["Inicio", "Legisladores", "Actividad", "Patrimonio", "Estadisticas"]

# Inicializar el estado del menú si no existe
if 'current_page' not in st.session_state:
    st.session_state['current_page'] = "Inicio"

# Si viene una redirección desde otra página
if 'menu_selection' in st.session_state:
    st.session_state['current_page'] = st.session_state['menu_selection']
    del st.session_state['menu_selection']

# Calcular el índice default basado en la página actual
try:
    default_index = menu_options.index(st.session_state['current_page'])
except ValueError:
    default_index = 0

selected = option_menu(
    menu_title=None,
    options=menu_options,
    icons=["house", "people", "clipboard-check", "cash-stack", "bar-chart"],
    default_index=default_index,
    orientation="horizontal",
    key="main_menu"
)

# Guardar la selección actual
st.session_state['current_page'] = selected

# Espaciado
st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)

# ============================================
# RENDERIZAR PÁGINA SELECCIONADA
# ============================================

if selected == "Inicio":
    home.render()
elif selected == "Legisladores":
    legisladores.render()
elif selected == "Actividad":
    actividad.render()
elif selected == "Patrimonio":
    patrimonio.render()
elif selected == "Estadisticas":
    estadisticas.render()