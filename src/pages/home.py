"""
Lobby - Página de Inicio / Dashboard
"""
import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal


@st.cache_data(ttl=1800)
def cargar_ultimas_votaciones(limit=5, tipo=None):
    db = SessionLocal()
    
    filtros = ["fecha IS NOT NULL", "titulo IS NOT NULL"]
    if tipo and tipo != "Todas":
        if tipo == "Leyes":
            filtros.append("(titulo ILIKE '%LEY%' OR resultado ILIKE '%LEY%')")
        elif tipo == "DNUs":
            filtros.append("titulo ILIKE '%DECRETO DE NECESIDAD%'")
        elif tipo == "Resoluciones":
            filtros.append("titulo ILIKE '%RESOLUCION%'")
    
    where = "WHERE " + " AND ".join(filtros)
    
    result = db.execute(text(f"""
        SELECT acta_id, titulo, fecha, resultado,
               votos_afirmativos, votos_negativos, abstenciones
        FROM actas_cabecera
        {where}
        ORDER BY fecha DESC, acta_id DESC
        LIMIT :limit
    """), {"limit": limit})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


@st.cache_data(ttl=1800)
def cargar_ultimas_sesiones(limit=3):
    db = SessionLocal()
    result = db.execute(text("""
        SELECT fecha, tipo_periodo, tipo_reunion, duracion_horas, hubo_quorum
        FROM sesiones
        WHERE fecha IS NOT NULL
          AND duracion_horas IS NOT NULL
          AND duracion_horas != ''
          AND duracion_horas ~ '^[0-9.]+$'
          AND duracion_horas::numeric > 0
          AND tipo_periodo IS NOT NULL
          AND tipo_periodo != ''
        ORDER BY fecha DESC
        LIMIT :limit
    """), {"limit": limit})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


@st.cache_data(ttl=3600)
def cargar_metricas_generales():
    db = SessionLocal()

    leg = db.execute(text("""
        SELECT COUNT(*) FROM legisladores
        WHERE mandato_hasta >= CURRENT_DATE
    """)).scalar()

    votos = db.execute(text("SELECT COUNT(*) FROM votos")).scalar()
    votos_hcdn = db.execute(text("SELECT COUNT(*) FROM votos_hcdn")).scalar()
    total_votos = (votos or 0) + (votos_hcdn or 0)

    sesiones = db.execute(text("""
        SELECT COUNT(*) FROM sesiones
        WHERE EXTRACT(YEAR FROM fecha) >= 2024
    """)).scalar()

    ddjj = db.execute(text("SELECT COUNT(*) FROM ddjj_legisladores WHERE patrimonio_neto > 0")).scalar()

    db.close()
    return {
        'legisladores': leg or 0,
        'votos': total_votos,
        'sesiones': sesiones or 0,
        'ddjj': ddjj or 0
    }


@st.cache_data(ttl=3600)
def cargar_votaciones_ajustadas(anio=None, limit=5):
    """Votaciones con menor diferencia de votos"""
    db = SessionLocal()
    
    filtros = [
        "fecha IS NOT NULL",
        "votos_afirmativos > 0",
        "votos_negativos > 0"
    ]
    
    if anio and anio != "Todos":
        filtros.append(f"EXTRACT(YEAR FROM fecha) = {anio}")
    
    where = "WHERE " + " AND ".join(filtros)
    
    result = db.execute(text(f"""
        SELECT acta_id, titulo, fecha, resultado,
               votos_afirmativos, votos_negativos,
               ABS(votos_afirmativos - votos_negativos) as diferencia
        FROM actas_cabecera
        {where}
        ORDER BY diferencia ASC
        LIMIT :limit
    """), {"limit": limit})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


@st.cache_data(ttl=3600)
def cargar_anios_disponibles():
    """Años con votaciones disponibles"""
    db = SessionLocal()
    result = db.execute(text("""
        SELECT DISTINCT EXTRACT(YEAR FROM fecha)::int as anio
        FROM actas_cabecera
        WHERE fecha IS NOT NULL
        ORDER BY anio DESC
    """))
    anios = [row[0] for row in result.fetchall()]
    db.close()
    return anios


@st.cache_data(ttl=3600)
def cargar_fecha_actualizacion():
    """Última fecha de actualización de datos"""
    db = SessionLocal()
    
    # Última votación
    ultima_votacion = db.execute(text("""
        SELECT MAX(fecha) FROM actas_cabecera
    """)).scalar()
    
    # Última sesión
    ultima_sesion = db.execute(text("""
        SELECT MAX(fecha) FROM sesiones
    """)).scalar()
    
    db.close()
    
    fechas = [f for f in [ultima_votacion, ultima_sesion] if f]
    return max(fechas) if fechas else None


def render():
    """Renderiza la página de inicio"""

    st.title("Monitor Legislativo")
    st.markdown("""
    <div class='page-subtitle'>
        Seguimiento de la actividad del Congreso de la Nación Argentina ·
        Votaciones, sesiones, comisiones y patrimonio de legisladores
    </div>
    """, unsafe_allow_html=True)

    # Métricas principales
    metricas = cargar_metricas_generales()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Legisladores activos", f"{metricas['legisladores']:,}")
    col2.metric("Votos registrados", f"{metricas['votos']:,}")
    col3.metric("Sesiones 2024-25", metricas['sesiones'])
    col4.metric("Declaraciones juradas", metricas['ddjj'])

    st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)

    # Dos columnas
    col_izq, col_der = st.columns([3, 2])

    with col_izq:
        # Header con filtro
        col_titulo, col_filtro = st.columns([2, 1])
        with col_titulo:
            st.markdown("## Actividad reciente")
        with col_filtro:
            tipo_filtro = st.selectbox(
                "Tipo",
                ["Todas", "Leyes", "DNUs", "Resoluciones"],
                key="filtro_tipo_actividad",
                label_visibility="collapsed"
            )

        df_votos = cargar_ultimas_votaciones(5, tipo=tipo_filtro)

        if not df_votos.empty:
            for idx, row in df_votos.iterrows():
                titulo = row['titulo'][:80] + "..." if len(str(row['titulo'])) > 80 else row['titulo']
                fecha = row['fecha']
                afirm = int(row['votos_afirmativos'] or 0)
                neg = int(row['votos_negativos'] or 0)
                acta_id = row['acta_id']

                if afirm > neg:
                    badge_color = "#059669"
                    badge_text = "Aprobado"
                elif neg > afirm:
                    badge_color = "#DC2626"
                    badge_text = "Rechazado"
                else:
                    badge_color = "#6B7280"
                    badge_text = "Empate"

                # Card clickeable
                if st.button(
                    f"🗳️ {titulo[:60]}{'...' if len(str(titulo)) > 60 else ''}",
                    key=f"votacion_{acta_id}",
                    use_container_width=True,
                    help=f"{fecha} · {afirm} ✓ · {neg} ✗ · {badge_text}"
                ):
                    st.session_state['votacion_seleccionada'] = acta_id
                    st.session_state['menu_selection'] = 'Actividad'
                    st.rerun()                
                # Info adicional debajo del botón
                st.markdown(f"""
                <div style="margin-top: -0.5rem; margin-bottom: 1rem; padding-left: 1rem; font-size: 0.85rem; color: #6B7280;">
                    {fecha} · {afirm} ✓ · {neg} ✗ 
                    <span style="background: {badge_color}20; color: {badge_color}; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">{badge_text}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No hay votaciones recientes con ese filtro.")

        # Últimas sesiones
        st.markdown("### Últimas sesiones")
        df_sesiones = cargar_ultimas_sesiones(3)

        if not df_sesiones.empty:
            for _, row in df_sesiones.iterrows():
                fecha = row['fecha']
                tipo = row['tipo_periodo'] or "Ordinaria"
                duracion = f"{float(row['duracion_horas']):.1f}h" if row['duracion_horas'] else "—"
                quorum = row['hubo_quorum']

                if quorum == 'Sí':
                    quorum_color = "#059669"
                    quorum_text = "Con quórum"
                else:
                    quorum_color = "#DC2626"
                    quorum_text = "Sin quórum"

                st.markdown(f"""
                <div style="background: white; border: 1px solid #E5E7EB; border-radius: 8px; padding: 1rem; margin-bottom: 0.5rem;">
                    <div style="display: flex; align-items: center; gap: 0.75rem;">
                        <span style="font-size: 1.5rem;">📋</span>
                        <div style="flex: 1;">
                            <div style="font-weight: 600; color: #1F2937;">{tipo}</div>
                            <div style="font-size: 0.85rem; color: #6B7280;">
                                {fecha} · Duración: {duracion}
                                <span style="background: {quorum_color}20; color: {quorum_color}; padding: 0.15rem 0.5rem; border-radius: 4px; margin-left: 0.5rem; font-size: 0.75rem;">{quorum_text}</span>
                            </div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No hay sesiones recientes cargadas.")

    with col_der:
        # Header con filtro de año
        col_titulo2, col_filtro2 = st.columns([2, 1])
        with col_titulo2:
            st.markdown("## Votaciones ajustadas")
        with col_filtro2:
            anios = cargar_anios_disponibles()
            anio_filtro = st.selectbox(
                "Año",
                ["Todos"] + anios,
                key="filtro_anio_ajustadas",
                label_visibility="collapsed"
            )

        st.caption("Menor diferencia entre afirmativos y negativos")

        df_disputadas = cargar_votaciones_ajustadas(anio=anio_filtro, limit=5)

        if not df_disputadas.empty:
            for i, (_, row) in enumerate(df_disputadas.iterrows(), 1):
                titulo = row['titulo'][:45] + "..." if len(str(row['titulo'])) > 45 else row['titulo']
                afirm = int(row['votos_afirmativos'] or 0)
                neg = int(row['votos_negativos'] or 0)
                dif = int(row['diferencia'] or 0)
                acta_id = row['acta_id']

                # Botón clickeable
                col_rank, col_btn = st.columns([0.15, 0.85])
                with col_rank:
                    st.markdown(f"""
                    <div style="font-size: 1.5rem; font-weight: 700; color: #D97706; text-align: center; padding-top: 0.5rem;">
                        #{i}
                    </div>
                    """, unsafe_allow_html=True)
                with col_btn:
                    if st.button(
                        f"{titulo}",
                        key=f"ajustada_{acta_id}",
                        use_container_width=True,
                        help=f"{afirm} ✓ vs {neg} ✗ · Diferencia: {dif} votos"
                    ):
                        st.session_state['votacion_seleccionada'] = acta_id
                        st.session_state['menu_selection'] = 'Actividad'
                        st.rerun()
                    st.markdown(f"""
                    <div style="margin-top: -0.8rem; margin-bottom: 0.5rem; font-size: 0.8rem; color: #6B7280;">
                        {afirm} ✓ vs {neg} ✗ · <span style="color: #D97706; font-weight: 600;">Δ{dif}</span>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("No hay votaciones ajustadas con ese filtro.")

        st.markdown("---")

        st.markdown("### Secciones")

        # Botones de navegación
        if st.button("🔍 Buscar legislador", use_container_width=True, help="Perfil completo, votaciones, patrimonio"):
            st.session_state['menu_selection'] = 'Legisladores'
            st.rerun()

        if st.button("📊 Ranking patrimonial", use_container_width=True, help="Evolución de declaraciones juradas"):
            st.session_state['menu_selection'] = 'Patrimonio'
            st.rerun()
        if st.button("🗳️ Votaciones", use_container_width=True, help="Historial de votaciones nominales"):
            st.session_state['menu_selection'] = 'Actividad'
            st.rerun()

        if st.button("📈 Estadísticas", use_container_width=True, help="Métricas y datos agregados"):
            st.session_state['menu_selection'] = 'Estadisticas'
            st.rerun()  

    # Footer con fecha de actualización
    fecha_actualizacion = cargar_fecha_actualizacion()
    fecha_str = fecha_actualizacion.strftime("%d/%m/%Y") if fecha_actualizacion else "—"
    
    st.markdown("---")
    st.markdown(f"""
    <div style="text-align: center; padding: 2rem 0; color: #9CA3AF; font-size: 0.85rem;">
        <strong>Lobby</strong> · Plataforma de Inteligencia Pública<br>
        Datos: HCDN, Senado, Oficina Anticorrupción · Última actualización: {fecha_str}
    </div>
    """, unsafe_allow_html=True)