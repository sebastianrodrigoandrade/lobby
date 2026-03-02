"""
Lobby - Página de Legisladores
"""
import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal
from src.styles import fmt_pesos

ENCODING = {
    '¾': 'ó', 'ß': 'á', '±': 'ñ', 'Ý': 'í', '┴': 'Á',
    '═': 'Í', 'Ë': 'Ó', 'Ð': 'Ñ', 'â': 'â',
}

def limpiar(texto):
    if not texto:
        return ''
    for mal, bien in ENCODING.items():
        texto = texto.replace(mal, bien)
    return texto


@st.cache_data(ttl=3600)
def cargar_legisladores(camara=None, solo_vigentes=True):
    db = SessionLocal()
    filtros = ["l.nombre_completo != 'xx BORRAR Manuel Isauro'",
               "COALESCE(l.bloque, '') != 'DATO INVALIDO'"]
    if camara and camara != "Todos":
        filtros.append(f"l.camara = '{camara}'")
    if solo_vigentes:
        filtros.append("l.mandato_hasta >= CURRENT_DATE")
    where = "WHERE " + " AND ".join(filtros)
    
    result = db.execute(text(f"""
        SELECT l.id, l.nombre_completo, l.camara,
               COALESCE(l.bloque, '—') as bloque,
               COALESCE(l.distrito, '—') as distrito,
               l.mandato_hasta,
               COUNT(v.id) as total_votos
        FROM legisladores l
        LEFT JOIN votos v ON v.legislador_id = l.id
        {where}
        GROUP BY l.id, l.nombre_completo, l.camara, l.bloque, l.distrito, l.mandato_hasta
        ORDER BY l.nombre_completo
    """))
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


@st.cache_data(ttl=3600)
def cargar_votos_legislador(legislador_id):
    db = SessionLocal()
    result = db.execute(text("""
        SELECT v.voto_individual, v.acta_id,
               a.fecha, a.titulo as titulo_acta, a.resultado as resultado_general
        FROM votos v
        LEFT JOIN actas_cabecera a ON a.acta_id = v.acta_id
        WHERE v.legislador_id = :id
        ORDER BY a.fecha DESC NULLS LAST
    """), {"id": legislador_id})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    df['titulo_acta'] = df['titulo_acta'].apply(limpiar)
    return df


@st.cache_data(ttl=3600)
def cargar_proyectos_legislador(nombre):
    db = SessionLocal()
    apellido = nombre.split(',')[0] if ',' in nombre else nombre.split()[0]
    result = db.execute(text("""
        SELECT nro_expediente, titulo, fecha_ingreso, estado
        FROM proyectos
        WHERE autores ILIKE :nombre
        ORDER BY fecha_ingreso DESC NULLS LAST
        LIMIT 50
    """), {"nombre": f"%{apellido}%"})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


@st.cache_data(ttl=3600)
def cargar_ddjj_legislador(legislador_id):
    db = SessionLocal()
    result = db.execute(text("""
        SELECT anio, patrimonio_neto, total_bienes, total_deudas, 
               ingresos_neto_gastos, proveedor_contratista, cuit
        FROM ddjj_legisladores
        WHERE legislador_id = :id
        ORDER BY anio DESC
    """), {"id": legislador_id})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


@st.cache_data(ttl=3600)
def calcular_afinidad(legislador_id, top_n=10):
    db = SessionLocal()
    result = db.execute(text("""
        WITH votos_ref AS (
            SELECT acta_id, voto_individual
            FROM votos
            WHERE legislador_id = :id AND acta_id IS NOT NULL
        ),
        comparacion AS (
            SELECT
                v.legislador_id,
                COUNT(*) as votaciones_compartidas,
                SUM(CASE WHEN v.voto_individual = r.voto_individual THEN 1 ELSE 0 END) as coincidencias
            FROM votos v
            JOIN votos_ref r ON r.acta_id = v.acta_id
            WHERE v.legislador_id != :id AND v.acta_id IS NOT NULL
            GROUP BY v.legislador_id
            HAVING COUNT(*) >= 20
        )
        SELECT
            l.nombre_completo,
            COALESCE(l.bloque, '—') as bloque,
            c.votaciones_compartidas, c.coincidencias,
            ROUND(c.coincidencias * 100.0 / c.votaciones_compartidas, 1) as afinidad_pct
        FROM comparacion c
        JOIN legisladores l ON l.id = c.legislador_id
        ORDER BY afinidad_pct DESC
        LIMIT :top_n
    """), {"id": legislador_id, "top_n": top_n})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


@st.cache_data(ttl=3600)
def calcular_divergencia(legislador_id, top_n=10):
    db = SessionLocal()
    result = db.execute(text("""
        WITH votos_ref AS (
            SELECT acta_id, voto_individual
            FROM votos
            WHERE legislador_id = :id AND acta_id IS NOT NULL
        ),
        comparacion AS (
            SELECT
                v.legislador_id,
                COUNT(*) as votaciones_compartidas,
                SUM(CASE WHEN v.voto_individual = r.voto_individual THEN 1 ELSE 0 END) as coincidencias
            FROM votos v
            JOIN votos_ref r ON r.acta_id = v.acta_id
            WHERE v.legislador_id != :id AND v.acta_id IS NOT NULL
            GROUP BY v.legislador_id
            HAVING COUNT(*) >= 20
        )
        SELECT
            l.nombre_completo,
            COALESCE(l.bloque, '—') as bloque,
            c.votaciones_compartidas, c.coincidencias,
            ROUND(c.coincidencias * 100.0 / c.votaciones_compartidas, 1) as afinidad_pct
        FROM comparacion c
        JOIN legisladores l ON l.id = c.legislador_id
        ORDER BY afinidad_pct ASC
        LIMIT :top_n
    """), {"id": legislador_id, "top_n": top_n})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


def render():
    """Renderiza la página de legisladores"""
    
    st.title("Legisladores")
    st.markdown("<div class='page-subtitle'>Diputados y Senadores · Perfil completo, votaciones y patrimonio</div>", unsafe_allow_html=True)

    # Filtros
    col_f1, col_f2, col_f3, col_f4 = st.columns([2, 1, 1, 1])

    with col_f1:
        busqueda = st.text_input("🔍 Buscar por nombre", placeholder="Ej: Lospennato, Kirchner, Espert...", key="leg_busq")

    with col_f2:
        camara_sel = st.selectbox("Cámara", ["Todos", "Diputados", "Senadores"], key="leg_cam")

    with col_f3:
        solo_vigentes = st.toggle("Solo vigentes", value=True, key="leg_vig")

    df_leg = cargar_legisladores(camara_sel if camara_sel != "Todos" else None, solo_vigentes)

    with col_f4:
        bloques = ["Todos"] + sorted([b for b in df_leg['bloque'].unique() if b != '—'])
        bloque_sel = st.selectbox("Bloque", bloques, key="leg_bloq")

    # Aplicar filtros
    df_filtrado = df_leg.copy()
    if busqueda:
        df_filtrado = df_filtrado[df_filtrado['nombre_completo'].str.contains(busqueda, case=False, na=False)]
    if bloque_sel != "Todos":
        df_filtrado = df_filtrado[df_filtrado['bloque'] == bloque_sel]

    if df_filtrado.empty:
        st.warning("No se encontraron legisladores con esos filtros.")
        return

    # Métricas
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Legisladores", len(df_filtrado))
    col_m2.metric("Bloques", df_filtrado['bloque'].nunique())
    col_m3.metric("Distritos", df_filtrado['distrito'].nunique())

    st.markdown("---")

    # Layout: lista + perfil
    col_lista, col_perfil = st.columns([1, 2])

    with col_lista:
        st.markdown("### Seleccionar legislador")
        nombres = df_filtrado['nombre_completo'].tolist()
        seleccionado = st.selectbox("", nombres, label_visibility="collapsed", key="leg_sel")
        
        st.caption(f"Mostrando {min(15, len(df_filtrado))} de {len(df_filtrado)}")
        st.dataframe(
            df_filtrado.head(15)[['nombre_completo', 'bloque', 'camara']].rename(columns={
                'nombre_completo': 'Nombre', 'bloque': 'Bloque', 'camara': 'Cámara'
            }),
            use_container_width=True,
            hide_index=True,
            height=400
        )

    with col_perfil:
        row = df_filtrado[df_filtrado['nombre_completo'] == seleccionado].iloc[0]
        leg_id = int(row['id'])
        
        st.markdown(f"### {seleccionado}")
        
        col_p1, col_p2, col_p3, col_p4 = st.columns(4)
        col_p1.markdown(f"**Bloque**<br>{row['bloque']}", unsafe_allow_html=True)
        col_p2.markdown(f"**Distrito**<br>{row['distrito']}", unsafe_allow_html=True)
        col_p3.markdown(f"**Cámara**<br>{row['camara']}", unsafe_allow_html=True)
        col_p4.markdown(f"**Votos**<br>{int(row['total_votos']):,}", unsafe_allow_html=True)
        
        # Tabs del perfil
        tabs = st.tabs(["📊 Votaciones", "📋 Proyectos", "💰 Patrimonio", "🤝 Afinidades"])
        
        with tabs[0]:
            df_votos = cargar_votos_legislador(leg_id)
            
            if df_votos.empty:
                st.info("No hay votos registrados.")
            else:
                col_v1, col_v2 = st.columns([1, 2])
                
                with col_v1:
                    dist = df_votos['voto_individual'].value_counts().reset_index()
                    dist.columns = ['Tipo', 'Cantidad']
                    st.markdown("**Distribución**")
                    
                    for _, r in dist.iterrows():
                        tipo = r['Tipo']
                        cant = r['Cantidad']
                        pct = cant / len(df_votos) * 100
                        color = '#059669' if tipo == 'AFIRMATIVO' else '#DC2626' if tipo == 'NEGATIVO' else '#D97706'
                        
                        st.markdown(f"""
                        <div style="margin-bottom: 0.5rem;">
                            <span style="color: {color}; font-weight: 600;">{tipo}</span><br>
                            <span style="font-size: 1.3rem; font-weight: 700;">{cant:,}</span>
                            <span style="color: #9CA3AF;"> ({pct:.0f}%)</span>
                        </div>
                        """, unsafe_allow_html=True)
                
                with col_v2:
                    st.markdown("**Evolución temporal**")
                    df_fecha = df_votos.dropna(subset=['fecha']).copy()
                    if not df_fecha.empty:
                        df_fecha['fecha'] = pd.to_datetime(df_fecha['fecha'])
                        df_fecha['año'] = df_fecha['fecha'].dt.year
                        evolucion = df_fecha.groupby(['año', 'voto_individual']).size().unstack(fill_value=0)
                        st.bar_chart(evolucion)
                
                st.markdown("**Últimas votaciones**")
                df_con_fecha = df_votos.dropna(subset=['fecha']).head(10)
                if not df_con_fecha.empty:
                    st.dataframe(
                        df_con_fecha[['fecha', 'voto_individual', 'titulo_acta']].rename(columns={
                            'fecha': 'Fecha', 'voto_individual': 'Voto', 'titulo_acta': 'Asunto'
                        }),
                        use_container_width=True, hide_index=True
                    )
        
        with tabs[1]:
            df_proyectos = cargar_proyectos_legislador(seleccionado)
            
            if df_proyectos.empty:
                st.info("No se encontraron proyectos.")
            else:
                st.markdown(f"**{len(df_proyectos)} proyectos encontrados**")
                st.dataframe(
                    df_proyectos.rename(columns={
                        'nro_expediente': 'Expediente', 'titulo': 'Título',
                        'fecha_ingreso': 'Fecha', 'estado': 'Tipo'
                    }),
                    use_container_width=True, hide_index=True
                )
        
        with tabs[2]:
            df_ddjj = cargar_ddjj_legislador(leg_id)
            
            if df_ddjj.empty:
                st.info("No hay declaración jurada cargada.")
            else:
                for _, r in df_ddjj.iterrows():
                    patrimonio = float(r['patrimonio_neto'] or 0)
                    bienes = float(r['total_bienes'] or 0)
                    deudas = float(r['total_deudas'] or 0)
                    ingresos = float(r['ingresos_neto_gastos'] or 0)
                    proveedor = r['proveedor_contratista']
                    cuit = r['cuit']
                    
                    st.markdown(f"""
                    <div class="lobby-card">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 0.8rem;">
                            <span class="lobby-card-title">DDJJ {int(r['anio'])}</span>
                            <span class="lobby-card-meta">CUIT: {cuit}</span>
                        </div>
                        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem;">
                            <div>
                                <div style="font-size: 0.75rem; color: #6B7280;">PATRIMONIO</div>
                                <div style="font-size: 1.2rem; font-weight: 700; color: #0F2240;">{fmt_pesos(patrimonio)}</div>
                            </div>
                            <div>
                                <div style="font-size: 0.75rem; color: #6B7280;">BIENES</div>
                                <div style="font-weight: 600;">{fmt_pesos(bienes)}</div>
                            </div>
                            <div>
                                <div style="font-size: 0.75rem; color: #6B7280;">DEUDAS</div>
                                <div style="font-weight: 600; color: #DC2626;">{fmt_pesos(deudas)}</div>
                            </div>
                            <div>
                                <div style="font-size: 0.75rem; color: #6B7280;">INGRESOS</div>
                                <div style="font-weight: 600;">{fmt_pesos(ingresos)}</div>
                            </div>
                        </div>
                        {"<div style='margin-top: 0.8rem;'><span class='lobby-badge lobby-badge-yellow'>Proveedor del Estado</span></div>" if proveedor == 'SI' else ""}
                    </div>
                    """, unsafe_allow_html=True)
        
        with tabs[3]:
            col_af1, col_af2 = st.columns(2)
            
            with col_af1:
                st.markdown("**Vota más igual con...**")
                df_afin = calcular_afinidad(leg_id)
                
                if df_afin.empty:
                    st.info("Sin datos suficientes.")
                else:
                    for i, (_, r) in enumerate(df_afin.iterrows(), 1):
                        st.markdown(f"""
                        <div class="ranking-item" style="border-left-color: #059669;">
                            <div class="ranking-position">{i}</div>
                            <div class="ranking-content">
                                <div class="ranking-name">{r['nombre_completo']}</div>
                                <div class="ranking-meta">{r['bloque']}</div>
                            </div>
                            <div class="ranking-value" style="color: #059669">{r['afinidad_pct']}%</div>
                        </div>
                        """, unsafe_allow_html=True)
            
            with col_af2:
                st.markdown("**Vota más distinto con...**")
                df_div = calcular_divergencia(leg_id)
                
                if df_div.empty:
                    st.info("Sin datos suficientes.")
                else:
                    for i, (_, r) in enumerate(df_div.iterrows(), 1):
                        st.markdown(f"""
                        <div class="ranking-item" style="border-left-color: #DC2626;">
                            <div class="ranking-position">{i}</div>
                            <div class="ranking-content">
                                <div class="ranking-name">{r['nombre_completo']}</div>
                                <div class="ranking-meta">{r['bloque']}</div>
                            </div>
                            <div class="ranking-value" style="color: #DC2626">{r['afinidad_pct']}%</div>
                        </div>
                        """, unsafe_allow_html=True)
