# -*- coding: utf-8 -*-
"""
Lobby - Página de Actividad Legislativa
Sesiones, votaciones, asistencia y proyectos
"""
import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal

# ============================================
# FUNCIONES DE CARGA
# ============================================

@st.cache_data(ttl=3600)
def cargar_resumen_sesiones():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total,
                SUM(duracion_horas::numeric) as horas_total,
                AVG(duracion_horas::numeric) as horas_prom,
                SUM(CASE WHEN hubo_quorum = 'Sí' THEN 1 ELSE 0 END) as con_quorum,
                SUM(CASE WHEN hubo_quorum != 'Sí' THEN 1 ELSE 0 END) as sin_quorum
            FROM sesiones
        """))
        row = result.fetchone()
        return {
            'total': row[0],
            'horas_total': float(row[1] or 0),
            'horas_prom': float(row[2] or 0),
            'con_quorum': row[3],
            'sin_quorum': row[4]
        }
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_sesiones_por_tipo():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT tipo_reunion, 
                   COUNT(*) as cantidad,
                   AVG(duracion_horas::numeric) as duracion_prom,
                   SUM(CASE WHEN hubo_quorum = 'Sí' THEN 1 ELSE 0 END) as con_quorum
            FROM sesiones
            GROUP BY tipo_reunion
            ORDER BY cantidad DESC
        """))
        return pd.DataFrame(result.fetchall(), columns=['tipo', 'cantidad', 'duracion_prom', 'con_quorum'])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_sesiones_fallidas():
    """Sesiones de minoría o sin quorum."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT fecha, tipo_reunion, duracion_horas, hubo_quorum
            FROM sesiones
            WHERE hubo_quorum != 'Sí' OR tipo_reunion ILIKE '%minoría%' OR tipo_reunion ILIKE '%fracasada%'
            ORDER BY fecha DESC
        """))
        return pd.DataFrame(result.fetchall(), columns=['fecha', 'tipo', 'duracion', 'quorum'])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_asistencia_legisladores():
    """Asistencia basada en votos."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                l.id,
                l.nombre_completo,
                l.bloque,
                l.camara,
                COUNT(*) as total_votos,
                COUNT(*) FILTER (WHERE v.voto = 'AUSENTE') as ausentes,
                COUNT(*) FILTER (WHERE v.voto = 'AFIRMATIVO') as afirmativos,
                COUNT(*) FILTER (WHERE v.voto = 'NEGATIVO') as negativos,
                COUNT(*) FILTER (WHERE v.voto = 'ABSTENCION') as abstenciones
            FROM votos_hcdn v
            JOIN legisladores l ON v.legislador_id = l.id
            WHERE l.mandato_hasta >= CURRENT_DATE
            GROUP BY l.id, l.nombre_completo, l.bloque, l.camara
            HAVING COUNT(*) >= 50
            ORDER BY COUNT(*) FILTER (WHERE v.voto = 'AUSENTE')::float / COUNT(*) DESC
        """))
        df = pd.DataFrame(result.fetchall(), columns=[
            'id', 'nombre', 'bloque', 'camara', 'total_votos', 
            'ausentes', 'afirmativos', 'negativos', 'abstenciones'
        ])
        df['pct_ausencia'] = (df['ausentes'] / df['total_votos'] * 100).round(1)
        df['pct_asistencia'] = 100 - df['pct_ausencia']
        return df
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_votaciones_recientes(limit=50):
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT fecha, hora, asunto, resultado, 
                   afirmativos, negativos, abstenciones, ausentes
            FROM votaciones_hcdn
            ORDER BY TO_DATE(fecha, 'DD/MM/YYYY') DESC, hora DESC
            LIMIT :limit
        """), {'limit': limit})
        return pd.DataFrame(result.fetchall(), columns=[
            'fecha', 'hora', 'asunto', 'resultado',
            'afirmativos', 'negativos', 'abstenciones', 'ausentes'
        ])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_resumen_votaciones():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total,
                AVG(afirmativos + negativos + abstenciones) as votos_prom,
                AVG(ausentes) as ausentes_prom
            FROM votaciones_hcdn
        """))
        row = result.fetchone()
        return {
            'total': row[0],
            'votos_prom': float(row[1] or 0),
            'ausentes_prom': float(row[2] or 0)
        }
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_proyectos_stats():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE nro_expediente LIKE '%-D-%') as diputados,
                COUNT(*) FILTER (WHERE nro_expediente LIKE '%-S-%') as senado,
                COUNT(*) FILTER (WHERE nro_expediente LIKE '%-PE-%') as ejecutivo,
                MIN(fecha_ingreso) as desde,
                MAX(fecha_ingreso) as hasta
            FROM proyectos
            WHERE titulo NOT LIKE '%ingresó a la base%' AND titulo NOT LIKE '%prueba%'
        """))
        row = result.fetchone()
        return {
            'total': row[0],
            'diputados': row[1],
            'senado': row[2],
            'ejecutivo': row[3],
            'desde': row[4],
            'hasta': row[5]
        }
    finally:
        db.close()

def fmt_pct(valor):
    if valor is None:
        return "N/A"
    return f"{valor:.1f}%"

# ============================================
# RENDER
# ============================================

def render():
    st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
    st.title("Actividad Legislativa")
    st.markdown("<div class='page-subtitle'>Sesiones, votaciones, asistencia y proyectos</div>", unsafe_allow_html=True)
    
    tabs = st.tabs(["Sesiones", "Asistencia", "Votaciones", "Proyectos"])
    
    # ========================================
    # TAB SESIONES
    # ========================================
    with tabs[0]:
        stats = cargar_resumen_sesiones()
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total sesiones", stats['total'])
        col2.metric("Horas totales", f"{stats['horas_total']:.0f}h")
        col3.metric("Duración promedio", f"{stats['horas_prom']:.1f}h")
        col4.metric("Sin quorum", stats['sin_quorum'], delta=None if stats['sin_quorum'] == 0 else f"{stats['sin_quorum']} fallidas", delta_color="inverse")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Por tipo de sesión")
            df_tipo = cargar_sesiones_por_tipo()
            
            for _, row in df_tipo.iterrows():
                quorum_pct = (row['con_quorum'] / row['cantidad'] * 100) if row['cantidad'] > 0 else 0
                color = "#059669" if quorum_pct == 100 else "#F59E0B" if quorum_pct > 50 else "#DC2626"
                
                st.markdown(f"""
                <div style="background: white; border: 1px solid #E5E7EB; border-radius: 8px; padding: 0.8rem; margin-bottom: 0.5rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="font-weight: 600;">{row['tipo']}</span>
                        </div>
                        <div style="text-align: right;">
                            <span style="font-weight: 600;">{int(row['cantidad'])}</span>
                            <span style="color: #6B7280; font-size: 0.85rem;"> sesiones</span>
                        </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: #6B7280; margin-top: 0.3rem;">
                        <span>Duración prom: {row['duracion_prom']:.1f}h</span>
                        <span style="color: {color};">Quorum: {quorum_pct:.0f}%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("### Sesiones fallidas / sin quorum")
            df_fallidas = cargar_sesiones_fallidas()
            
            if df_fallidas.empty:
                st.success("No hay sesiones fallidas registradas")
            else:
                for _, row in df_fallidas.iterrows():
                    st.markdown(f"""
                    <div style="background: #FEF2F2; border-left: 4px solid #DC2626; padding: 0.6rem 1rem; margin-bottom: 0.4rem; border-radius: 0 8px 8px 0;">
                        <div style="display: flex; justify-content: space-between;">
                            <span style="font-weight: 600;">{row['fecha']}</span>
                            <span style="color: #DC2626;">{row['tipo']}</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    
    # ========================================
    # TAB ASISTENCIA
    # ========================================
    with tabs[1]:
        st.markdown("### Asistencia a votaciones")
        st.caption("Basado en votos nominales registrados (mínimo 50 votaciones)")
        
        df_asist = cargar_asistencia_legisladores()
        
        if df_asist.empty:
            st.info("No hay datos de asistencia disponibles")
        else:
            # Métricas generales
            prom_ausencia = df_asist['pct_ausencia'].mean()
            max_ausencia = df_asist['pct_ausencia'].max()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Legisladores analizados", len(df_asist))
            col2.metric("Ausencia promedio", fmt_pct(prom_ausencia))
            col3.metric("Máxima ausencia", fmt_pct(max_ausencia))
            
            st.markdown("---")
            
            # Filtro
            filtro = st.radio("Ordenar por:", ["Más ausentes", "Más presentes"], horizontal=True)
            
            if filtro == "Más presentes":
                df_mostrar = df_asist.sort_values('pct_ausencia').head(30)
            else:
                df_mostrar = df_asist.head(30)
            
            for _, row in df_mostrar.iterrows():
                # Color según ausencia
                if row['pct_ausencia'] > 50:
                    color = "#DC2626"
                    bg = "#FEF2F2"
                elif row['pct_ausencia'] > 20:
                    color = "#F59E0B"
                    bg = "#FFFBEB"
                else:
                    color = "#059669"
                    bg = "#ECFDF5"
                
                st.markdown(f"""
                <div style="background: {bg}; border-left: 4px solid {color}; padding: 0.6rem 1rem; margin-bottom: 0.4rem; border-radius: 0 8px 8px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="font-weight: 600;">{row['nombre']}</span>
                            <span style="color: #6B7280; font-size: 0.85rem;"> - {row['bloque']}</span>
                        </div>
                        <div style="text-align: right;">
                            <span style="color: {color}; font-weight: 600;">{fmt_pct(row['pct_ausencia'])} ausencia</span>
                            <span style="color: #6B7280; font-size: 0.85rem;"> ({int(row['ausentes'])}/{int(row['total_votos'])})</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
    # ========================================
    # TAB VOTACIONES
    # ========================================
    with tabs[2]:
        stats_vot = cargar_resumen_votaciones()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total votaciones", f"{stats_vot['total']:,}")
        col2.metric("Votos promedio", f"{stats_vot['votos_prom']:.0f}")
        col3.metric("Ausentes promedio", f"{stats_vot['ausentes_prom']:.0f}")
        
        st.markdown("---")
        st.markdown("### Votaciones recientes")
        
        df_vot = cargar_votaciones_recientes(30)
        
        for _, row in df_vot.iterrows():
            total_votos = row['afirmativos'] + row['negativos'] + row['abstenciones']
            pct_afirm = (row['afirmativos'] / total_votos * 100) if total_votos > 0 else 0
            
            if pct_afirm >= 66:
                color = "#059669"
            elif pct_afirm >= 50:
                color = "#2563EB"
            else:
                color = "#DC2626"
            
            st.markdown(f"""
            <div style="background: white; border: 1px solid #E5E7EB; border-radius: 8px; padding: 0.8rem; margin-bottom: 0.5rem;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.3rem;">
                    <span style="color: #6B7280; font-size: 0.85rem;">{row['fecha']} {row['hora']}</span>
                    <span style="color: {color}; font-weight: 600;">{int(row['afirmativos'])}-{int(row['negativos'])}-{int(row['abstenciones'])}</span>
                </div>
                <div style="font-size: 0.9rem;">{row['asunto'][:150]}{'...' if len(str(row['asunto'])) > 150 else ''}</div>
            </div>
            """, unsafe_allow_html=True)
    
    # ========================================
    # TAB PROYECTOS
    # ========================================
    with tabs[3]:
        stats_proy = cargar_proyectos_stats()
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total proyectos", f"{stats_proy['total']:,}")
        col2.metric("De Diputados", f"{stats_proy['diputados']:,}")
        col3.metric("Del Senado", f"{stats_proy['senado']:,}")
        col4.metric("Del Ejecutivo", f"{stats_proy['ejecutivo']:,}")
        
        st.markdown("---")
        st.info(f"Datos desde {stats_proy['desde']} hasta {stats_proy['hasta']}")
        st.caption("Próximamente: proyectos por autor, por tipo, con media sanción, tiempo de tratamiento")
