# -*- coding: utf-8 -*-
"""
Lobby - Página de Legisladores
Perfil completo: votaciones, patrimonio, bienes, proyectos y afinidades
"""
import streamlit as st
import pandas as pd
import urllib.parse
import plotly.graph_objects as go
from sqlalchemy import text
from src.database import SessionLocal
from src import tarjetas

# Paleta unificada para tipos de voto (usar tanto en Distribución como en Evolución temporal)
COLOR_VOTOS = {
    'AFIRMATIVO': '#059669',
    'NEGATIVO': '#DC2626',
    'AUSENTE': '#9CA3AF',
    'ABSTENCION': '#D97706',
    'ABSTENCIÓN': '#D97706',
    'PRESIDENTE': '#6B7280',
}


def _color_voto(tipo: str) -> str:
    return COLOR_VOTOS.get((tipo or '').upper(), '#D97706')

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
                   l.mandato_hasta, l.foto_url,
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
                   l.mandato_hasta, l.foto_url,
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
def cargar_bienes_legislador(legislador_id):
    """Carga bienes detallados del legislador."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT bien_tipo, bien_descripcion, bien_importe, anio
            FROM ddjj_bienes b
            WHERE legislador_id = :id
            ORDER BY b.bien_importe DESC NULLS LAST
        """), {"id": legislador_id})
        return pd.DataFrame(result.fetchall(), columns=['tipo', 'descripcion', 'importe', 'anio'])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_comisiones_legislador(legislador_id):
    """Carga comisiones a las que pertenece el legislador."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT c.nombre, ci.cargo
            FROM comision_integrantes ci
            JOIN comisiones c ON c.id = ci.comision_id
            WHERE ci.legislador_id = :id
            ORDER BY 
                CASE ci.cargo 
                    WHEN 'PRESIDENTE' THEN 1 
                    WHEN 'VICEPRESIDENTE 1ª' THEN 2
                    WHEN 'VICEPRESIDENTE 2ª' THEN 3
                    WHEN 'SECRETARIO' THEN 4
                    ELSE 5 
                END
        """), {"id": legislador_id})
        return pd.DataFrame(result.fetchall(), columns=['comision', 'cargo'])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_intervenciones_legislador(legislador_id: int) -> dict:
    """
    Devuelve un resumen de las intervenciones en el recinto para este
    legislador: total, palabras, última fecha, preview.
    Si la tabla `intervenciones_recinto` no existe o no tiene datos
    devuelve un dict con ceros (no rompe la UI).
    """
    db = SessionLocal()
    out = {
        "total": 0, "palabras": 0, "ultima_fecha": None,
        "ultima_preview": None, "promedio_palabras": 0,
    }
    try:
        r = db.execute(text("""
            SELECT
                COUNT(*)                         AS total,
                COALESCE(SUM(palabras), 0)       AS palabras,
                MAX(fecha)                       AS ultima_fecha,
                COALESCE(AVG(palabras), 0)::int  AS promedio
            FROM intervenciones_recinto
            WHERE legislador_id = :id
        """), {"id": legislador_id}).fetchone()
        if r:
            out["total"] = int(r[0] or 0)
            out["palabras"] = int(r[1] or 0)
            out["ultima_fecha"] = r[2]
            out["promedio_palabras"] = int(r[3] or 0)
        if out["total"] > 0:
            preview = db.execute(text("""
                SELECT LEFT(texto, 180)
                FROM intervenciones_recinto
                WHERE legislador_id = :id
                ORDER BY fecha DESC, orden_intervencion DESC
                LIMIT 1
            """), {"id": legislador_id}).scalar()
            out["ultima_preview"] = preview
    except Exception:
        db.rollback()
    finally:
        db.close()
    return out


@st.cache_data(ttl=3600)
def cargar_stats_tarjeta(legislador_id: int, nombre_completo: str) -> dict:
    """
    Devuelve stats compactos para la tarjeta compartible:
    proyectos firmados, % de asistencia, último patrimonio declarado, menciones CIJ.
    Todas las queries son tolerantes a tablas faltantes.
    """
    db = SessionLocal()
    out = {"proyectos": 0, "asistencia_pct": None, "patrimonio_total": None, "menciones_cij": 0}
    try:
        try:
            r = db.execute(text("""
                SELECT COUNT(*) FROM proyectos_legisladores WHERE legislador_id = :id
            """), {"id": legislador_id}).scalar()
            out["proyectos"] = int(r or 0)
        except Exception:
            db.rollback()

        try:
            r = db.execute(text("""
                SELECT COUNT(*) FILTER (WHERE voto != 'AUSENTE')::float / NULLIF(COUNT(*), 0) * 100
                FROM votos_hcdn WHERE legislador_id = :id
            """), {"id": legislador_id}).scalar()
            out["asistencia_pct"] = float(r) if r is not None else None
        except Exception:
            db.rollback()

        try:
            r = db.execute(text("""
                SELECT patrimonio_neto FROM ddjj_legisladores
                WHERE legislador_id = :id AND patrimonio_neto IS NOT NULL
                ORDER BY anio DESC LIMIT 1
            """), {"id": legislador_id}).scalar()
            out["patrimonio_total"] = float(r) if r is not None else None
        except Exception:
            db.rollback()

        try:
            r = db.execute(text("""
                SELECT COUNT(*) FROM menciones_cij
                WHERE legislador_nombre ILIKE :nombre
            """), {"nombre": f"%{nombre_completo}%"}).scalar()
            out["menciones_cij"] = int(r or 0)
        except Exception:
            db.rollback()

        return out
    finally:
        db.close()


@st.cache_data(ttl=3600)
def cargar_mediana_y_ranking(legislador_id, anio=2024):
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY patrimonio_neto) as mediana
            FROM ddjj_legisladores
            WHERE patrimonio_neto > 0 AND anio = :anio
        """), {"anio": anio})
        mediana = float(result.scalar() or 0)
        
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

def _filtro_leyes_sql(solo_leyes: bool) -> str:
    """Devuelve el subfiltro SQL que restringe a actas cuyo asunto sea un proyecto de ley."""
    if not solo_leyes:
        return ""
    return (
        " AND EXISTS ("
        "   SELECT 1 FROM votaciones_hcdn vh "
        "   WHERE vh.acta_id = v.acta_id "
        "     AND (vh.asunto ILIKE '%proyecto de ley%' OR vh.asunto ILIKE '%ley %' OR vh.asunto ILIKE '% ley')"
        " )"
    )

@st.cache_data(ttl=3600)
def calcular_afinidad(legislador_id, limit=5, solo_leyes=False):
    db = SessionLocal()
    try:
        filtro_leyes = _filtro_leyes_sql(solo_leyes)
        query = f"""
            WITH mis_votos AS (
                SELECT v.acta_id, v.voto
                FROM votos_hcdn v
                WHERE v.legislador_id = :id
                {filtro_leyes}
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
                   ROUND(100.0 * c.votos_iguales / c.votos_comunes, 1) as afinidad_pct,
                   c.votos_comunes
            FROM comparacion c
            JOIN legisladores l ON l.id = c.legislador_id
            ORDER BY afinidad_pct DESC
            LIMIT :limit
        """
        result = db.execute(text(query), {"id": legislador_id, "limit": limit})
        return pd.DataFrame(result.fetchall(), columns=result.keys())
    finally:
        db.close()

@st.cache_data(ttl=3600)
def calcular_divergencia(legislador_id, limit=5, solo_leyes=False):
    db = SessionLocal()
    try:
        filtro_leyes = _filtro_leyes_sql(solo_leyes)
        query = f"""
            WITH mis_votos AS (
                SELECT v.acta_id, v.voto
                FROM votos_hcdn v
                WHERE v.legislador_id = :id
                {filtro_leyes}
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
                   ROUND(100.0 * c.votos_iguales / c.votos_comunes, 1) as afinidad_pct,
                   c.votos_comunes
            FROM comparacion c
            JOIN legisladores l ON l.id = c.legislador_id
            ORDER BY afinidad_pct ASC
            LIMIT :limit
        """
        result = db.execute(text(query), {"id": legislador_id, "limit": limit})
        return pd.DataFrame(result.fetchall(), columns=result.keys())
    finally:
        db.close()

# ============================================
# RENDER
# ============================================

def render():
    st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
    st.title("Legisladores")
    st.markdown("<div class='page-subtitle'>Perfil completo: votaciones, patrimonio, bienes, proyectos y afinidades</div>", unsafe_allow_html=True)

    # Verificar si viene de home con selección
    legislador_preseleccionado = None
    if 'legislador_seleccionado' in st.session_state:
        leg_id = st.session_state['legislador_seleccionado']
        legislador_preseleccionado = cargar_legislador_por_id(leg_id)
        del st.session_state['legislador_seleccionado']

    # Buscador
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

    # Selector
    nombres = df_filtrado['nombre_completo'].tolist()
    
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
    foto_url = row['foto_url'] if pd.notna(row.get('foto_url')) else None

    # Header del perfil con foto
    if foto_url:
        foto_html = f'<img src="{foto_url}" style="width: 100px; height: 100px; border-radius: 50%; object-fit: cover; border: 4px solid {color_bloque};">'
    else:
        foto_html = f'<div style="width: 100px; height: 100px; border-radius: 50%; background: {color_bloque}20; display: flex; align-items: center; justify-content: center; color: {color_bloque}; font-weight: 700; font-size: 2.5rem; border: 4px solid {color_bloque};">{seleccionado[0]}</div>'

    st.markdown(f"""
    <div style="background: linear-gradient(135deg, {color_bloque}15, {color_bloque}05);
                border-left: 4px solid {color_bloque};
                padding: 1.5rem; border-radius: 0 12px 12px 0; margin: 1rem 0;">
        <div style="display: flex; gap: 1.5rem; align-items: center; flex-wrap: wrap;">
            {foto_html}
            <div>
                <h2 style="margin: 0 0 0.5rem 0; color: #1F2937;">{seleccionado}</h2>
                <div style="display: flex; gap: 1.5rem; flex-wrap: wrap;">
                    <div><span style="color: #6B7280;">Bloque:</span> <strong style="color: {color_bloque};">{row['bloque']}</strong></div>
                    <div><span style="color: #6B7280;">Distrito:</span> <strong>{row['distrito']}</strong></div>
                    <div><span style="color: #6B7280;">Camara:</span> <strong>{row['camara']}</strong></div>
                    <div><span style="color: #6B7280;">Votos:</span> <strong>{int(row['total_votos']):,}</strong></div>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Comisiones del legislador
    df_comisiones = cargar_comisiones_legislador(leg_id)
    if not df_comisiones.empty:
        comisiones_str = " · ".join([
            f"<strong>{r['cargo']}</strong> {r['comision']}" if r['cargo'] != 'VOCAL' else r['comision']
            for _, r in df_comisiones.iterrows()
        ])
        st.markdown(f"""
        <div style="background: #F3F4F6; padding: 0.8rem 1rem; border-radius: 8px; margin-bottom: 1rem; font-size: 0.9rem;">
            <span style="color: #6B7280;">Comisiones:</span> {comisiones_str}
        </div>
        """, unsafe_allow_html=True)
    
    # Intervenciones en el recinto (Diarios de Sesiones)
    _iv = cargar_intervenciones_legislador(leg_id)
    if _iv["total"] > 0:
        _ultima = _iv["ultima_fecha"].strftime("%d/%m/%Y") if _iv["ultima_fecha"] else "—"
        _preview_html = ""
        if _iv["ultima_preview"]:
            _prev_safe = (_iv["ultima_preview"] or "").replace("<", "&lt;").replace(">", "&gt;").replace("\n", " ")
            _preview_html = (
                f"<div style='margin-top: 0.5rem; font-style: italic; color: #4B5563; "
                f"font-size: 0.85rem; line-height: 1.4;'>"
                f"«{_prev_safe}…»</div>"
            )
        st.markdown(f"""
        <div style="background: #F0F9FF; border-left: 4px solid #0EA5E9; padding: 0.8rem 1rem;
                    border-radius: 8px; margin-bottom: 1rem; font-size: 0.9rem;">
            <div style="display: flex; gap: 2rem; flex-wrap: wrap; align-items: center;">
                <div><span style="color: #6B7280;">Intervenciones en el recinto:</span>
                     <strong>{_iv['total']:,}</strong></div>
                <div><span style="color: #6B7280;">Palabras pronunciadas:</span>
                     <strong>{_iv['palabras']:,}</strong></div>
                <div><span style="color: #6B7280;">Promedio por intervención:</span>
                     <strong>{_iv['promedio_palabras']:,}</strong> pal.</div>
                <div><span style="color: #6B7280;">Última:</span> <strong>{_ultima}</strong></div>
            </div>
            {_preview_html}
        </div>
        """, unsafe_allow_html=True)

    # Botón compartir + tarjeta descargable
    tweet = f"{seleccionado} ({row['bloque']}, {row['camara']}). Mira su perfil completo en Lobby."
    col_share1, col_share2, _ = st.columns([1.2, 1.6, 4])
    with col_share1:
        st.link_button("Compartir en X", generar_tweet(tweet), use_container_width=True)
    with col_share2:
        _stats = cargar_stats_tarjeta(leg_id, seleccionado)
        _png = tarjetas.tarjeta_legislador({
            "nombre": seleccionado,
            "bloque": row["bloque"],
            "camara": row["camara"],
            "provincia": row["distrito"],
            "proyectos": _stats["proyectos"],
            "asistencia_pct": _stats["asistencia_pct"],
            "patrimonio_total": _stats["patrimonio_total"],
            "menciones_cij": _stats["menciones_cij"],
        })
        _fname = "".join(c for c in seleccionado.lower().replace(",", "").replace(" ", "_") if c.isalnum() or c == "_")
        st.download_button(
            "📸 Tarjeta para redes",
            _png,
            file_name=f"lobby_{_fname}.png",
            mime="image/png",
            use_container_width=True,
        )

    # Tabs
    tabs = st.tabs(["Patrimonio", "Bienes", "Deudas", "Familia", "Votaciones", "Proyectos", "Afinidades"])

    # ========================================
    # TAB PATRIMONIO
    # ========================================
    with tabs[0]:
        df_ddjj = cargar_ddjj_legislador(leg_id)

        if df_ddjj.empty:
            st.info("No hay declaraciones juradas cargadas para este legislador.")
        else:
            variacion = cargar_variacion_patrimonial(leg_id)
            ranking = cargar_mediana_y_ranking(leg_id, 2024)
            
            ultimo_pat = float(df_ddjj.iloc[0]['patrimonio_neto'])
            veces_mediana = ultimo_pat / ranking['mediana'] if ranking['mediana'] > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Patrimonio 2024", fmt_pesos(ultimo_pat))
            col2.metric("vs Mediana", f"{veces_mediana:.1f}x")
            if ranking['rank']:
                col3.metric("Ranking", f"#{ranking['rank']} de {ranking['total']}")
            
            if variacion:
                st.markdown("---")
                st.markdown("**Variacion 2022-2024** (inflacion: 493%)")
                
                col1, col2, col3 = st.columns(3)
                col1.metric("2022", fmt_pesos(variacion['pat_2022']))
                col2.metric("2024", fmt_pesos(variacion['pat_2024']))
                
                if variacion['var_real'] is not None:
                    color_var = "#059669" if variacion['var_real'] > 0 else "#DC2626"
                    col3.markdown(f"""
                    <div style="background: {color_var}10; padding: 0.8rem; border-radius: 8px; text-align: center;">
                        <div style="font-size: 0.8rem; color: #6B7280;">Variacion real</div>
                        <div style="font-size: 1.5rem; font-weight: 700; color: {color_var};">{variacion['var_real']:+.1f}%</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("---")
            st.markdown("**Detalle por año**")
            for _, r in df_ddjj.iterrows():
                patrimonio = float(r['patrimonio_neto'] or 0)
                bienes = float(r['total_bienes'] or 0)
                deudas = float(r['total_deudas'] or 0)
                proveedor = r['proveedor_contratista']

                proveedor_badge = '<span style="background: #FEF3C7; color: #92400E; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.8rem; margin-left: 0.5rem;">Proveedor del Estado</span>' if proveedor == 'SI' else ''
                html_ddjj = f"""<div style="background: white; border: 1px solid #E5E7EB; border-radius: 12px; padding: 1rem; margin-bottom: 0.8rem;">
                    <div style="margin-bottom: 0.5rem;">
                        <span style="font-weight: 700; font-size: 1.1rem; color: #2563EB;">DDJJ {int(r['anio'])}</span>{proveedor_badge}
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
                </div>"""
                st.markdown(html_ddjj, unsafe_allow_html=True)

    # ========================================
    # TAB BIENES
    # ========================================
    with tabs[1]:
        df_bienes = cargar_bienes_legislador(leg_id)
        
        if df_bienes.empty:
            st.info("No hay detalle de bienes cargado para este legislador.")
        else:
            st.markdown(f"**{len(df_bienes)} bienes declarados**")
            
            # Resumen por tipo
            resumen = df_bienes.groupby('tipo').agg({
                'importe': ['count', 'sum']
            }).reset_index()
            resumen.columns = ['tipo', 'cantidad', 'total']
            resumen = resumen.sort_values('total', ascending=False)
            
            # Participaciones en empresas
            empresas = df_bienes[df_bienes['tipo'].str.contains('PARTICIPACIONES|ACCIONES.*SIN COTIZACION', case=False, na=False, regex=True)]
            if not empresas.empty:
                st.markdown("### Participaciones en empresas")
                for _, b in empresas.iterrows():
                    st.markdown(f"""
                    <div style="border-left: 4px solid #7C3AED; padding: 0.6rem 1rem; margin-bottom: 0.5rem; background: #F5F3FF; border-radius: 0 8px 8px 0;">
                        <div style="font-weight: 600;">{b['descripcion'][:100]}{'...' if len(str(b['descripcion'])) > 100 else ''}</div>
                        <div style="color: #6B7280; font-size: 0.9rem;">{fmt_pesos(b['importe'])}</div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Inmuebles
            inmuebles = df_bienes[df_bienes['tipo'].str.contains('INMUEBLES', case=False, na=False)]
            if not inmuebles.empty:
                st.markdown("### Inmuebles")
                for _, b in inmuebles.head(10).iterrows():
                    st.markdown(f"""
                    <div style="border-left: 4px solid #059669; padding: 0.6rem 1rem; margin-bottom: 0.5rem; background: #ECFDF5; border-radius: 0 8px 8px 0;">
                        <div style="font-size: 0.9rem;">{b['descripcion'][:120]}{'...' if len(str(b['descripcion'])) > 120 else ''}</div>
                        <div style="color: #059669; font-weight: 600;">{fmt_pesos(b['importe'])}</div>
                    </div>
                    """, unsafe_allow_html=True)
                if len(inmuebles) > 10:
                    st.caption(f"... y {len(inmuebles) - 10} inmuebles más")
            
            # Vehículos
            vehiculos = df_bienes[df_bienes['tipo'].str.contains('AUTOMOTORES|VEHICULOS', case=False, na=False, regex=True)]
            if not vehiculos.empty:
                st.markdown("### Vehiculos")
                for _, b in vehiculos.iterrows():
                    st.markdown(f"""
                    <div style="padding: 0.4rem 0; border-bottom: 1px solid #E5E7EB;">
                        <span>{b['descripcion'][:80]}{'...' if len(str(b['descripcion'])) > 80 else ''}</span>
                        <span style="float: right; color: #6B7280;">{fmt_pesos(b['importe'])}</span>
                    </div>
                    """, unsafe_allow_html=True)
            
            # Resumen general
            st.markdown("---")
            st.markdown("### Resumen por tipo de bien")
            for _, r in resumen.iterrows():
                st.markdown(f"""
                <div style="display: flex; justify-content: space-between; padding: 0.4rem 0; border-bottom: 1px solid #F3F4F6;">
                    <span style="font-size: 0.9rem;">{r['tipo']}</span>
                    <span><strong>{int(r['cantidad'])}</strong> ({fmt_pesos(r['total'])})</span>
                </div>
                """, unsafe_allow_html=True)

    # ========================================
    # ========================================
    # TAB DEUDAS
    # ========================================
    with tabs[2]:
        df_deudas = cargar_deudas_legislador(leg_id)

        if df_deudas.empty:
            st.info("No hay deudas registradas para este legislador.")
        else:
            total_deuda = df_deudas['importe'].sum()
            anio_deudas = int(df_deudas['anio'].iloc[0]) if pd.notna(df_deudas['anio'].iloc[0]) else None
            _periodo = f" (DDJJ {anio_deudas})" if anio_deudas else ""
            st.markdown(f"**Total adeudado{_periodo}: {fmt_pesos(total_deuda)}**")
            st.caption(
                "Datos extraídos de la última DDJJ disponible ante la Oficina Anticorrupción. "
                "Los importes son los declarados a esa fecha — no necesariamente la situación actual."
            )

            # Resumen por tipo
            col1, col2, col3 = st.columns(3)
            tipos = df_deudas.groupby('tipo')['importe'].sum()
            col1.metric("Común", fmt_pesos(tipos.get('COMUN', 0)))
            col2.metric("Hipotecario", fmt_pesos(tipos.get('HIPOTECARIO', 0)))
            col3.metric("Prendario", fmt_pesos(tipos.get('PRENDARIO', 0)))

            st.markdown("---")
            st.markdown(f"### Detalle de deudas ({len(df_deudas)})")

            for i, d in df_deudas.iterrows():
                acreedor, cuit = _parsear_acreedor(d.get('descripcion'))
                tipo = d.get('tipo') or '—'
                clasif = d.get('clasificacion') or '—'
                importe = d.get('importe')

                color = '#DC2626' if tipo == 'HIPOTECARIO' else (
                    '#7C3AED' if tipo == 'PRENDARIO' else '#F59E0B'
                )

                # Tarjeta visible
                st.markdown(f"""
                <div style="border-left: 4px solid {color}; padding: 0.7rem 1rem; margin-bottom: 0.4rem; background: {color}10; border-radius: 0 8px 8px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; flex-wrap: wrap;">
                        <div>
                            <div style="font-weight: 600;">{acreedor}</div>
                            <div style="font-size: 0.8rem; color: #6B7280; margin-top: 0.15rem;">
                                {tipo} · {clasif}{f' · CUIT {cuit}' if cuit else ''}
                            </div>
                        </div>
                        <div style="font-weight: 700; color: {color}; white-space: nowrap;">{fmt_pesos(importe)}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                # Expander con texto completo (auditoría)
                with st.expander("Ver descripción completa de la deuda", expanded=False):
                    desc_full = d.get('descripcion') or '(sin descripción)'
                    st.markdown(f"""
                    **Año DDJJ:** {anio_deudas if anio_deudas else '—'}
                    **Tipo:** {tipo}
                    **Clasificación:** {clasif}
                    **Acreedor (parseado):** {acreedor}
                    **CUIT del acreedor:** {cuit or '—'}
                    **Importe declarado:** {fmt_pesos(importe)}

                    **Descripción original (campo `deuda_descripcion`):**
                    """)
                    st.code(str(desc_full), language=None)

    # ========================================
    # TAB FAMILIA
    # ========================================
    with tabs[3]:
        df_familia = cargar_familia_legislador(leg_id)
        
        if df_familia.empty:
            st.info("No hay grupo familiar declarado.")
        else:
            st.markdown(f"**{len(df_familia)} familiares declarados**")
            
            # Separar por parentesco
            conyuges = df_familia[df_familia['parentesco'].str.contains('CONYUGE|CONVIVIENTE', case=False, na=False)]
            hijos = df_familia[df_familia['parentesco'].str.contains('HIJO', case=False, na=False)]
            
            if not conyuges.empty:
                st.markdown("### Conyuge / Conviviente")
                for _, f in conyuges.iterrows():
                    # Verificar si tiene cargo publico
                    cargo_pub = verificar_familiar_funcionario(f['cuit']) if f['cuit'] else None
                    
                    st.markdown(f"""
                    <div style="background: white; border: 1px solid #E5E7EB; border-radius: 12px; padding: 1rem; margin-bottom: 0.5rem;">
                        <div style="font-weight: 600; font-size: 1.1rem;">{f['nombre']}</div>
                        <div style="color: #6B7280; font-size: 0.9rem;">
                            {f['genero'] or ''} 
                            {' - Nac: ' + str(f['fecha_nacimiento'])[:10] if pd.notna(f['fecha_nacimiento']) else ''}
                        </div>
                        {"<div style='background: #FEF3C7; color: #92400E; padding: 0.3rem 0.6rem; border-radius: 4px; margin-top: 0.5rem; font-size: 0.85rem;'><strong>Cargo publico:</strong> " + cargo_pub['cargo'] + " - " + cargo_pub['organismo'][:50] + "</div>" if cargo_pub else ""}
                    </div>
                    """, unsafe_allow_html=True)
            
            if not hijos.empty:
                st.markdown("### Hijos/as")
                cols = st.columns(min(len(hijos), 3))
                for i, (_, f) in enumerate(hijos.iterrows()):
                    with cols[i % 3]:
                        # Calcular edad
                        edad = ""
                        if pd.notna(f['fecha_nacimiento']):
                            from datetime import date
                            try:
                                nac = pd.to_datetime(f['fecha_nacimiento']).date()
                                edad = f" ({(date.today() - nac).days // 365} años)"
                            except:
                                pass
                        
                        cargo_pub = verificar_familiar_funcionario(f['cuit']) if f['cuit'] else None
                        
                        st.markdown(f"""
                        <div style="background: #F9FAFB; border-radius: 8px; padding: 0.8rem; margin-bottom: 0.5rem;">
                            <div style="font-weight: 600;">{f['nombre']}</div>
                            <div style="color: #6B7280; font-size: 0.85rem;">{f['genero'] or ''}{edad}</div>
                            {"<div style='color: #DC2626; font-size: 0.8rem; margin-top: 0.3rem;'>Funcionario publico</div>" if cargo_pub else ""}
                        </div>
                        """, unsafe_allow_html=True)

    # TAB VOTACIONES
    # ========================================
    with tabs[4]:
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
                    color = _color_voto(tipo)

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

                        # Gráfico de barras apiladas con la MISMA paleta que Distribución
                        fig_evo = go.Figure()
                        orden_tipos = ['AFIRMATIVO', 'NEGATIVO', 'ABSTENCION', 'ABSTENCIÓN', 'AUSENTE', 'PRESIDENTE']
                        columnas_ordenadas = (
                            [t for t in orden_tipos if t in evolucion.columns]
                            + [t for t in evolucion.columns if t not in orden_tipos]
                        )
                        for tipo in columnas_ordenadas:
                            fig_evo.add_trace(go.Bar(
                                x=evolucion.index.astype(str),
                                y=evolucion[tipo],
                                name=tipo,
                                marker_color=_color_voto(tipo),
                            ))
                        fig_evo.update_layout(
                            barmode='stack',
                            xaxis_title='Año',
                            yaxis_title='Votos',
                            height=320,
                            margin=dict(l=10, r=10, t=10, b=10),
                            legend=dict(orientation='h', y=-0.25),
                        )
                        st.plotly_chart(fig_evo, use_container_width=True)

            # Tabla detallada colapsada: antes aparecía por default y agregaba ruido
            # debajo de los gráficos de Distribución / Evolución temporal.
            df_con_fecha = df_votos.dropna(subset=['fecha'])
            if not df_con_fecha.empty:
                with st.expander(f"📋 Ver últimas {min(15, len(df_con_fecha))} votaciones en detalle", expanded=False):
                    st.dataframe(
                        df_con_fecha.head(15)[['fecha', 'voto_individual', 'titulo_acta']].rename(columns={
                            'fecha': 'Fecha', 'voto_individual': 'Voto', 'titulo_acta': 'Asunto'
                        }),
                        use_container_width=True,
                        hide_index=True
                    )

    # ========================================
    # TAB PROYECTOS
    # ========================================
    with tabs[5]:
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
    with tabs[6]:
        st.markdown("""
        <div style="background: #F0F9FF; border: 1px solid #BAE6FD; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
            <strong>Como se calcula?</strong>
            <span style="color: #0369A1; font-size: 0.9rem;">
            Se comparan todas las votaciones donde ambos legisladores participaron.
            El porcentaje indica en cuantas votaron igual.
            </span>
        </div>
        """, unsafe_allow_html=True)

        tipo_votacion = st.radio(
            "Base de cálculo",
            ["Todas las votaciones", "Solo proyectos de ley"],
            horizontal=True,
            key=f"afin_tipo_{leg_id}",
            help="'Solo proyectos de ley' excluye mociones, apartamientos de reglamento y cuestiones de privilegio."
        )
        solo_leyes = tipo_votacion == "Solo proyectos de ley"

        col_af1, col_af2 = st.columns(2)

        with col_af1:
            st.markdown("**Vota mas igual con...**")
            df_afin = calcular_afinidad(leg_id, solo_leyes=solo_leyes)
            if df_afin.empty:
                st.info("Sin datos suficientes.")
            else:
                for _, r in df_afin.iterrows():
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
            df_div = calcular_divergencia(leg_id, solo_leyes=solo_leyes)
            if df_div.empty:
                st.info("Sin datos suficientes.")
            else:
                for _, r in df_div.iterrows():
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

@st.cache_data(ttl=3600)
def cargar_deudas_legislador(legislador_id):
    """
    Carga deudas del legislador correspondientes a la última DDJJ disponible.
    Incluye el año, para que el dato sea verificable.
    """
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT
                anio,
                deuda_tipo,
                deuda_descripcion,
                deuda_clasificacion,
                deuda_importe
            FROM ddjj_deudas
            WHERE legislador_id = :id
              AND anio = (
                  SELECT MAX(anio) FROM ddjj_deudas WHERE legislador_id = :id
              )
            ORDER BY deuda_importe DESC NULLS LAST
        """), {"id": legislador_id})
        return pd.DataFrame(
            result.fetchall(),
            columns=['anio', 'tipo', 'descripcion', 'clasificacion', 'importe'],
        )
    finally:
        db.close()


def _parsear_acreedor(descripcion: str) -> tuple[str, str | None]:
    """
    El campo `deuda_descripcion` típico de la OA viene con el acreedor seguido
    de "-CUIT XX-XXXXXXXX-X" y a veces más texto. Devolvemos (acreedor, cuit).
    Tolerante a None / NaN / formatos sucios.
    """
    if descripcion is None:
        return ("Acreedor no informado", None)
    if isinstance(descripcion, float) and pd.isna(descripcion):
        return ("Acreedor no informado", None)
    s = str(descripcion).strip()
    if not s:
        return ("Acreedor no informado", None)
    # Buscar CUIT con regex laxa
    import re as _re
    m = _re.search(r"CUIT[\s:\-]*([\d\-]{8,15})", s, flags=_re.IGNORECASE)
    cuit = m.group(1) if m else None
    # Acreedor = texto antes del primer "-CUIT" / "CUIT"
    if " -CUIT" in s:
        acreedor = s.split(" -CUIT", 1)[0].strip()
    elif " CUIT" in s:
        acreedor = s.split(" CUIT", 1)[0].strip()
    else:
        acreedor = s.strip(" -")
    return (acreedor or "Acreedor no informado", cuit)

@st.cache_data(ttl=3600)
def cargar_familia_legislador(legislador_id):
    """Carga grupo familiar del legislador."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT familiar_apellido_nombre, familiar_parentesco, familiar_genero, 
                   familiar_fecha_nacimiento, familiar_cuit
            FROM ddjj_grupo_familiar
            WHERE legislador_id = :id
            ORDER BY familiar_parentesco, familiar_apellido_nombre
        """), {"id": legislador_id})
        return pd.DataFrame(result.fetchall(), columns=['nombre', 'parentesco', 'genero', 'fecha_nacimiento', 'cuit'])
    finally:
        db.close()

@st.cache_data(ttl=3600)
def verificar_familiar_funcionario(cuit_familiar):
    """Verifica si un familiar tiene cargo publico."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT funcionario_apellido_nombre, cargo, organismo
            FROM ddjj_legisladores
            WHERE cuit = :cuit
            LIMIT 1
        """), {"cuit": cuit_familiar})
        row = result.fetchone()
        if row:
            return {'nombre': row[0], 'cargo': row[1], 'organismo': row[2]}
        return None
    finally:
        db.close()
