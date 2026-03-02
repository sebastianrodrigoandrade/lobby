"""
Lobby - Página de Inicio / Dashboard
"""
import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal


@st.cache_data(ttl=1800)
def cargar_ultimas_votaciones(limit=5):
    db = SessionLocal()
    result = db.execute(text("""
        SELECT acta_id, titulo, fecha, resultado,
               votos_afirmativos, votos_negativos, abstenciones
        FROM actas_cabecera
        WHERE fecha IS NOT NULL AND titulo IS NOT NULL
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
    
    sesiones = db.execute(text("""
        SELECT COUNT(*) FROM sesiones 
        WHERE EXTRACT(YEAR FROM fecha) >= 2024
    """)).scalar()
    
    ddjj = db.execute(text("SELECT COUNT(*) FROM ddjj_legisladores")).scalar()
    
    db.close()
    return {
        'legisladores': leg or 0,
        'votos': votos or 0,
        'sesiones': sesiones or 0,
        'ddjj': ddjj or 0
    }


@st.cache_data(ttl=3600)
def cargar_votaciones_ajustadas():
    """Votaciones con menor diferencia de votos"""
    db = SessionLocal()
    result = db.execute(text("""
        SELECT acta_id, titulo, fecha, resultado,
               votos_afirmativos, votos_negativos,
               ABS(votos_afirmativos - votos_negativos) as diferencia
        FROM actas_cabecera
        WHERE fecha IS NOT NULL 
          AND votos_afirmativos > 0 
          AND votos_negativos > 0
        ORDER BY diferencia ASC
        LIMIT 5
    """))
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


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
        st.markdown("## Actividad reciente")
        
        df_votos = cargar_ultimas_votaciones(5)
        
        if not df_votos.empty:
            for _, row in df_votos.iterrows():
                titulo = row['titulo'][:80] + "..." if len(str(row['titulo'])) > 80 else row['titulo']
                fecha = row['fecha']
                afirm = int(row['votos_afirmativos'] or 0)
                neg = int(row['votos_negativos'] or 0)
                
                if afirm > neg:
                    badge = '<span class="lobby-badge lobby-badge-green">Aprobado</span>'
                elif neg > afirm:
                    badge = '<span class="lobby-badge lobby-badge-red">Rechazado</span>'
                else:
                    badge = '<span class="lobby-badge lobby-badge-gray">Empate</span>'
                
                st.markdown(f"""
                <div class="activity-item">
                    <div class="activity-icon activity-icon-vote">🗳️</div>
                    <div class="activity-content">
                        <div class="activity-title">{titulo}</div>
                        <div class="activity-meta">
                            {fecha} · {afirm} ✓ · {neg} ✗ {badge}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No hay votaciones recientes cargadas.")
        
        # Últimas sesiones
        st.markdown("### Últimas sesiones")
        df_sesiones = cargar_ultimas_sesiones(3)
        
        if not df_sesiones.empty:
            for _, row in df_sesiones.iterrows():
                fecha = row['fecha']
                tipo = row['tipo_periodo'] or "—"
                duracion = f"{float(row['duracion_horas']):.1f}h" if row['duracion_horas'] else "—"
                quorum = row['hubo_quorum']
                
                quorum_badge = '<span class="lobby-badge lobby-badge-green">Con quórum</span>' if quorum == 'Sí' else '<span class="lobby-badge lobby-badge-red">Sin quórum</span>'
                
                st.markdown(f"""
                <div class="activity-item">
                    <div class="activity-icon activity-icon-session">📋</div>
                    <div class="activity-content">
                        <div class="activity-title">{tipo}</div>
                        <div class="activity-meta">
                            {fecha} · Duración: {duracion} {quorum_badge}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    with col_der:
        st.markdown("## Votaciones más ajustadas")
        st.caption("Menor diferencia entre afirmativos y negativos")
        
        df_disputadas = cargar_votaciones_ajustadas()
        
        if not df_disputadas.empty:
            for i, (_, row) in enumerate(df_disputadas.iterrows(), 1):
                titulo = row['titulo'][:50] + "..." if len(str(row['titulo'])) > 50 else row['titulo']
                afirm = int(row['votos_afirmativos'] or 0)
                neg = int(row['votos_negativos'] or 0)
                dif = int(row['diferencia'] or 0)
                
                st.markdown(f"""
                <div class="ranking-item">
                    <div class="ranking-position">{i}</div>
                    <div class="ranking-content">
                        <div class="ranking-name">{titulo}</div>
                        <div class="ranking-meta">{afirm} ✓ vs {neg} ✗</div>
                    </div>
                    <div class="ranking-value" style="color: #D97706">Δ{dif}</div>
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        st.markdown("### Acceso rápido")
        
        st.markdown("""
        <div class="lobby-card">
            <div class="lobby-card-title">🔍 Buscar legislador</div>
            <div class="lobby-card-meta">Perfil completo, votaciones, patrimonio</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="lobby-card">
            <div class="lobby-card-title">📊 Ranking patrimonial</div>
            <div class="lobby-card-meta">Evolución de declaraciones juradas</div>
        </div>
        """, unsafe_allow_html=True)

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; padding: 2rem 0; color: #9CA3AF; font-size: 0.85rem;">
        <strong>Lobby</strong> · Plataforma de Inteligencia Pública<br>
        Datos: HCDN, Senado, Oficina Anticorrupción · Actualización continua
    </div>
    """, unsafe_allow_html=True)
