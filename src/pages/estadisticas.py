# -*- coding: utf-8 -*-
"""
Lobby - Pagina de Estadisticas
Incluye: Leyes por año, DNUs, metricas generales
"""
import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal

# ============================================
# FUNCIONES DE CARGA
# ============================================

@st.cache_data(ttl=3600)
def cargar_leyes_por_año():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                EXTRACT(YEAR FROM fecha_ingreso)::int as año,
                estado,
                COUNT(*) as total
            FROM proyectos
            WHERE fecha_ingreso IS NOT NULL
              AND estado IN ('LEY', 'RESOLUCION', 'DECLARACION', 'MENSAJE')
            GROUP BY año, estado
            ORDER BY año DESC, total DESC
        """))
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    finally:
        db.close()
    return df


@st.cache_data(ttl=3600)
def cargar_dnus():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                EXTRACT(YEAR FROM fecha_ingreso)::int as año,
                COUNT(*) as total
            FROM proyectos
            WHERE nro_expediente ILIKE '%-JGM-%'
              AND titulo ILIKE '%DECRETO DE NECESIDAD Y URGENCIA%'
            GROUP BY año
            ORDER BY año DESC
        """))
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    finally:
        db.close()
    return df


@st.cache_data(ttl=3600)
def cargar_dnus_detalle():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                nro_expediente,
                titulo,
                fecha_ingreso,
                estado
            FROM proyectos
            WHERE nro_expediente ILIKE '%-JGM-%'
              AND titulo ILIKE '%DECRETO DE NECESIDAD Y URGENCIA%'
            ORDER BY fecha_ingreso DESC
        """))
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    finally:
        db.close()
    return df


@st.cache_data(ttl=3600)
def cargar_metricas_db():
    db = SessionLocal()
    try:
        votos = db.execute(text("SELECT COUNT(*) FROM votos")).scalar() or 0
        legisladores = db.execute(text("SELECT COUNT(*) FROM legisladores")).scalar() or 0
        proyectos = db.execute(text("SELECT COUNT(*) FROM proyectos")).scalar() or 0
        sesiones = db.execute(text("SELECT COUNT(*) FROM sesiones")).scalar() or 0
        comisiones = db.execute(text("SELECT COUNT(*) FROM comisiones")).scalar() or 0
        ddjj = db.execute(text("SELECT COUNT(*) FROM ddjj_legisladores")).scalar() or 0
    finally:
        db.close()
    return {
        'votos': votos,
        'legisladores': legisladores,
        'proyectos': proyectos,
        'sesiones': sesiones,
        'comisiones': comisiones,
        'ddjj': ddjj
    }


@st.cache_data(ttl=3600)
def cargar_votos_por_camara():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                COALESCE(a.camara, 'Diputados') as camara,
                COUNT(v.id) as votos
            FROM votos v
            LEFT JOIN actas_cabecera a ON a.acta_id = v.acta_id
            GROUP BY camara
        """))
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    finally:
        db.close()
    return df


@st.cache_data(ttl=3600)
def cargar_proyectos_por_tipo():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                COALESCE(estado, 'SIN ESTADO') as tipo,
                COUNT(*) as total
            FROM proyectos
            WHERE fecha_ingreso >= '2020-01-01'
            GROUP BY estado
            ORDER BY total DESC
            LIMIT 10
        """))
        df = pd.DataFrame(result.fetchall(), columns=result.keys())
    finally:
        db.close()
    return df


# ============================================
# FUNCION RENDER
# ============================================

def render():
    """Renderiza la pagina de estadisticas."""
    
    st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
    st.title("Estadisticas")
    st.markdown("<div class='page-subtitle'>Metricas y datos agregados del Congreso de la Nacion</div>", unsafe_allow_html=True)

    # METRICAS GENERALES
    try:
        metricas = cargar_metricas_db()
        
        st.markdown("### Base de datos")
        
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("Votos", f"{metricas['votos']:,}")
        col2.metric("Legisladores", f"{metricas['legisladores']:,}")
        col3.metric("Proyectos", f"{metricas['proyectos']:,}")
        col4.metric("Sesiones", f"{metricas['sesiones']:,}")
        col5.metric("Comisiones", f"{metricas['comisiones']:,}")
        col6.metric("DDJJ", f"{metricas['ddjj']:,}")
    except Exception as e:
        st.error(f"Error al cargar metricas: {e}")
        return

    st.markdown("---")

    # TABS PRINCIPALES
    tabs = st.tabs(["Leyes y Proyectos", "DNUs", "Distribuciones"])

    # --- TAB LEYES ---
    with tabs[0]:
        df_leyes = cargar_leyes_por_año()

        if df_leyes.empty:
            st.info("Sin datos de leyes.")
        else:
            total_leyes = int(df_leyes[df_leyes['estado'] == 'LEY']['total'].sum())
            total_res = int(df_leyes[df_leyes['estado'] == 'RESOLUCION']['total'].sum())
            total_decl = int(df_leyes[df_leyes['estado'] == 'DECLARACION']['total'].sum())

            col1, col2, col3 = st.columns(3)
            col1.metric("Total leyes (historico)", f"{total_leyes:,}")
            col2.metric("Resoluciones", f"{total_res:,}")
            col3.metric("Declaraciones", f"{total_decl:,}")

            st.markdown("---")

            st.markdown("### Leyes sancionadas por año")
            
            df_pivot = df_leyes.pivot_table(
                index='año', columns='estado', values='total', fill_value=0
            ).reset_index()
            df_pivot = df_pivot[df_pivot['año'] >= 2008].sort_values('año')

            if 'LEY' in df_pivot.columns:
                st.bar_chart(df_pivot.set_index('año')[['LEY']])

            st.markdown("---")

            st.markdown("### Actividad legislativa por año")
            df_tabla = df_leyes[df_leyes['año'] >= 2008].pivot_table(
                index='año', columns='estado', values='total', fill_value=0
            ).reset_index().sort_values('año', ascending=False)
            
            st.dataframe(df_tabla, use_container_width=True, hide_index=True)

    # --- TAB DNUs ---
    with tabs[1]:
        df_dnus = cargar_dnus()
        df_dnus_det = cargar_dnus_detalle()

        if df_dnus.empty:
            st.info("Sin datos de DNUs.")
        else:
            total_dnus = int(df_dnus['total'].sum())
            año_max = int(df_dnus['año'].max())
            dnus_max = int(df_dnus.loc[df_dnus['total'].idxmax(), 'total'])
            año_mas_dnus = int(df_dnus.loc[df_dnus['total'].idxmax(), 'año'])

            col1, col2, col3 = st.columns(3)
            col1.metric("Total DNUs registrados", total_dnus)
            col2.metric("Ultimo año con datos", año_max)
            col3.metric("Año con mas DNUs", f"{año_mas_dnus} ({dnus_max})")

            st.caption("Datos disponibles: 2008-2023. Los DNUs del periodo 2024-2025 no estan publicados en el portal de datos abiertos.")

            st.markdown("---")

            st.markdown("### DNUs por año")
            st.bar_chart(df_dnus.set_index('año')[['total']].sort_index())

            st.markdown("---")

            st.markdown("### Listado de DNUs")
            
            busqueda_dnu = st.text_input("Buscar DNU", placeholder="Ej: jubilaciones, emergencia, exportaciones...")
            
            df_mostrar = df_dnus_det.copy()
            if busqueda_dnu:
                df_mostrar = df_mostrar[df_mostrar['titulo'].str.contains(busqueda_dnu, case=False, na=False)]

            st.markdown(f"**{len(df_mostrar)} DNUs encontrados**")
            
            st.dataframe(
                df_mostrar[['fecha_ingreso', 'nro_expediente', 'titulo']].rename(columns={
                    'fecha_ingreso': 'Fecha',
                    'nro_expediente': 'Expediente',
                    'titulo': 'Descripcion',
                }),
                use_container_width=True,
                hide_index=True
            )

    # --- TAB DISTRIBUCIONES ---
    with tabs[2]:
        col_d1, col_d2 = st.columns(2)
        
        with col_d1:
            st.markdown("### Votos por camara")
            df_votos_cam = cargar_votos_por_camara()
            
            if not df_votos_cam.empty:
                for _, r in df_votos_cam.iterrows():
                    camara = r['camara']
                    votos = int(r['votos'])
                    pct = votos / df_votos_cam['votos'].sum() * 100
                    
                    st.markdown(f"""
                    <div style="background: white; border: 1px solid #E5E7EB; border-radius: 8px; padding: 1rem; margin-bottom: 0.5rem;">
                        <div style="font-weight: 600; color: #1F2937;">{camara}</div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: #0F2240;">{votos:,}</div>
                        <div style="font-size: 0.8rem; color: #6B7280;">{pct:.1f}% del total</div>
                    </div>
                    """, unsafe_allow_html=True)
        
        with col_d2:
            st.markdown("### Proyectos por tipo (2020+)")
            df_tipos = cargar_proyectos_por_tipo()
            
            if not df_tipos.empty:
                st.bar_chart(df_tipos.set_index('tipo')['total'])
        
        st.markdown("---")
        
        st.markdown("### Fuentes de datos")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **Portal de Datos Abiertos HCDN**  
            Votaciones nominales, proyectos, sesiones  
            [datos.hcdn.gob.ar](https://datos.hcdn.gob.ar/)
            
            **Senado de la Nacion**  
            Votaciones nominales del Senado  
            [senado.gob.ar/votaciones](https://www.senado.gob.ar/votaciones)
            """)
        
        with col2:
            st.markdown("""
            **Oficina Anticorrupcion**  
            Declaraciones juradas de funcionarios  
            [datos.jus.gob.ar](https://datos.jus.gob.ar/dataset/declaraciones-juradas-patrimoniales-integrales)
            
            **Series de Tiempo Argentina**  
            IPC, RIPTE, tipo de cambio  
            [apis.datos.gob.ar/series](https://apis.datos.gob.ar/series/)
            """)