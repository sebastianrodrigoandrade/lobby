# -*- coding: utf-8 -*-
"""
Lobby - Página de Comisiones
Integrantes y estructura del Congreso
"""
import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal

# ============================================
# FUNCIONES DE CARGA
# ============================================

@st.cache_data(ttl=3600)
def cargar_comisiones():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT c.id, c.nombre, c.slug,
                   COUNT(ci.id) as total_integrantes
            FROM comisiones c
            LEFT JOIN comision_integrantes ci ON ci.comision_id = c.id
            GROUP BY c.id, c.nombre, c.slug
            ORDER BY c.nombre
        """))
        return pd.DataFrame(result.fetchall(), columns=['id', 'nombre', 'slug', 'total_integrantes'])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_integrantes_comision(comision_id):
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                ci.nombre_raw,
                ci.cargo,
                ci.bloque,
                l.id as legislador_id,
                l.nombre_completo,
                l.foto_url,
                l.distrito
            FROM comision_integrantes ci
            LEFT JOIN legisladores l ON ci.legislador_id = l.id
            WHERE ci.comision_id = :com_id
            ORDER BY 
                CASE ci.cargo 
                    WHEN 'PRESIDENTE' THEN 1 
                    WHEN 'VICEPRESIDENTE 1ª' THEN 2
                    WHEN 'VICEPRESIDENTE 2ª' THEN 3
                    WHEN 'SECRETARIO' THEN 4
                    ELSE 5 
                END,
                ci.nombre_raw
        """), {"com_id": comision_id})
        return pd.DataFrame(result.fetchall(), columns=[
            'nombre_raw', 'cargo', 'bloque', 'legislador_id', 'nombre_completo', 'foto_url', 'distrito'
        ])
    finally:
        db.close()

# ============================================
# COLORES POR BLOQUE
# ============================================

COLORES_BLOQUE = {
    'LA LIBERTAD AVANZA': '#7C3AED',
    'PRO': '#FBBF24', 
    'UNIÓN POR LA PATRIA': '#2563EB',
    'UNION POR LA PATRIA': '#2563EB',
    'UCR': '#DC2626',
    'HACEMOS COALICION FEDERAL': '#F97316',
}

def get_color_bloque(bloque):
    if not bloque:
        return '#6B7280'
    bloque_upper = bloque.upper()
    for key, color in COLORES_BLOQUE.items():
        if key in bloque_upper:
            return color
    return '#6B7280'

# ============================================
# RENDER
# ============================================

def render():
    st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
    st.title("Comisiones")
    st.markdown("<div class='page-subtitle'>Integrantes de las 46 comisiones permanentes de la Camara de Diputados</div>", unsafe_allow_html=True)
    
    # Cargar datos
    df_comisiones = cargar_comisiones()
    
    # Búsqueda
    busqueda = st.text_input(
        "Buscar comision",
        placeholder="Ej: Presupuesto, Justicia, Educacion...",
        key="busq_comision"
    )
    
    if busqueda:
        df_filtrado = df_comisiones[df_comisiones['nombre'].str.contains(busqueda, case=False, na=False)]
    else:
        df_filtrado = df_comisiones
    
    # Métricas
    col1, col2, col3 = st.columns(3)
    col1.metric("Comisiones", len(df_filtrado))
    col2.metric("Total integrantes", f"{df_filtrado['total_integrantes'].sum():,}")
    col3.metric("Promedio por comision", f"{df_filtrado['total_integrantes'].mean():.0f}")
    
    st.markdown("---")
    
    # Selector de comisión
    opciones = df_filtrado['nombre'].tolist()
    
    if not opciones:
        st.warning("No se encontraron comisiones con ese criterio.")
        return
    
    comision_sel = st.selectbox(
        "Seleccionar comision",
        opciones,
        key="com_sel"
    )
    
    if not comision_sel:
        return
    
    # Obtener ID y slug
    row_com = df_filtrado[df_filtrado['nombre'] == comision_sel].iloc[0]
    comision_id = int(row_com['id'])
    comision_slug = row_com['slug']
    
    # Cargar integrantes
    df_integrantes = cargar_integrantes_comision(comision_id)
    
    if df_integrantes.empty:
        st.info("Esta comision no tiene integrantes cargados.")
        return
    
    # Header de la comisión
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #1E3A5F 0%, #0F2240 100%); 
                padding: 1.5rem; border-radius: 12px; margin: 1rem 0; color: white;">
        <h2 style="margin: 0 0 0.5rem 0; color: white;">{comision_sel}</h2>
        <div style="display: flex; gap: 2rem; flex-wrap: wrap; opacity: 0.9;">
            <div><strong>{len(df_integrantes)}</strong> integrantes</div>
            <div><a href="https://www.hcdn.gob.ar/comisiones/permanentes/{comision_slug}/" 
                    target="_blank" style="color: #93C5FD;">Ver en HCDN</a></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Autoridades (Presidente, Vice, Secretario)
    autoridades = df_integrantes[df_integrantes['cargo'] != 'VOCAL']
    vocales = df_integrantes[df_integrantes['cargo'] == 'VOCAL']
    
    if not autoridades.empty:
        st.markdown("### Autoridades")
        
        cols = st.columns(min(len(autoridades), 4))
        for i, (_, row) in enumerate(autoridades.iterrows()):
            with cols[i % 4]:
                color = get_color_bloque(row['bloque'])
                foto = row['foto_url'] if pd.notna(row['foto_url']) else None
                nombre = row['nombre_completo'] or row['nombre_raw']
                
                if foto:
                    foto_html = f'<img src="{foto}" style="width: 70px; height: 70px; border-radius: 50%; object-fit: cover; margin-bottom: 0.5rem; border: 3px solid {color};">'
                else:
                    foto_html = f'<div style="width: 70px; height: 70px; border-radius: 50%; background: {color}20; display: flex; align-items: center; justify-content: center; color: {color}; font-weight: 700; font-size: 1.5rem; margin: 0 auto 0.5rem auto; border: 3px solid {color};">{nombre[0] if nombre else "?"}</div>'
                
                st.markdown(f"""
                <div style="background: white; border: 1px solid #E5E7EB; border-radius: 12px; padding: 1rem; text-align: center; margin-bottom: 0.5rem;">
                    {foto_html}
                    <div style="font-weight: 600; font-size: 0.95rem;">{nombre}</div>
                    <div style="color: {color}; font-size: 0.8rem; font-weight: 600;">{row['cargo']}</div>
                    <div style="color: #6B7280; font-size: 0.75rem;">{row['bloque'] or ''}</div>
                </div>
                """, unsafe_allow_html=True)
    
    # Vocales por bloque
    if not vocales.empty:
        st.markdown("### Vocales")
        
        # Contar por bloque
        bloques_count = vocales['bloque'].fillna('Sin bloque').value_counts()
        bloques = bloques_count.index.tolist()
        
        tabs = st.tabs([f"{b} ({bloques_count[b]})" for b in bloques])
        
        for tab, bloque in zip(tabs, bloques):
            with tab:
                if bloque == 'Sin bloque':
                    vocales_bloque = vocales[vocales['bloque'].isna()]
                else:
                    vocales_bloque = vocales[vocales['bloque'] == bloque]
                
                color = get_color_bloque(bloque)
                
                # Lista de vocales
                for _, row in vocales_bloque.iterrows():
                    foto = row['foto_url'] if pd.notna(row['foto_url']) else None
                    nombre = row['nombre_completo'] or row['nombre_raw']
                    
                    if foto:
                        foto_html = f'<img src="{foto}" style="width: 40px; height: 40px; border-radius: 50%; object-fit: cover;">'
                    else:
                        foto_html = f'<div style="width: 40px; height: 40px; border-radius: 50%; background: {color}15; display: flex; align-items: center; justify-content: center; color: {color}; font-weight: 600;">{nombre[0] if nombre else "?"}</div>'
                    
                    st.markdown(f"""
                    <div style="display: flex; align-items: center; gap: 0.8rem; padding: 0.6rem 0; border-bottom: 1px solid #F3F4F6;">
                        {foto_html}
                        <span style="font-size: 0.95rem;">{nombre}</span>
                    </div>
                    """, unsafe_allow_html=True)
    
    # Composición por bloque
    st.markdown("---")
    st.markdown("### Composicion por bloque")
    
    comp = df_integrantes['bloque'].fillna('Sin bloque').value_counts().reset_index()
    comp.columns = ['Bloque', 'Integrantes']
    
    for _, row in comp.iterrows():
        bloque = row['Bloque']
        cant = row['Integrantes']
        pct = cant / len(df_integrantes) * 100
        color = get_color_bloque(bloque)
        
        st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 1rem; padding: 0.5rem 0;">
            <div style="width: 200px; font-size: 0.9rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{bloque}</div>
            <div style="flex: 1; background: #F3F4F6; border-radius: 4px; height: 24px; overflow: hidden;">
                <div style="width: {pct}%; background: {color}; height: 100%;"></div>
            </div>
            <div style="width: 40px; text-align: right; font-weight: 600;">{cant}</div>
        </div>
        """, unsafe_allow_html=True)
