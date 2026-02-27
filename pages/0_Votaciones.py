import re
import streamlit as st
import pandas as pd
from src.styles import apply_styles, show_logo
from sqlalchemy import text
from src.database import SessionLocal
show_logo()
apply_styles()

st.set_page_config(page_title="Votaciones — Lobby", layout="wide")

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

def extraer_tema_madre(titulo):
    """'Modernización Laboral. Título V.' → 'Modernización Laboral'"""
    titulo = limpiar(titulo or '')
    partes = titulo.split('.')
    return partes[0].strip()

def es_subtitulo(titulo):
    titulo = limpiar(titulo or '')
    return bool(re.search(r'\.(.*)(T[íi]tulo|Art[íi]culo|Cap[íi]tulo|Secci[óo]n)', titulo, re.IGNORECASE))

@st.cache_data(ttl=3600)
def cargar_votaciones(limit=100):
    db = SessionLocal()
    result = db.execute(text("""
        SELECT acta_id, titulo, fecha, resultado,
               votos_afirmativos, votos_negativos, abstenciones, ausentes
        FROM actas_cabecera
        WHERE fecha IS NOT NULL
        ORDER BY fecha DESC, acta_id DESC
        LIMIT :limit
    """), {"limit": limit})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    df['titulo'] = df['titulo'].apply(limpiar)
    df['tema_madre'] = df['titulo'].apply(extraer_tema_madre)
    df['es_sub'] = df['titulo'].apply(es_subtitulo)
    return df

@st.cache_data(ttl=3600)
def cargar_detalle_votacion(acta_id):
    db = SessionLocal()
    result = db.execute(text("""
        SELECT
            l.nombre_completo,
            l.bloque,
            l.distrito,
            v.voto_individual
        FROM votos v
        JOIN legisladores l ON l.id = v.legislador_id
        WHERE v.acta_id = :acta_id
        ORDER BY l.bloque, l.nombre_completo
    """), {"acta_id": acta_id})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    df['bloque'] = df['bloque'].apply(limpiar)
    return df

def mostrar_votos_acta(acta_id, titulo):
    df = cargar_detalle_votacion(acta_id)
    if df.empty:
        st.caption("Sin detalle de votos.")
        return

    col_a, col_b = st.columns(2)

    with col_a:
        afavor = df[df['voto_individual'] == 'AFIRMATIVO']
        st.markdown(f"**🟢 A favor — {len(afavor)} votos**")
        if not afavor.empty:
            for bloque, grp in afavor.groupby('bloque'):
                with st.expander(f"{bloque or 'Sin bloque'} ({len(grp)})"):
                    st.dataframe(
                        grp[['nombre_completo', 'distrito']].rename(columns={
                            'nombre_completo': 'Legislador', 'distrito': 'Distrito'
                        }),
                        use_container_width=True, hide_index=True
                    )

    with col_b:
        encontra = df[df['voto_individual'] == 'NEGATIVO']
        st.markdown(f"**🔴 En contra — {len(encontra)} votos**")
        if not encontra.empty:
            for bloque, grp in encontra.groupby('bloque'):
                with st.expander(f"{bloque or 'Sin bloque'} ({len(grp)})"):
                    st.dataframe(
                        grp[['nombre_completo', 'distrito']].rename(columns={
                            'nombre_completo': 'Legislador', 'distrito': 'Distrito'
                        }),
                        use_container_width=True, hide_index=True
                    )

    abstenciones = df[df['voto_individual'].isin(['ABSTENCION', 'ABSTENCIÓN'])]
    if not abstenciones.empty:
        st.markdown(f"**🟡 Abstenciones — {len(abstenciones)} votos**")
        for bloque, grp in abstenciones.groupby('bloque'):
            with st.expander(f"{bloque or 'Sin bloque'} ({len(grp)})"):
                st.dataframe(
                    grp[['nombre_completo', 'distrito']].rename(columns={
                        'nombre_completo': 'Legislador', 'distrito': 'Distrito'
                    }),
                    use_container_width=True, hide_index=True
                )

# ---------------------------------------------------------
st.title("Votaciones")
st.markdown("<div class='page-subtitle'>Cámara de Diputados · Votaciones nominales</div>", unsafe_allow_html=True)

col_f1, col_f2 = st.columns([3, 1])
with col_f1:
    busqueda = st.text_input("Buscar por tema", placeholder="Ej: Presupuesto, Laboral, Educación...")
with col_f2:
    limit = st.selectbox("Mostrar últimas", [50, 100, 200, 500], index=1)

df = cargar_votaciones(limit)

if busqueda:
    df = df[df['titulo'].str.contains(busqueda, case=False, na=False)]

# Métricas
total_leyes = df['tema_madre'].nunique()
col1, col2, col3 = st.columns(3)
col1.metric("Leyes / temas votados", total_leyes)
col2.metric("Votaciones nominales", len(df))
col3.metric("Período", f"{df['fecha'].min()} – {df['fecha'].max()}" if not df.empty else "—")

st.divider()

# Agrupar por tema madre + fecha
grupos = df.groupby(['tema_madre', 'fecha'], sort=False)

for (tema, fecha), grp in grupos:
    grp = grp.sort_values('acta_id')
    acta_principal = grp[~grp['es_sub']].head(1)
    subtitulos = grp[grp['es_sub']]

    # Totales agregados del grupo
    total_afirm = int(grp['votos_afirmativos'].fillna(0).max())
    total_neg = int(grp['votos_negativos'].fillna(0).max())
    total_abst = int(grp['abstenciones'].fillna(0).max())
    n_sub = len(subtitulos)

    label_sub = f" · {n_sub} votaciones parciales" if n_sub > 0 else ""
    header = f"**{tema}** — {fecha}{label_sub} · {total_afirm}✔ {total_neg}✘"

    with st.expander(header):
        # Votación general (acta principal)
        if not acta_principal.empty:
            row = acta_principal.iloc[0]
            st.markdown(f"##### Votación general")
            mostrar_votos_acta(int(row['acta_id']), row['titulo'])

        # Subtítulos colapsados
        if not subtitulos.empty:
            st.markdown("---")
            st.markdown(f"##### Votaciones por título ({n_sub})")
            for _, sub in subtitulos.iterrows():
                subtitulo_limpio = limpiar(sub['titulo'])
                afirm_s = int(sub['votos_afirmativos'] or 0)
                neg_s = int(sub['votos_negativos'] or 0)
                with st.expander(f"↳ {subtitulo_limpio} · {afirm_s}✔ {neg_s}✘"):
                    mostrar_votos_acta(int(sub['acta_id']), sub['titulo'])