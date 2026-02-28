import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal
from src.styles import apply_styles, show_logo

st.set_page_config(page_title="Patrimonio · Lobby", layout="wide")
apply_styles()
show_logo()
st.sidebar.title("Monitor Legislativo")
st.sidebar.markdown("Congreso de la Nación · Argentina")

URL_BUSCADOR = "https://www2.jus.gov.ar/consultaddjj/Home/Busqueda"
URL_CSV = "https://datos.jus.gob.ar/dataset/4680199f-6234-4262-8a2a-8f7993bf784d/resource/a331ccb8-5c13-447f-9bd6-d8018a4b8a62/download/ddjj-2024-12-22.csv"


def fmt_pesos(val):
    if not val or val == 0:
        return "—"
    millones = val / 1_000_000
    if millones >= 1000:
        return f"${millones/1000:,.1f}B"
    return f"${millones:,.1f}M"


@st.cache_data(ttl=3600)
def cargar_ddjj():
    db = SessionLocal()
    result = db.execute(text("""
        SELECT
            d.id, d.anio, d.cuit, d.funcionario_apellido_nombre,
            d.organismo, d.cargo,
            d.total_bienes, d.total_deudas, d.patrimonio_neto,
            d.ingresos_neto_gastos, d.proveedor_contratista,
            d.tipo_declaracion, d.legislador_id,
            l.nombre_completo, l.bloque, l.distrito, l.camara
        FROM ddjj_legisladores d
        LEFT JOIN legisladores l ON l.id = d.legislador_id
        ORDER BY d.patrimonio_neto DESC NULLS LAST
    """))
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    for col in ['total_bienes', 'total_deudas', 'patrimonio_neto', 'ingresos_neto_gastos']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    return df


# ---------------------------------------------------------
st.title("Declaraciones Juradas")
st.markdown("<div class='page-subtitle'>Patrimonio de legisladores · Fuente: Oficina Anticorrupción 2024</div>", unsafe_allow_html=True)

df = cargar_ddjj()

if df.empty:
    st.warning("Sin datos.")
    st.stop()

tab_ranking, tab_tabla, tab_bloques = st.tabs(["Rankings", "Tabla completa", "Por bloque"])

# ── TAB 1: RANKINGS ─────────────────────────────────────────
with tab_ranking:
    col_rica, col_deuda = st.columns(2)

    with col_rica:
        st.subheader("Top 5 mayor patrimonio")
        top_ricos = df.nlargest(5, 'patrimonio_neto')[
            ['funcionario_apellido_nombre', 'bloque', 'camara', 'patrimonio_neto']
        ]
        for i, r in enumerate(top_ricos.itertuples(), 1):
            st.markdown(f"""
            <div style='background:white; border-left:4px solid #0F2240; padding:0.8rem 1rem; margin-bottom:0.5rem; border-radius:4px;'>
                <div style='font-size:0.75rem; color:#999; font-weight:600'>#{i}</div>
                <div style='font-weight:600; color:#1a1a1a'>{r.funcionario_apellido_nombre}</div>
                <div style='font-size:0.8rem; color:#666'>{r.bloque} · {r.camara}</div>
                <div style='font-size:1.2rem; font-weight:700; color:#0F2240; margin-top:0.3rem'>{fmt_pesos(r.patrimonio_neto)}</div>
            </div>
            """, unsafe_allow_html=True)

    with col_deuda:
        st.subheader("Top 5 mayor endeudamiento")
        top_deudas = df[df['total_deudas'] > 0].nlargest(5, 'total_deudas')[
            ['funcionario_apellido_nombre', 'bloque', 'camara', 'total_deudas']
        ]
        for i, r in enumerate(top_deudas.itertuples(), 1):
            st.markdown(f"""
            <div style='background:white; border-left:4px solid #c0392b; padding:0.8rem 1rem; margin-bottom:0.5rem; border-radius:4px;'>
                <div style='font-size:0.75rem; color:#999; font-weight:600'>#{i}</div>
                <div style='font-weight:600; color:#1a1a1a'>{r.funcionario_apellido_nombre}</div>
                <div style='font-size:0.8rem; color:#666'>{r.bloque} · {r.camara}</div>
                <div style='font-size:1.2rem; font-weight:700; color:#c0392b; margin-top:0.3rem'>{fmt_pesos(r.total_deudas)}</div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # Métricas generales
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Legisladores con DDJJ", len(df))
    col2.metric("Patrimonio promedio", fmt_pesos(float(df['patrimonio_neto'].mean())))
    col3.metric("Mayor patrimonio", fmt_pesos(float(df['patrimonio_neto'].max())))
    col4.metric("Proveedores del Estado", int((df['proveedor_contratista'] == 'SI').sum()))

# ── TAB 2: TABLA COMPLETA ───────────────────────────────────
with tab_tabla:
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        busqueda = st.text_input("Buscar legislador", placeholder="Ej: Kirchner, Lousteau...")
    with col_f2:
        camara_opts = ["Todas"] + sorted(df['camara'].dropna().unique().tolist())
        camara_sel = st.selectbox("Cámara", camara_opts)
    with col_f3:
        orden = st.selectbox("Ordenar por", ["Mayor patrimonio", "Menor patrimonio", "Mayor deuda", "Apellido"])

    df_filtrado = df.copy()
    if busqueda:
        df_filtrado = df_filtrado[
            df_filtrado['funcionario_apellido_nombre'].str.contains(busqueda, case=False, na=False) |
            df_filtrado['nombre_completo'].str.contains(busqueda, case=False, na=False)
        ]
    if camara_sel != "Todas":
        df_filtrado = df_filtrado[df_filtrado['camara'] == camara_sel]

    if orden == "Mayor patrimonio":
        df_filtrado = df_filtrado.sort_values('patrimonio_neto', ascending=False)
    elif orden == "Menor patrimonio":
        df_filtrado = df_filtrado.sort_values('patrimonio_neto', ascending=True)
    elif orden == "Mayor deuda":
        df_filtrado = df_filtrado.sort_values('total_deudas', ascending=False)
    else:
        df_filtrado = df_filtrado.sort_values('funcionario_apellido_nombre')

    st.subheader(f"{len(df_filtrado)} declaraciones")
    tabla = df_filtrado[[
        'funcionario_apellido_nombre', 'bloque', 'distrito', 'camara',
        'patrimonio_neto', 'total_bienes', 'total_deudas',
        'ingresos_neto_gastos', 'proveedor_contratista', 'cuit'
    ]].copy().rename(columns={
        'funcionario_apellido_nombre': 'Legislador', 'bloque': 'Bloque',
        'distrito': 'Distrito', 'camara': 'Cámara',
        'patrimonio_neto': 'Patrimonio neto', 'total_bienes': 'Bienes',
        'total_deudas': 'Deudas', 'ingresos_neto_gastos': 'Ingresos',
        'proveedor_contratista': 'Proveedor Estado', 'cuit': 'CUIT',
    })

    st.dataframe(
        tabla, use_container_width=True, hide_index=True,
        column_config={
            'Patrimonio neto': st.column_config.NumberColumn(format="$ %d"),
            'Bienes': st.column_config.NumberColumn(format="$ %d"),
            'Deudas': st.column_config.NumberColumn(format="$ %d"),
            'Ingresos': st.column_config.NumberColumn(format="$ %d"),
        }
    )

    with st.expander("Como consultar la declaracion original"):
        st.markdown(f"""
Para acceder al documento completo de cada declaración jurada:

1. **Buscador de la Oficina Anticorrupción** — ingresá el apellido del legislador:
   [{URL_BUSCADOR}]({URL_BUSCADOR})

2. **CSV completo 2024** — filtrá por CUIT:
   [Descargar CSV]({URL_CSV})
        """)

# ── TAB 3: POR BLOQUE ───────────────────────────────────────
with tab_bloques:
    st.subheader("Patrimonio promedio por bloque")
    df_bloque = df[df['bloque'].notna()].groupby('bloque').agg(
        legisladores=('id', 'count'),
        patrimonio_promedio=('patrimonio_neto', 'mean'),
        patrimonio_total=('patrimonio_neto', 'sum')
    ).reset_index().sort_values('patrimonio_promedio', ascending=False)

    st.bar_chart(df_bloque.set_index('bloque')['patrimonio_promedio'])

    st.dataframe(
        df_bloque.rename(columns={
            'bloque': 'Bloque', 'legisladores': 'Legisladores',
            'patrimonio_promedio': 'Patrimonio promedio',
            'patrimonio_total': 'Patrimonio total',
        }),
        use_container_width=True, hide_index=True,
        column_config={
            'Patrimonio promedio': st.column_config.NumberColumn(format="$ %d"),
            'Patrimonio total': st.column_config.NumberColumn(format="$ %d"),
        }
    )