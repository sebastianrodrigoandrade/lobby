"""
Lobby - Página de Legisladores
Actualizado para usar votos_hcdn (2020-2026)
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
               COALESCE((SELECT COUNT(*) FROM votos_hcdn vh WHERE vh.legislador_id = l.id), 0) +
               COALESCE((SELECT COUNT(*) FROM votos v WHERE v.legislador_id = l.id), 0) as total_votos
        FROM legisladores l
        {where}
        ORDER BY l.nombre_completo
    """))
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df

@st.cache_data(ttl=3600)
def cargar_votos_legislador(legislador_id):
    db = SessionLocal()
    result = db.execute(text("""
        SELECT vh.voto as voto_individual, vh.acta_id, va.fecha,
               va.asunto as titulo_acta, va.resultado as resultado_general
        FROM votos_hcdn vh
        LEFT JOIN votaciones_hcdn va ON va.acta_id = vh.acta_id
        WHERE vh.legislador_id = :id
        UNION ALL
        SELECT v.voto_individual, v.acta_id,
               a.fecha, a.titulo as titulo_acta, a.resultado as resultado_general
        FROM votos v
        LEFT JOIN actas_cabecera a ON a.acta_id = v.acta_id
        WHERE v.legislador_id = :id
        ORDER BY fecha DESC NULLS LAST
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
        WHERE legislador_id = :id AND patrimonio_neto IS NOT NULL
        ORDER BY anio DESC
    """), {"id": legislador_id})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df

@st.cache_data(ttl=3600)
def calcular_afinidad(legislador_id, limit=5):
    db = SessionLocal()
    result = db.execute(text("""
        WITH mis_votos AS (
            SELECT acta_id, voto FROM votos_hcdn WHERE legislador_id = :id
        ),
        comparacion AS (
            SELECT
                v2.legislador_id,
                COUNT(*) as votos_comunes,
                SUM(CASE WHEN v1.voto = v2.voto THEN 1 ELSE 0 END) as votos_iguales
            FROM mis_votos v1
            JOIN votos_hcdn v2 ON v1.acta_id = v2.acta_id AND v2.legislador_id != :id
            GROUP BY v2.legislador_id
            HAVING COUNT(*) >= 10
        )
        SELECT l.nombre_completo, COALESCE(l.bloque, '—') as bloque,
               ROUND(100.0 * c.votos_iguales / c.votos_comunes, 1) as afinidad_pct
        FROM comparacion c
        JOIN legisladores l ON l.id = c.legislador_id
        ORDER BY afinidad_pct DESC
        LIMIT :limit
    """), {"id": legislador_id, "limit": limit})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df

@st.cache_data(ttl=3600)
def calcular_divergencia(legislador_id, limit=5):
    db = SessionLocal()
    result = db.execute(text("""
        WITH mis_votos AS (
            SELECT acta_id, voto FROM votos_hcdn WHERE legislador_id = :id
        ),
        comparacion AS (
            SELECT
                v2.legislador_id,
                COUNT(*) as votos_comunes,
                SUM(CASE WHEN v1.voto = v2.voto THEN 1 ELSE 0 END) as votos_iguales
            FROM mis_votos v1
            JOIN votos_hcdn v2 ON v1.acta_id = v2.acta_id AND v2.legislador_id != :id
            GROUP BY v2.legislador_id
            HAVING COUNT(*) >= 10
        )
        SELECT l.nombre_completo, COALESCE(l.bloque, '—') as bloque,
               ROUND(100.0 * c.votos_iguales / c.votos_comunes, 1) as afinidad_pct
        FROM comparacion c
        JOIN legisladores l ON l.id = c.legislador_id
        ORDER BY afinidad_pct ASC
        LIMIT :limit
    """), {"id": legislador_id, "limit": limit})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df

# Colores por bloque (consistentes en toda la app)
COLORES_BLOQUE = {
    'LA LIBERTAD AVANZA': '#7C3AED',
    'PRO': '#FBBF24', 
    'UNION POR LA PATRIA': '#2563EB',
    'UNIÓN POR LA PATRIA': '#2563EB',
    'UCR': '#DC2626',
    'HACEMOS COALICION FEDERAL': '#F97316',
    'DEFAULT': '#6B7280'
}

def get_color_bloque(bloque):
    if not bloque:
        return COLORES_BLOQUE['DEFAULT']
    bloque_upper = bloque.upper()
    for key, color in COLORES_BLOQUE.items():
        if key in bloque_upper:
            return color
    return COLORES_BLOQUE['DEFAULT']

def render():
    st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
    st.title("Legisladores")
    st.markdown("<div class='page-subtitle'>Perfil completo: votaciones, patrimonio, proyectos y afinidades</div>", unsafe_allow_html=True)

    # ========================================
    # BUSCADOR PROMINENTE
    # ========================================
    
    busqueda = st.text_input(
        "🔍 Buscar legislador",
        placeholder="Escribí nombre o apellido...",
        key="busqueda_legislador"
    )

    # Filtros en una fila
    col_f1, col_f2, col_f3 = st.columns([1, 1, 2])
    with col_f1:
        camara = st.selectbox("Cámara", ["Todos", "Diputados", "Senadores"], key="filtro_camara")
    with col_f2:
        vigentes = st.checkbox("Solo mandatos vigentes", value=True, key="filtro_vigentes")

    # Cargar datos
    df_legisladores = cargar_legisladores(camara=camara, solo_vigentes=vigentes)

    # Aplicar búsqueda
    if busqueda:
        df_filtrado = df_legisladores[
            df_legisladores['nombre_completo'].str.contains(busqueda, case=False, na=False)
        ]
    else:
        df_filtrado = df_legisladores

    if df_filtrado.empty:
        st.warning("No se encontraron legisladores con esos criterios.")
        return

    # Métricas
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("Legisladores", len(df_filtrado))
    col_m2.metric("Bloques", df_filtrado['bloque'].nunique())
    col_m3.metric("Distritos", df_filtrado['distrito'].nunique())
    col_m4.metric("Votos registrados", f"{df_filtrado['total_votos'].sum():,}")

    st.markdown("---")

    # ========================================
    # SELECTOR DE LEGISLADOR (sin tabla redundante)
    # ========================================
    
    nombres = df_filtrado['nombre_completo'].tolist()
    
    # Mostrar cantidad de resultados
    if busqueda:
        st.success(f"✓ {len(nombres)} legisladores encontrados")
    
    seleccionado = st.selectbox(
        "Seleccionar legislador",
        nombres,
        key="leg_sel",
        help="Seleccioná un legislador para ver su perfil completo"
    )

    if not seleccionado:
        return

    # ========================================
    # PERFIL DEL LEGISLADOR
    # ========================================
    
    row = df_filtrado[df_filtrado['nombre_completo'] == seleccionado].iloc[0]
    leg_id = int(row['id'])
    color_bloque = get_color_bloque(row['bloque'])

    # Header del perfil
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {color_bloque}15, {color_bloque}05); 
                border-left: 4px solid {color_bloque}; 
                padding: 1.5rem; border-radius: 0 12px 12px 0; margin: 1rem 0;">
        <h2 style="margin: 0 0 0.5rem 0; color: #1F2937;">{seleccionado}</h2>
        <div style="display: flex; gap: 2rem; flex-wrap: wrap;">
            <div><span style="color: #6B7280;">Bloque:</span> <strong style="color: {color_bloque};">{row['bloque']}</strong></div>
            <div><span style="color: #6B7280;">Distrito:</span> <strong>{row['distrito']}</strong></div>
            <div><span style="color: #6B7280;">Cámara:</span> <strong>{row['camara']}</strong></div>
            <div><span style="color: #6B7280;">Votos registrados:</span> <strong>{int(row['total_votos']):,}</strong></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Tabs del perfil
    tabs = st.tabs(["📊 Votaciones", "📋 Proyectos", "💰 Patrimonio", "🤝 Afinidades"])

    # ========================================
    # TAB VOTACIONES
    # ========================================
    with tabs[0]:
        df_votos = cargar_votos_legislador(leg_id)

        if df_votos.empty:
            st.info("No hay votos registrados para este legislador.")
        else:
            col_v1, col_v2 = st.columns([1, 2])

            with col_v1:
                dist = df_votos['voto_individual'].value_counts().reset_index()
                dist.columns = ['Tipo', 'Cantidad']
                st.markdown("**Distribución de votos**")

                for _, r in dist.iterrows():
                    tipo = r['Tipo']
                    cant = r['Cantidad']
                    pct = cant / len(df_votos) * 100
                    
                    if tipo == 'AFIRMATIVO':
                        color = '#059669'
                    elif tipo == 'NEGATIVO':
                        color = '#DC2626'
                    elif tipo == 'AUSENTE':
                        color = '#9CA3AF'
                    else:
                        color = '#D97706'

                    st.markdown(f"""
                    <div style="margin-bottom: 0.8rem; padding: 0.5rem; background: {color}10; border-radius: 8px;">
                        <span style="color: {color}; font-weight: 600;">{tipo}</span><br>
                        <span style="font-size: 1.3rem; font-weight: 700;">{cant:,}</span>
                        <span style="color: #9CA3AF;"> ({pct:.0f}%)</span>
                    </div>
                    """, unsafe_allow_html=True)

            with col_v2:
                st.markdown("**Evolución temporal**")
                df_fecha = df_votos.dropna(subset=['fecha']).copy()
                if not df_fecha.empty:
                    df_fecha['fecha'] = pd.to_datetime(df_fecha['fecha'], errors='coerce')
                    df_fecha = df_fecha.dropna(subset=['fecha'])
                    if not df_fecha.empty:
                        df_fecha['año'] = df_fecha['fecha'].dt.year
                        evolucion = df_fecha.groupby(['año', 'voto_individual']).size().unstack(fill_value=0)
                        st.bar_chart(evolucion)

            st.markdown("**Últimas votaciones**")
            df_con_fecha = df_votos.dropna(subset=['fecha']).head(15)
            if not df_con_fecha.empty:
                st.dataframe(
                    df_con_fecha[['fecha', 'voto_individual', 'titulo_acta']].rename(columns={
                        'fecha': 'Fecha', 'voto_individual': 'Voto', 'titulo_acta': 'Asunto'
                    }),
                    use_container_width=True, 
                    hide_index=True
                )

    # ========================================
    # TAB PROYECTOS
    # ========================================
    with tabs[1]:
        df_proyectos = cargar_proyectos_legislador(seleccionado)

        if df_proyectos.empty:
            st.info("No se encontraron proyectos donde figure como autor.")
        else:
            st.markdown(f"**{len(df_proyectos)} proyectos encontrados**")
            st.dataframe(
                df_proyectos.rename(columns={
                    'nro_expediente': 'Expediente', 'titulo': 'Título',
                    'fecha_ingreso': 'Fecha', 'estado': 'Tipo'
                }),
                use_container_width=True, 
                hide_index=True
            )

    # ========================================
    # TAB PATRIMONIO
    # ========================================
    with tabs[2]:
        df_ddjj = cargar_ddjj_legislador(leg_id)

        if df_ddjj.empty:
            st.info("No hay declaraciones juradas cargadas para este legislador.")
        else:
            # Mostrar evolución si hay más de un año
            if len(df_ddjj) > 1:
                st.markdown("**Evolución patrimonial**")
                df_evol = df_ddjj[['anio', 'patrimonio_neto']].copy()
                df_evol = df_evol.set_index('anio').sort_index()
                st.line_chart(df_evol)

            st.markdown("**Detalle por año**")
            for _, r in df_ddjj.iterrows():
                patrimonio = float(r['patrimonio_neto'] or 0)
                bienes = float(r['total_bienes'] or 0)
                deudas = float(r['total_deudas'] or 0)
                ingresos = float(r['ingresos_neto_gastos'] or 0)
                proveedor = r['proveedor_contratista']
                cuit = r['cuit']

                st.markdown(f"""
                <div style="background: white; border: 1px solid #E5E7EB; border-radius: 12px; padding: 1.2rem; margin-bottom: 1rem;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 0.8rem;">
                        <span style="font-weight: 700; font-size: 1.1rem; color: #2563EB;">DDJJ {int(r['anio'])}</span>
                        <span style="color: #9CA3AF; font-size: 0.85rem;">CUIT: {cuit}</span>
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
                    {"<div style='margin-top: 0.8rem;'><span style='background: #FEF3C7; color: #92400E; padding: 0.25rem 0.75rem; border-radius: 999px; font-size: 0.8rem;'>⚠️ Proveedor del Estado</span></div>" if proveedor == 'SI' else ""}
                </div>
                """, unsafe_allow_html=True)

    # ========================================
    # TAB AFINIDADES
    # ========================================
    with tabs[3]:
        st.markdown("""
        <div style="background: #F0F9FF; border: 1px solid #BAE6FD; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
            <strong>¿Cómo se calcula?</strong><br>
            <span style="color: #0369A1; font-size: 0.9rem;">
            Se comparan todas las votaciones donde ambos legisladores participaron. 
            El porcentaje indica en cuántas votaron igual.
            </span>
        </div>
        """, unsafe_allow_html=True)

        col_af1, col_af2 = st.columns(2)

        with col_af1:
            st.markdown("**🤝 Vota más igual con...**")
            df_afin = calcular_afinidad(leg_id)

            if df_afin.empty:
                st.info("Sin datos suficientes (se necesitan al menos 10 votaciones en común).")
            else:
                for i, (_, r) in enumerate(df_afin.iterrows(), 1):
                    color = get_color_bloque(r['bloque'])
                    st.markdown(f"""
                    <div style="background: white; border-left: 4px solid #059669; padding: 0.8rem 1rem;
                                margin-bottom: 0.5rem; border-radius: 0 8px 8px 0; display: flex; align-items: center; gap: 1rem;">
                        <div style="font-size: 1.3rem; font-weight: 700; color: #9CA3AF; min-width: 1.5rem;">#{i}</div>
                        <div style="flex: 1;">
                            <div style="font-weight: 600; color: #1F2937;">{r['nombre_completo']}</div>
                            <div style="font-size: 0.8rem; color: {color};">{r['bloque']}</div>
                        </div>
                        <div style="font-size: 1.2rem; font-weight: 700; color: #059669;">{r['afinidad_pct']}%</div>
                    </div>
                    """, unsafe_allow_html=True)

        with col_af2:
            st.markdown("**⚔️ Vota más distinto con...**")
            df_div = calcular_divergencia(leg_id)

            if df_div.empty:
                st.info("Sin datos suficientes (se necesitan al menos 10 votaciones en común).")
            else:
                for i, (_, r) in enumerate(df_div.iterrows(), 1):
                    color = get_color_bloque(r['bloque'])
                    st.markdown(f"""
                    <div style="background: white; border-left: 4px solid #DC2626; padding: 0.8rem 1rem;
                                margin-bottom: 0.5rem; border-radius: 0 8px 8px 0; display: flex; align-items: center; gap: 1rem;">
                        <div style="font-size: 1.3rem; font-weight: 700; color: #9CA3AF; min-width: 1.5rem;">#{i}</div>
                        <div style="flex: 1;">
                            <div style="font-weight: 600; color: #1F2937;">{r['nombre_completo']}</div>
                            <div style="font-size: 0.8rem; color: {color};">{r['bloque']}</div>
                        </div>
                        <div style="font-size: 1.2rem; font-weight: 700; color: #DC2626;">{r['afinidad_pct']}%</div>
                    </div>
                    """, unsafe_allow_html=True)