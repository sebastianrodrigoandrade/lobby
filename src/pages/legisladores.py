# -*- coding: utf-8 -*-
"""
Lobby - Página de Legisladores
Perfil completo: votaciones, patrimonio, proyectos y afinidades
"""
import streamlit as st
import pandas as pd
import urllib.parse
from sqlalchemy import text
from src.database import SessionLocal

# ============================================
# CONSTANTES
# ============================================

ENCODING = {
    '¾': 'ó', 'ß': 'á', '±': 'ñ', 'Ý': 'í', '┴': 'Á',
    '═': 'Í', 'Ë': 'Ó', 'Ð': 'Ñ', 'â': 'â',
}

COLORES_BLOQUE = {
    'LA LIBERTAD AVANZA': '#7C3AED',
    'PRO': '#FBBF24', 
    'UNION POR LA PATRIA': '#2563EB',
    'UNIÓN POR LA PATRIA': '#2563EB',
    'UCR': '#DC2626',
    'HACEMOS COALICION FEDERAL': '#F97316',
    'DEFAULT': '#6B7280'
}

# ============================================
# FUNCIONES AUXILIARES
# ============================================

def limpiar(texto):
    if not texto:
        return ''
    for mal, bien in ENCODING.items():
        texto = texto.replace(mal, bien)
    return texto

def get_color_bloque(bloque):
    if not bloque:
        return COLORES_BLOQUE['DEFAULT']
    bloque_upper = bloque.upper()
    for key, color in COLORES_BLOQUE.items():
        if key in bloque_upper:
            return color
    return COLORES_BLOQUE['DEFAULT']

def fmt_pesos(valor):
    if pd.isna(valor) or valor is None:
        return "-"
    valor = float(valor)
    if valor >= 1_000_000_000:
        return f"${valor/1_000_000_000:,.1f}B"
    if valor >= 1_000_000:
        return f"${valor/1_000_000:,.0f}M"
    return f"${valor:,.0f}"

def generar_tweet(texto):
    return f"https://twitter.com/intent/tweet?{urllib.parse.urlencode({'text': texto})}"

# ============================================
# FUNCIONES DE CARGA
# ============================================

@st.cache_data(ttl=3600)
def cargar_legisladores(camara=None, solo_vigentes=True):
    db = SessionLocal()
    try:
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
        return pd.DataFrame(result.fetchall(), columns=result.keys())
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_legislador_por_id(legislador_id):
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT l.id, l.nombre_completo, l.camara,
                   COALESCE(l.bloque, '—') as bloque,
                   COALESCE(l.distrito, '—') as distrito,
                   l.mandato_hasta,
                   COALESCE((SELECT COUNT(*) FROM votos_hcdn vh WHERE vh.legislador_id = l.id), 0) +
                   COALESCE((SELECT COUNT(*) FROM votos v WHERE v.legislador_id = l.id), 0) as total_votos
            FROM legisladores l
            WHERE l.id = :id
        """), {"id": legislador_id})
        row = result.fetchone()
        if row:
            return dict(zip(result.keys(), row))
        return None
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_votos_legislador(legislador_id):
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT vh.voto as voto_individual, vh.acta_id,
                   TO_DATE(va.fecha, 'DD/MM/YYYY') as fecha,
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
        df['titulo_acta'] = df['titulo_acta'].apply(limpiar)
        return df
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_proyectos_legislador(nombre):
    db = SessionLocal()
    try:
        apellido = nombre.split(',')[0] if ',' in nombre else nombre.split()[0]
        result = db.execute(text("""
            SELECT nro_expediente, titulo, fecha_ingreso, estado
            FROM proyectos
            WHERE autores ILIKE :nombre
            ORDER BY fecha_ingreso DESC NULLS LAST
            LIMIT 50
        """), {"nombre": f"%{apellido}%"})
        return pd.DataFrame(result.fetchall(), columns=result.keys())
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_ddjj_legislador(legislador_id):
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT anio, patrimonio_neto, total_bienes, total_deudas,
                   ingresos_neto_gastos, proveedor_contratista, cuit
            FROM ddjj_legisladores
            WHERE legislador_id = :id AND patrimonio_neto IS NOT NULL AND patrimonio_neto > 0
            ORDER BY anio DESC
        """), {"id": legislador_id})
        return pd.DataFrame(result.fetchall(), columns=result.keys())
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_mediana_y_ranking(legislador_id, anio=2024):
    """Obtiene la mediana general y el ranking del legislador."""
    db = SessionLocal()
    try:
        # Mediana general
        result = db.execute(text("""
            SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY patrimonio_neto) as mediana
            FROM ddjj_legisladores
            WHERE patrimonio_neto > 0 AND anio = :anio
        """), {"anio": anio})
        mediana = float(result.scalar() or 0)
        
        # Ranking del legislador
        result = db.execute(text("""
            WITH ranked AS (
                SELECT legislador_id, patrimonio_neto,
                       ROW_NUMBER() OVER (ORDER BY patrimonio_neto DESC) as rank,
                       COUNT(*) OVER () as total
                FROM ddjj_legisladores
                WHERE patrimonio_neto > 0 AND anio = :anio AND legislador_id IS NOT NULL
            )
            SELECT rank, total FROM ranked WHERE legislador_id = :leg_id
        """), {"anio": anio, "leg_id": legislador_id})
        row = result.fetchone()
        rank = int(row[0]) if row else None
        total = int(row[1]) if row else None
        
        return {"mediana": mediana, "rank": rank, "total": total}
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_variacion_patrimonial(legislador_id):
    """Calcula variación patrimonial con ajuste por inflación."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            WITH datos AS (
                SELECT 
                    MAX(CASE WHEN anio = 2022 THEN patrimonio_neto END) as pat_2022,
                    MAX(CASE WHEN anio = 2024 THEN patrimonio_neto END) as pat_2024
                FROM ddjj_legisladores
                WHERE legislador_id = :id AND patrimonio_neto > 0
            ),
            inflacion AS (
                SELECT 
                    (SELECT ipc_acumulado FROM indicadores_anuales WHERE anio = 2024) /
                    (SELECT ipc_acumulado FROM indicadores_anuales WHERE anio = 2022) as ratio_ipc
            )
            SELECT 
                d.pat_2022, d.pat_2024,
                CASE WHEN d.pat_2022 > 0 THEN ((d.pat_2024 / d.pat_2022) - 1) * 100 END as var_nominal,
                CASE WHEN d.pat_2022 > 0 THEN (((d.pat_2024 / d.pat_2022) / i.ratio_ipc) - 1) * 100 END as var_real
            FROM datos d, inflacion i
        """), {"id": legislador_id})
        row = result.fetchone()
        if row and row[0] and row[1]:
            return {
                "pat_2022": float(row[0]),
                "pat_2024": float(row[1]),
                "var_nominal": float(row[2]) if row[2] else None,
                "var_real": float(row[3]) if row[3] else None
            }
        return None
    finally:
        db.close()

@st.cache_data(ttl=3600)
def calcular_afinidad(legislador_id, limit=5):
    db = SessionLocal()
    try:
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
        return pd.DataFrame(result.fetchall(), columns=result.keys())
    finally:
        db.close()

@st.cache_data(ttl=3600)
def calcular_divergencia(legislador_id, limit=5):
    db = SessionLocal()
    try:
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
        return pd.DataFrame(result.fetchall(), columns=result.keys())
    finally:
        db.close()

# ============================================
# RENDER
# ============================================

def render():
    st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
    st.title("Legisladores")
    st.markdown("<div class='page-subtitle'>Perfil completo: votaciones, patrimonio, proyectos y afinidades</div>", unsafe_allow_html=True)

    # ========================================
    # VERIFICAR SI VIENE DE HOME CON SELECCIÓN
    # ========================================
    
    legislador_preseleccionado = None
    if 'legislador_seleccionado' in st.session_state:
        leg_id = st.session_state['legislador_seleccionado']
        legislador_preseleccionado = cargar_legislador_por_id(leg_id)
        del st.session_state['legislador_seleccionado']

    # ========================================
    # BUSCADOR
    # ========================================

    busqueda = st.text_input(
        "Buscar legislador",
        placeholder="Escribi nombre o apellido...",
        key="busqueda_legislador"
    )

    col_f1, col_f2 = st.columns([1, 1])
    with col_f1:
        camara = st.selectbox("Camara", ["Todos", "Diputados", "Senadores"], key="filtro_camara")
    with col_f2:
        vigentes = st.checkbox("Solo mandatos vigentes", value=True, key="filtro_vigentes")

    # Cargar datos
    df_legisladores = cargar_legisladores(camara=camara, solo_vigentes=vigentes)

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
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Legisladores", len(df_filtrado))
    col_m2.metric("Bloques", df_filtrado['bloque'].nunique())
    col_m3.metric("Votos registrados", f"{df_filtrado['total_votos'].sum():,}")

    st.markdown("---")

    # ========================================
    # SELECTOR
    # ========================================

    nombres = df_filtrado['nombre_completo'].tolist()
    
    # Si viene preseleccionado, buscar índice
    default_index = 0
    if legislador_preseleccionado:
        nombre_pre = legislador_preseleccionado['nombre_completo']
        if nombre_pre in nombres:
            default_index = nombres.index(nombre_pre)

    seleccionado = st.selectbox(
        "Seleccionar legislador",
        nombres,
        index=default_index,
        key="leg_sel"
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
            <div><span style="color: #6B7280;">Camara:</span> <strong>{row['camara']}</strong></div>
            <div><span style="color: #6B7280;">Votos:</span> <strong>{int(row['total_votos']):,}</strong></div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Botón compartir
    tweet = f"{seleccionado} ({row['bloque']}, {row['camara']}). Mira su perfil completo en Lobby: votaciones, patrimonio y mas."
    st.link_button("Compartir en X", generar_tweet(tweet), use_container_width=False)

    # Tabs
    tabs = st.tabs(["Votaciones", "Patrimonio", "Proyectos", "Afinidades"])

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
                st.markdown("**Distribucion de votos**")

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
                    <div style="margin-bottom: 0.5rem; padding: 0.5rem; background: {color}10; border-radius: 8px;">
                        <span style="color: {color}; font-weight: 600;">{tipo}</span>
                        <span style="float: right; font-weight: 700;">{cant:,} <span style="color: #9CA3AF; font-weight: normal;">({pct:.0f}%)</span></span>
                    </div>
                    """, unsafe_allow_html=True)

            with col_v2:
                st.markdown("**Evolucion temporal**")
                df_fecha = df_votos.dropna(subset=['fecha']).copy()
                if not df_fecha.empty:
                    df_fecha['fecha'] = pd.to_datetime(df_fecha['fecha'], errors='coerce')
                    df_fecha = df_fecha.dropna(subset=['fecha'])
                    if not df_fecha.empty:
                        df_fecha['año'] = df_fecha['fecha'].dt.year
                        evolucion = df_fecha.groupby(['año', 'voto_individual']).size().unstack(fill_value=0)
                        st.bar_chart(evolucion)

            st.markdown("**Ultimas votaciones**")
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
    # TAB PATRIMONIO
    # ========================================
    with tabs[1]:
        df_ddjj = cargar_ddjj_legislador(leg_id)

        if df_ddjj.empty:
            st.info("No hay declaraciones juradas cargadas para este legislador.")
        else:
            # Variación y ranking
            variacion = cargar_variacion_patrimonial(leg_id)
            ranking = cargar_mediana_y_ranking(leg_id, 2024)
            
            # Resumen destacado
            ultimo_pat = float(df_ddjj.iloc[0]['patrimonio_neto'])
            veces_mediana = ultimo_pat / ranking['mediana'] if ranking['mediana'] > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            col1.metric(
                "Patrimonio 2024", 
                fmt_pesos(ultimo_pat),
                help="Ultimo patrimonio declarado"
            )
            col2.metric(
                "vs Mediana",
                f"{veces_mediana:.1f}x",
                help=f"La mediana de legisladores es {fmt_pesos(ranking['mediana'])}"
            )
            if ranking['rank']:
                col3.metric(
                    "Ranking",
                    f"#{ranking['rank']} de {ranking['total']}",
                    help="Posicion entre todos los legisladores con DDJJ"
                )
            
            # Variación real si hay datos
            if variacion:
                st.markdown("---")
                st.markdown("**Variacion 2022-2024** (inflacion acumulada: 493%)")
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Patrimonio 2022", fmt_pesos(variacion['pat_2022']))
                col2.metric("Patrimonio 2024", fmt_pesos(variacion['pat_2024']))
                
                if variacion['var_real'] is not None:
                    color_var = "#059669" if variacion['var_real'] > 0 else "#DC2626"
                    col3.markdown(f"""
                    <div style="background: {color_var}10; padding: 0.8rem; border-radius: 8px; text-align: center;">
                        <div style="font-size: 0.8rem; color: #6B7280;">Variacion real</div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: {color_var};">{variacion['var_real']:+.1f}%</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Detalle por año
            st.markdown("**Detalle por anio**")
            for _, r in df_ddjj.iterrows():
                patrimonio = float(r['patrimonio_neto'] or 0)
                bienes = float(r['total_bienes'] or 0)
                deudas = float(r['total_deudas'] or 0)
                proveedor = r['proveedor_contratista']

                st.markdown(f"""
                <div style="background: white; border: 1px solid #E5E7EB; border-radius: 12px; padding: 1rem; margin-bottom: 0.8rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                        <span style="font-weight: 700; font-size: 1.1rem; color: #2563EB;">DDJJ {int(r['anio'])}</span>
                        {"<span style='background: #FEF3C7; color: #92400E; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.8rem;'>Proveedor del Estado</span>" if proveedor == 'SI' else ""}
                    </div>
                    <div style="display: flex; gap: 2rem; flex-wrap: wrap;">
                        <div>
                            <span style="font-size: 0.75rem; color: #6B7280;">PATRIMONIO</span><br>
                            <span style="font-size: 1.1rem; font-weight: 700;">{fmt_pesos(patrimonio)}</span>
                        </div>
                        <div>
                            <span style="font-size: 0.75rem; color: #6B7280;">BIENES</span><br>
                            <span style="font-weight: 600;">{fmt_pesos(bienes)}</span>
                        </div>
                        <div>
                            <span style="font-size: 0.75rem; color: #6B7280;">DEUDAS</span><br>
                            <span style="font-weight: 600; color: #DC2626;">{fmt_pesos(deudas)}</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # ========================================
    # TAB PROYECTOS
    # ========================================
    with tabs[2]:
        df_proyectos = cargar_proyectos_legislador(seleccionado)

        if df_proyectos.empty:
            st.info("No se encontraron proyectos donde figure como autor.")
        else:
            st.markdown(f"**{len(df_proyectos)} proyectos encontrados**")
            st.dataframe(
                df_proyectos.rename(columns={
                    'nro_expediente': 'Expediente', 'titulo': 'Titulo',
                    'fecha_ingreso': 'Fecha', 'estado': 'Tipo'
                }),
                use_container_width=True,
                hide_index=True
            )

    # ========================================
    # TAB AFINIDADES
    # ========================================
    with tabs[3]:
        st.markdown("""
        <div style="background: #F0F9FF; border: 1px solid #BAE6FD; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
            <strong>Como se calcula?</strong>
            <span style="color: #0369A1; font-size: 0.9rem;">
            Se comparan todas las votaciones donde ambos legisladores participaron. 
            El porcentaje indica en cuantas votaron igual.
            </span>
        </div>
        """, unsafe_allow_html=True)
        
        col_af1, col_af2 = st.columns(2)
        
        with col_af1:
            st.markdown("**Vota mas igual con...**")
            df_afin = calcular_afinidad(leg_id)
            if df_afin.empty:
                st.info("Sin datos suficientes.")
            else:
                for i, (_, r) in enumerate(df_afin.iterrows(), 1):
                    color = get_color_bloque(r['bloque'])
                    st.markdown(f"""
                    <div style="background: white; border-left: 4px solid #059669; padding: 0.6rem 1rem;
                                margin-bottom: 0.4rem; border-radius: 0 8px 8px 0;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <span style="font-weight: 600;">{r['nombre_completo']}</span>
                                <span style="font-size: 0.8rem; color: {color};"> · {r['bloque']}</span>
                            </div>
                            <span style="font-weight: 700; color: #059669;">{r['afinidad_pct']}%</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        
        with col_af2:
            st.markdown("**Vota mas distinto con...**")
            df_div = calcular_divergencia(leg_id)
            if df_div.empty:
                st.info("Sin datos suficientes.")
            else:
                for i, (_, r) in enumerate(df_div.iterrows(), 1):
                    color = get_color_bloque(r['bloque'])
                    st.markdown(f"""
                    <div style="background: white; border-left: 4px solid #DC2626; padding: 0.6rem 1rem;
                                margin-bottom: 0.4rem; border-radius: 0 8px 8px 0;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <span style="font-weight: 600;">{r['nombre_completo']}</span>
                                <span style="font-size: 0.8rem; color: {color};"> · {r['bloque']}</span>
                            </div>
                            <span style="font-weight: 700; color: #DC2626;">{r['afinidad_pct']}%</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)