# -*- coding: utf-8 -*-
"""
Pagina de menciones judiciales de legisladores.
Fuente: Archivo CIJ (Centro de Informacion Judicial) - CSJN
"""
import streamlit as st
from sqlalchemy import text
from src.components.causas import (
    get_ranking_menciones, 
    get_estadisticas_generales,
    get_menciones_legislador
)

def show(db):
    st.title("Menciones Judiciales")
    st.caption("Fuente: Archivo CIJ (Centro de Informacion Judicial) - Corte Suprema de Justicia")
    
    st.warning("""
        **Aviso importante**: Esta seccion muestra menciones de legisladores en noticias 
        del archivo judicial. Una mencion **no implica culpabilidad ni condena**. 
        Los legisladores pueden aparecer como querellantes, testigos, o en contexto informativo.
    """)
    
    stats = get_estadisticas_generales(db)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Noticias analizadas", stats['total_noticias'])
    with col2:
        st.metric("Menciones encontradas", stats['total_menciones'])
    with col3:
        st.metric("Legisladores mencionados", stats['legisladores_mencionados'])
    
    st.markdown("---")
    
    tab1, tab2 = st.tabs(["Ranking", "Buscar legislador"])
    
    with tab1:
        mostrar_ranking(db)
    
    with tab2:
        buscar_legislador(db)

def mostrar_ranking(db):
    """Muestra el ranking de legisladores con mas menciones."""
    
    col1, col2 = st.columns(2)
    with col1:
        camara = st.selectbox("Camara", ["Todas", "Diputados", "Senadores"], key="rank_camara")
    with col2:
        min_menciones = st.number_input("Minimo de menciones", min_value=1, value=1, key="rank_min")
    
    ranking = get_ranking_menciones(db, camara if camara != "Todas" else None, min_menciones)
    
    if not ranking:
        st.info("No se encontraron legisladores con los filtros seleccionados.")
        return
    
    st.subheader(f"Legisladores con menciones judiciales ({len(ranking)})")
    
    for leg in ranking:
        leg_id, nombre, bloque, camara_leg, menciones = leg
        
        with st.expander(f"**{nombre}** - {menciones} menciones"):
            st.write(f"**Bloque:** {bloque or 'Sin datos'}")
            st.write(f"**Camara:** {camara_leg}")
            
            noticias = get_menciones_legislador(db, leg_id)
            
            st.markdown("##### Noticias:")
            for noticia in noticias:
                titulo, fecha, url, palabra_clave, tipo_match = noticia
                st.markdown(f"- [{titulo[:70]}...]({url}) ({fecha})")

def buscar_legislador(db):
    """Busqueda de legislador especifico."""
    
    result = db.execute(text("""
        SELECT DISTINCT l.id, l.nombre_completo 
        FROM menciones_cij m
        JOIN legisladores l ON m.legislador_id = l.id
        ORDER BY l.nombre_completo
    """))
    legisladores = result.fetchall()
    
    if not legisladores:
        st.info("No hay legisladores con menciones registradas.")
        return
    
    opciones = {f"{l[1]}": l[0] for l in legisladores}
    
    seleccion = st.selectbox(
        "Seleccionar legislador",
        options=[""] + list(opciones.keys()),
        key="buscar_leg"
    )
    
    if seleccion and seleccion in opciones:
        leg_id = opciones[seleccion]
        
        result = db.execute(text("""
            SELECT nombre_completo, bloque, camara, distrito
            FROM legisladores WHERE id = :id
        """), {"id": leg_id})
        leg = result.fetchone()
        
        if leg:
            st.markdown(f"### {leg[0]}")
            st.write(f"**Bloque:** {leg[1] or 'Sin datos'}")
            st.write(f"**Camara:** {leg[2]}")
            if leg[3]:
                st.write(f"**Distrito:** {leg[3]}")
        
        menciones = get_menciones_legislador(db, leg_id)
        
        st.markdown(f"### Menciones ({len(menciones)})")
        
        for mencion in menciones:
            titulo, fecha, url, palabra_clave, tipo_match = mencion
            with st.expander(f"{titulo[:70]}..." if len(titulo) > 70 else titulo):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Fecha:** {fecha}")
                    st.write(f"**Palabra clave:** {palabra_clave}")
                with col2:
                    st.write(f"**Tipo match:** {tipo_match}")
                st.markdown(f"[Ver noticia completa]({url})")

def render():
    """Funcion principal llamada desde main.py"""
    from src.database import SessionLocal
    db = SessionLocal()
    try:
        show(db)
    finally:
        db.close()