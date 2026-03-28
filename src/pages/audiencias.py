# -*- coding: utf-8 -*-
"""
Lobby - Página de Audiencias
Audiencias del Poder Ejecutivo vinculadas a legisladores vigentes
"""
import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal

# ============================================
# FUNCIONES DE CARGA
# ============================================

@st.cache_data(ttl=3600)
def cargar_estadisticas_audiencias():
    db = SessionLocal()
    try:
        # Solo audiencias de legisladores vigentes
        result = db.execute(text("""
            SELECT 
                COUNT(DISTINCT al.audiencia_id) as total,
                COUNT(DISTINCT l.id) as legisladores
            FROM audiencias_legisladores al
            JOIN legisladores l ON l.id = al.legislador_id
            WHERE l.mandato_hasta >= CURRENT_DATE
        """))
        row = result.fetchone()
        
        result2 = db.execute(text("SELECT MIN(anio), MAX(anio) FROM audiencias_ejecutivo"))
        periodo = result2.fetchone()
        
        return {
            'total': row[0],
            'legisladores': row[1],
            'desde': periodo[0],
            'hasta': periodo[1]
        }
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_legisladores_con_audiencias():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT l.id, l.nombre_completo, l.bloque, l.camara, l.foto_url,
                   COUNT(*) FILTER (WHERE al.rol = 'funcionario') as como_funcionario,
                   COUNT(*) FILTER (WHERE al.rol = 'solicitante') as como_solicitante
            FROM audiencias_legisladores al
            JOIN legisladores l ON l.id = al.legislador_id
            WHERE l.mandato_hasta >= CURRENT_DATE
            GROUP BY l.id, l.nombre_completo, l.bloque, l.camara, l.foto_url
            ORDER BY (COUNT(*) FILTER (WHERE al.rol = 'funcionario') + 
                      COUNT(*) FILTER (WHERE al.rol = 'solicitante')) DESC
        """))
        return pd.DataFrame(result.fetchall(), columns=[
            'id', 'nombre', 'bloque', 'camara', 'foto_url', 'como_funcionario', 'como_solicitante'
        ])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_audiencias_legislador(legislador_id, limit=100):
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT a.fecha, a.sujeto_obligado_nombre, a.sujeto_obligado_cargo,
                   a.sujeto_obligado_dependencia, a.solicitante_nombre,
                   a.solicitante_ocupacion, a.motivo, al.rol
            FROM audiencias_legisladores al
            JOIN audiencias_ejecutivo a ON a.id = al.audiencia_id
            WHERE al.legislador_id = :leg_id
            ORDER BY a.fecha DESC
            LIMIT :limit
        """), {"leg_id": legislador_id, "limit": limit})
        return pd.DataFrame(result.fetchall(), columns=[
            'fecha', 'funcionario', 'cargo', 'dependencia', 
            'solicitante', 'ocupacion', 'motivo', 'rol'
        ])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def buscar_audiencias_legisladores(filtros, limit=50, offset=0):
    """Buscar audiencias solo de legisladores vigentes."""
    db = SessionLocal()
    try:
        where = ["l.mandato_hasta >= CURRENT_DATE"]
        params = {"limit": limit, "offset": offset}
        
        if filtros.get('legislador'):
            where.append("l.nombre_completo ILIKE :leg")
            params['leg'] = f"%{filtros['legislador']}%"
        
        if filtros.get('rol'):
            where.append("al.rol = :rol")
            params['rol'] = filtros['rol']
        
        if filtros.get('motivo'):
            where.append("(a.motivo ILIKE :mot OR a.sintesis ILIKE :mot)")
            params['mot'] = f"%{filtros['motivo']}%"
        
        if filtros.get('anio'):
            where.append("a.anio = :anio")
            params['anio'] = filtros['anio']
        
        where_clause = " AND ".join(where)
        
        count_result = db.execute(text(f"""
            SELECT COUNT(DISTINCT a.id) 
            FROM audiencias_legisladores al
            JOIN audiencias_ejecutivo a ON a.id = al.audiencia_id
            JOIN legisladores l ON l.id = al.legislador_id
            WHERE {where_clause}
        """), params)
        total = count_result.scalar()
        
        result = db.execute(text(f"""
            SELECT DISTINCT a.fecha, a.sujeto_obligado_nombre, a.sujeto_obligado_cargo,
                   a.sujeto_obligado_dependencia, a.solicitante_nombre, 
                   a.solicitante_ocupacion, a.motivo, al.rol,
                   l.nombre_completo as legislador
            FROM audiencias_legisladores al
            JOIN audiencias_ejecutivo a ON a.id = al.audiencia_id
            JOIN legisladores l ON l.id = al.legislador_id
            WHERE {where_clause}
            ORDER BY a.fecha DESC
            LIMIT :limit OFFSET :offset
        """), params)
        
        df = pd.DataFrame(result.fetchall(), columns=[
            'fecha', 'funcionario', 'cargo', 'dependencia', 
            'solicitante', 'ocupacion', 'motivo', 'rol', 'legislador'
        ])
        
        return df, total
    finally:
        db.close()

# ============================================
# RENDER
# ============================================

def render():
    st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
    st.title("Audiencias")
    st.markdown("<div class='page-subtitle'>Audiencias del Ejecutivo de legisladores vigentes</div>", unsafe_allow_html=True)
    
    stats = cargar_estadisticas_audiencias()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Audiencias vinculadas", f"{stats['total']:,}")
    col2.metric("Legisladores", f"{stats['legisladores']:,}")
    col3.metric("Periodo", f"{stats['desde']}-{stats['hasta']}")
    
    st.markdown("---")
    
    tabs = st.tabs(["Por Legislador", "Buscar"])
    
    # ========================================
    # TAB POR LEGISLADOR
    # ========================================
    with tabs[0]:
        df_leg = cargar_legisladores_con_audiencias()
        
        if df_leg.empty:
            st.info("No se encontraron legisladores vigentes con audiencias.")
            return
        
        st.markdown(f"**{len(df_leg)} legisladores vigentes con audiencias del Ejecutivo**")
        
        # Selector de legislador
        opciones = df_leg['nombre'].tolist()
        seleccionado = st.selectbox("Seleccionar legislador:", [""] + opciones, key="aud_leg_sel")
        
        if not seleccionado:
            # Mostrar lista resumen
            st.markdown("---")
            for _, row in df_leg.iterrows():
                total = row['como_funcionario'] + row['como_solicitante']
                foto = row['foto_url'] if pd.notna(row['foto_url']) else None
                
                if foto:
                    foto_html = f'<img src="{foto}" style="width: 45px; height: 45px; border-radius: 50%; object-fit: cover;">'
                else:
                    foto_html = f'<div style="width: 45px; height: 45px; border-radius: 50%; background: #E5E7EB; display: flex; align-items: center; justify-content: center; font-weight: 600; color: #6B7280;">{row["nombre"][0]}</div>'
                
                st.markdown(f"""
                <div style="display: flex; align-items: center; gap: 1rem; padding: 0.8rem 0; border-bottom: 1px solid #F3F4F6;">
                    {foto_html}
                    <div style="flex: 1;">
                        <div style="font-weight: 600;">{row['nombre']}</div>
                        <div style="font-size: 0.85rem; color: #6B7280;">{row['bloque']} - {row['camara']}</div>
                    </div>
                    <div style="text-align: right; font-size: 0.9rem;">
                        <div><span style="color: #2563EB; font-weight: 600;">{row['como_funcionario']}</span> <span style="color: #9CA3AF;">como funcionario</span></div>
                        <div><span style="color: #059669; font-weight: 600;">{row['como_solicitante']}</span> <span style="color: #9CA3AF;">como solicitante</span></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            # Mostrar audiencias del legislador
            leg_row = df_leg[df_leg['nombre'] == seleccionado].iloc[0]
            leg_id = int(leg_row['id'])
            
            # Header del legislador
            foto = leg_row['foto_url'] if pd.notna(leg_row['foto_url']) else None
            if foto:
                foto_html = f'<img src="{foto}" style="width: 80px; height: 80px; border-radius: 50%; object-fit: cover;">'
            else:
                foto_html = f'<div style="width: 80px; height: 80px; border-radius: 50%; background: #E5E7EB; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 2rem; color: #6B7280;">{seleccionado[0]}</div>'
            
            st.markdown(f"""
            <div style="display: flex; align-items: center; gap: 1.5rem; padding: 1rem; background: #F9FAFB; border-radius: 12px; margin-bottom: 1rem;">
                {foto_html}
                <div>
                    <div style="font-weight: 700; font-size: 1.2rem;">{seleccionado}</div>
                    <div style="color: #6B7280;">{leg_row['bloque']} - {leg_row['camara']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            col1.metric("Como funcionario", int(leg_row['como_funcionario']))
            col2.metric("Como solicitante", int(leg_row['como_solicitante']))
            
            df_aud = cargar_audiencias_legislador(leg_id)
            
            if df_aud.empty:
                st.info("No se encontraron audiencias.")
            else:
                st.markdown("---")
                st.markdown("### Audiencias")
                
                for _, row in df_aud.iterrows():
                    rol_color = "#2563EB" if row['rol'] == 'funcionario' else "#059669"
                    rol_text = "Como funcionario" if row['rol'] == 'funcionario' else "Como solicitante"
                    
                    st.markdown(f"""
                    <div style="background: white; border: 1px solid #E5E7EB; border-left: 4px solid {rol_color}; border-radius: 0 8px 8px 0; padding: 1rem; margin-bottom: 0.5rem;">
                        <div style="display: flex; justify-content: space-between; flex-wrap: wrap; margin-bottom: 0.5rem;">
                            <span style="background: {rol_color}15; color: {rol_color}; padding: 0.2rem 0.6rem; border-radius: 4px; font-size: 0.8rem; font-weight: 600;">{rol_text}</span>
                            <span style="color: #6B7280; font-size: 0.85rem;">{row['fecha'] or ''}</span>
                        </div>
                        <div>
                            <strong>{row['funcionario']}</strong>
                            <span style="color: #6B7280;"> - {row['cargo'] or ''}</span>
                        </div>
                        <div style="font-size: 0.85rem; color: #6B7280;">{row['dependencia'] or ''}</div>
                        <div style="margin-top: 0.5rem; font-size: 0.9rem;">
                            Solicitante: <strong>{row['solicitante'] or 'No especificado'}</strong>
                            <span style="color: #6B7280;"> ({row['ocupacion'] or ''})</span>
                        </div>
                        <div style="font-size: 0.9rem; color: #374151; background: #F9FAFB; padding: 0.5rem; border-radius: 4px; margin-top: 0.5rem;">
                            {row['motivo'][:300] if row['motivo'] else ''}{'...' if row['motivo'] and len(row['motivo']) > 300 else ''}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    
    # ========================================
    # TAB BUSCAR
    # ========================================
    with tabs[1]:
        st.markdown("### Buscar en audiencias de legisladores vigentes")
        
        col1, col2 = st.columns(2)
        with col1:
            filtro_leg = st.text_input("Legislador", placeholder="Nombre del legislador...", key="aud_busq_leg")
            filtro_rol = st.selectbox("Rol", [None, "funcionario", "solicitante"], 
                                      format_func=lambda x: "Todos" if x is None else x.title(), key="aud_busq_rol")
        with col2:
            filtro_motivo = st.text_input("Motivo/Tema", placeholder="Buscar en motivo...", key="aud_busq_mot")
            filtro_anio = st.selectbox("Año", [None] + list(range(2025, 2016, -1)), 
                                       format_func=lambda x: "Todos" if x is None else str(x), key="aud_busq_anio")
        
        if 'aud_busq_page' not in st.session_state:
            st.session_state['aud_busq_page'] = 0
        
        page_size = 25
        
        filtros = {
            'legislador': filtro_leg,
            'rol': filtro_rol,
            'motivo': filtro_motivo,
            'anio': filtro_anio
        }
        
        df, total = buscar_audiencias_legisladores(filtros, limit=page_size, offset=st.session_state['aud_busq_page'] * page_size)
        
        st.markdown(f"**{total:,} audiencias encontradas**")
        
        if not df.empty:
            for _, row in df.iterrows():
                rol_color = "#2563EB" if row['rol'] == 'funcionario' else "#059669"
                
                st.markdown(f"""
                <div style="background: white; border: 1px solid #E5E7EB; border-radius: 8px; padding: 1rem; margin-bottom: 0.5rem;">
                    <div style="display: flex; justify-content: space-between; flex-wrap: wrap;">
                        <div>
                            <span style="background: {rol_color}15; color: {rol_color}; padding: 0.15rem 0.4rem; border-radius: 4px; font-size: 0.75rem;">{row['legislador']}</span>
                            <span style="color: #6B7280; font-size: 0.85rem; margin-left: 0.5rem;">{row['fecha'] or ''}</span>
                        </div>
                    </div>
                    <div style="margin-top: 0.5rem;">
                        <strong>{row['funcionario']}</strong>
                        <span style="color: #6B7280;"> - {row['cargo'] or ''}</span>
                    </div>
                    <div style="font-size: 0.85rem; color: #6B7280;">{row['dependencia'] or ''}</div>
                    <div style="margin-top: 0.3rem; font-size: 0.9rem;">
                        Solicitante: <strong>{row['solicitante'] or 'No especificado'}</strong>
                    </div>
                    <div style="font-size: 0.85rem; color: #374151; background: #F9FAFB; padding: 0.4rem; border-radius: 4px; margin-top: 0.4rem;">
                        {row['motivo'][:200] if row['motivo'] else ''}{'...' if row['motivo'] and len(row['motivo']) > 200 else ''}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            total_pages = max(1, (total // page_size) + (1 if total % page_size > 0 else 0))
            
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if st.button("Anterior", disabled=st.session_state['aud_busq_page'] == 0, key="aud_busq_prev"):
                    st.session_state['aud_busq_page'] -= 1
                    st.rerun()
            with col2:
                st.markdown(f"<div style='text-align: center;'>Pagina {st.session_state['aud_busq_page'] + 1} de {total_pages}</div>", unsafe_allow_html=True)
            with col3:
                if st.button("Siguiente", disabled=st.session_state['aud_busq_page'] >= total_pages - 1, key="aud_busq_next"):
                    st.session_state['aud_busq_page'] += 1
                    st.rerun()
