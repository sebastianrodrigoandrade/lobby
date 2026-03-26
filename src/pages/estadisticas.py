# -*- coding: utf-8 -*-
"""
Lobby - Página de Datos
Exportación de datasets, metodología y contacto
"""
import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal

# ============================================
# FUNCIONES DE CARGA PARA EXPORTAR
# ============================================

@st.cache_data(ttl=3600)
def exportar_legisladores():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                nombre_completo, camara, bloque, distrito, mandato_hasta
            FROM legisladores
            WHERE mandato_hasta >= CURRENT_DATE
            ORDER BY camara, nombre_completo
        """))
        return pd.DataFrame(result.fetchall(), columns=['Nombre', 'Camara', 'Bloque', 'Distrito', 'Mandato hasta'])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def exportar_patrimonio():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                d.funcionario_apellido_nombre as nombre,
                d.anio,
                CASE WHEN d.organismo ILIKE '%SENADO%' THEN 'Senadores' ELSE 'Diputados' END as camara,
                d.patrimonio_neto,
                d.total_bienes,
                d.total_deudas
            FROM ddjj_legisladores d
            WHERE d.patrimonio_neto > 0
            ORDER BY d.anio DESC, d.patrimonio_neto DESC
        """))
        return pd.DataFrame(result.fetchall(), columns=['Nombre', 'Anio', 'Camara', 'Patrimonio Neto', 'Total Bienes', 'Total Deudas'])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def exportar_votaciones():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                acta_id,
                fecha,
                asunto,
                resultado,
                afirmativos,
                negativos,
                abstenciones,
                ausentes
            FROM votaciones_hcdn
            WHERE asunto IS NOT NULL AND asunto != ''
            ORDER BY fecha DESC
            LIMIT 1000
        """))
        return pd.DataFrame(result.fetchall(), columns=['Acta ID', 'Fecha', 'Asunto', 'Resultado', 'Afirmativos', 'Negativos', 'Abstenciones', 'Ausentes'])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_resumen_datos():
    db = SessionLocal()
    try:
        stats = {}
        
        result = db.execute(text("SELECT COUNT(*) FROM legisladores WHERE mandato_hasta >= CURRENT_DATE"))
        stats['legisladores_vigentes'] = result.scalar()
        
        result = db.execute(text("SELECT COUNT(*) FROM ddjj_legisladores WHERE patrimonio_neto > 0"))
        stats['ddjj_total'] = result.scalar()
        
        result = db.execute(text("SELECT COUNT(DISTINCT anio) FROM ddjj_legisladores WHERE patrimonio_neto > 0"))
        stats['ddjj_anios'] = result.scalar()
        
        result = db.execute(text("SELECT COUNT(*) FROM votaciones_hcdn"))
        stats['votaciones'] = result.scalar()
        
        result = db.execute(text("SELECT COUNT(*) FROM votos_hcdn"))
        stats['votos'] = result.scalar()
        
        result = db.execute(text("SELECT COUNT(*) FROM audiencias_ejecutivo"))
        stats['audiencias'] = result.scalar()
        
        return stats
    finally:
        db.close()

# ============================================
# RENDER
# ============================================

def render():
    st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
    st.title("Datos Abiertos")
    st.markdown("<div class='page-subtitle'>Descarga los datasets para tu investigacion periodistica</div>", unsafe_allow_html=True)
    
    # ========================================
    # RESUMEN DE DATOS DISPONIBLES
    # ========================================
    
    stats = cargar_resumen_datos()
    
    st.markdown("### Datos disponibles")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Legisladores vigentes", f"{stats['legisladores_vigentes']:,}")
    col2.metric("Declaraciones juradas", f"{stats['ddjj_total']:,}")
    col3.metric("Votaciones HCDN", f"{stats['votaciones']:,}")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Votos individuales", f"{stats['votos']:,}")
    col2.metric("Audiencias ejecutivo", f"{stats['audiencias']:,}")
    col3.metric("Anios de DDJJ", f"{stats['ddjj_anios']}")
    
    st.markdown("---")
    
    # ========================================
    # EXPORTAR DATASETS
    # ========================================
    
    st.markdown("### Descargar datasets")
    st.caption("Todos los datos son de fuentes publicas oficiales")
    
    tab1, tab2, tab3 = st.tabs(["Legisladores", "Patrimonio", "Votaciones"])
    
    with tab1:
        st.markdown("**Legisladores vigentes**")
        st.caption("Nombre, camara, bloque, distrito y fin de mandato")
        
        if st.button("Preparar descarga", key="prep_leg"):
            with st.spinner("Cargando datos..."):
                df = exportar_legisladores()
                st.success(f"{len(df)} legisladores")
                st.download_button(
                    "Descargar CSV",
                    df.to_csv(index=False).encode('utf-8'),
                    "legisladores_vigentes.csv",
                    "text/csv",
                    use_container_width=True
                )
                st.dataframe(df.head(10), use_container_width=True)
    
    with tab2:
        st.markdown("**Declaraciones Juradas Patrimoniales**")
        st.caption("Patrimonio neto, bienes y deudas por legislador y anio")
        
        if st.button("Preparar descarga", key="prep_pat"):
            with st.spinner("Cargando datos..."):
                df = exportar_patrimonio()
                st.success(f"{len(df)} registros")
                st.download_button(
                    "Descargar CSV",
                    df.to_csv(index=False).encode('utf-8'),
                    "patrimonio_legisladores.csv",
                    "text/csv",
                    use_container_width=True
                )
                st.dataframe(df.head(10), use_container_width=True)
    
    with tab3:
        st.markdown("**Votaciones HCDN**")
        st.caption("Ultimas 1000 votaciones con resultados")
        
        if st.button("Preparar descarga", key="prep_vot"):
            with st.spinner("Cargando datos..."):
                df = exportar_votaciones()
                st.success(f"{len(df)} votaciones")
                st.download_button(
                    "Descargar CSV",
                    df.to_csv(index=False).encode('utf-8'),
                    "votaciones_hcdn.csv",
                    "text/csv",
                    use_container_width=True
                )
                st.dataframe(df.head(10), use_container_width=True)
    
    st.markdown("---")
    
    # ========================================
    # METODOLOGIA
    # ========================================
    
    st.markdown("### Metodologia")
    
    with st.expander("Fuentes de datos"):
        st.markdown("""
        | Dataset | Fuente | Actualizacion |
        |---------|--------|---------------|
        | Legisladores | HCDN / Senado | Manual |
        | DDJJ Patrimoniales | Oficina Anticorrupcion (datos.jus.gob.ar) | Anual |
        | Votaciones | HCDN (votaciones.hcdn.gob.ar) | Automatica (semanal) |
        | Audiencias Ejecutivo | datos.gob.ar | Manual |
        | Indicadores economicos | INDEC / BCRA | Manual |
        """)
    
    with st.expander("Calculos y definiciones"):
        st.markdown("""
        **Patrimonio neto:** Total de bienes menos total de deudas, segun DDJJ.
        
        **Variacion real:** Ajusta el cambio patrimonial por inflacion.
        - Formula: ((1 + var_nominal) / (1 + inflacion)) - 1
        - Positivo = gano poder adquisitivo
        - Negativo = perdio poder adquisitivo
        
        **Mediana:** Valor del medio cuando se ordenan todos los patrimonios. 
        Es mas representativa que el promedio porque no se distorsiona con valores extremos.
        
        **Inflacion acumulada 2022-2024:** 493% (IPC INDEC)
        """)
    
    with st.expander("Limitaciones"):
        st.markdown("""
        - **DDJJ:** Solo incluye lo declarado. El patrimonio real puede diferir.
        - **Vinculacion:** No todas las DDJJ estan vinculadas a legisladores en nuestra base.
        - **Votaciones:** Solo HCDN (Diputados). Senado en desarrollo.
        - **Cobertura temporal:** DDJJ disponibles: 2019, 2020, 2021, 2022, 2024. Falta 2023.
        """)
    
    st.markdown("---")
    
    # ========================================
    # CONTACTO
    # ========================================
    
    st.markdown("### Contacto")
    
    st.markdown("""
    <div style="background: #F3F4F6; padding: 1.5rem; border-radius: 12px;">
        <div style="font-size: 1.1rem; font-weight: 600; margin-bottom: 0.5rem;">Para consultas, sugerencias o reportar errores:</div>
        <div style="font-size: 1rem; margin-bottom: 1rem;">
            <a href="mailto:lobby.matufia@gmail.com" style="color: #2563EB; text-decoration: none;">
                lobby.matufia@gmail.com
            </a>
        </div>
        <div style="font-size: 0.9rem; color: #6B7280;">
            Lobby es un proyecto de inteligencia publica que busca facilitar el acceso 
            a informacion sobre el Congreso argentino para periodistas e investigadores.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="text-align: center; color: #9CA3AF; font-size: 0.85rem; margin-top: 2rem;">
        Todos los datos provienen de fuentes publicas oficiales.<br>
        El codigo fuente esta disponible en GitHub.
    </div>
    """, unsafe_allow_html=True)