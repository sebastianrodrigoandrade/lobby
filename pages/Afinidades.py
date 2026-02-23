# pages/2_Afinidad.py
import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal
from src.styles import apply_styles
apply_styles()

st.set_page_config(page_title="Afinidad de votos — Monitor Legislativo", layout="wide")

@st.cache_data(ttl=3600)
def cargar_legisladores():
    db = SessionLocal()
    result = db.execute(text("""
        SELECT l.id, l.nombre_completo, 
               COALESCE(l.bloque, '—') as bloque,
               COALESCE(l.distrito, '—') as distrito,
               COUNT(v.id) as total_votos
        FROM legisladores l
        JOIN votos v ON v.legislador_id = l.id
        GROUP BY l.id, l.nombre_completo, l.bloque, l.distrito
        HAVING COUNT(v.id) > 50
        ORDER BY l.nombre_completo
    """))
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df

@st.cache_data(ttl=3600)
def calcular_afinidad(legislador_id, top_n=20):
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
            l.id as leg_id,
            l.nombre_completo,
            COALESCE(l.bloque, '—') as bloque,
            COALESCE(l.distrito, '—') as distrito,
            c.votaciones_compartidas,
            c.coincidencias,
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
def calcular_divergencia(legislador_id, top_n=20):
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
            l.id as leg_id,
            l.nombre_completo,
            COALESCE(l.bloque, '—') as bloque,
            COALESCE(l.distrito, '—') as distrito,
            c.votaciones_compartidas,
            c.coincidencias,
            ROUND(c.coincidencias * 100.0 / c.votaciones_compartidas, 1) as afinidad_pct
        FROM comparacion c
        JOIN legisladores l ON l.id = c.legislador_id
        ORDER BY afinidad_pct ASC
        LIMIT :top_n
    """), {"id": legislador_id, "top_n": top_n})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df

@st.cache_data(ttl=3600)
def cargar_divergencias(leg_id_a, leg_id_b):
    """Votaciones donde A y B votaron DISTINTO."""
    db = SessionLocal()
    result = db.execute(text("""
        SELECT 
            a.acta_id,
            a.voto_individual as voto_a,
            b.voto_individual as voto_b,
            ac.titulo as asunto,
            ac.fecha,
            ac.resultado
        FROM votos a
        JOIN votos b ON b.acta_id = a.acta_id AND b.legislador_id = :leg_b
        LEFT JOIN actas_cabecera ac ON ac.acta_id = a.acta_id
        WHERE a.legislador_id = :leg_a
          AND a.acta_id IS NOT NULL
          AND a.voto_individual != b.voto_individual
        ORDER BY ac.fecha DESC NULLS LAST
        LIMIT 30
    """), {"leg_a": leg_id_a, "leg_b": leg_id_b})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df

@st.cache_data(ttl=3600)
def cargar_coincidencias(leg_id_a, leg_id_b):
    """Votaciones donde A y B votaron IGUAL."""
    db = SessionLocal()
    result = db.execute(text("""
        SELECT 
            a.acta_id,
            a.voto_individual as voto,
            ac.titulo as asunto,
            ac.fecha,
            ac.resultado
        FROM votos a
        JOIN votos b ON b.acta_id = a.acta_id AND b.legislador_id = :leg_b
        LEFT JOIN actas_cabecera ac ON ac.acta_id = a.acta_id
        WHERE a.legislador_id = :leg_a
          AND a.acta_id IS NOT NULL
          AND a.voto_individual = b.voto_individual
        ORDER BY ac.fecha DESC NULLS LAST
        LIMIT 30
    """), {"leg_a": leg_id_a, "leg_b": leg_id_b})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df

# ---------------------------------------------------------
st.title("Afinidad de votos")
st.markdown("¿Con quién vota igual — y con quién vota distinto?")

df_leg = cargar_legisladores()
nombres = df_leg['nombre_completo'].tolist()

busqueda = st.text_input("Buscar legislador", placeholder="Ej: Lospennato, Kirchner, Espert...")
if busqueda:
    nombres = [n for n in nombres if busqueda.lower() in n.lower()]

if not nombres:
    st.warning("No se encontró el legislador.")
    st.stop()

seleccionado = st.selectbox("Seleccionar legislador", nombres)
row = df_leg[df_leg['nombre_completo'] == seleccionado].iloc[0]
leg_id = int(row['id'])

col1, col2, col3 = st.columns(3)
col1.metric("Bloque", row['bloque'])
col2.metric("Distrito", row['distrito'])
col3.metric("Votaciones analizadas", int(row['total_votos']))

st.divider()

with st.spinner("Calculando afinidad..."):
    df_afin = calcular_afinidad(leg_id)
    df_div = calcular_divergencia(leg_id)

col_a, col_b = st.columns(2)

with col_a:
    st.subheader("Vota más igual con...")
    if df_afin.empty:
        st.info("Sin datos suficientes.")
    else:
        for _, r in df_afin.iterrows():
            with st.expander(f"**{r['nombre_completo']}** ({r['bloque']}) — {r['afinidad_pct']}% afinidad · {int(r['votaciones_compartidas'])} votaciones"):
                st.caption(f"Voto A = **{seleccionado}** · Voto B = **{r['nombre_completo']}** · Votaciones donde no coincidieron")
                df_diver = cargar_divergencias(leg_id, int(r['leg_id']))
                if df_diver.empty:
                    st.write("Coincidieron en todas las votaciones registradas.")
                else:
                    st.dataframe(
                        df_diver[['fecha', 'asunto', 'voto_a', 'voto_b', 'resultado']].rename(columns={
                            'fecha': 'Fecha',
                            'asunto': 'Asunto',
                            'voto_a': 'Voto A',
                            'voto_b': 'Voto B',
                            'resultado': 'Resultado'
                        }),
                        use_container_width=True,
                        hide_index=True
                    )

with col_b:
    st.subheader("Vota más distinto con...")
    if df_div.empty:
        st.info("Sin datos suficientes.")
    else:
        for _, r in df_div.iterrows():
            with st.expander(f"**{r['nombre_completo']}** ({r['bloque']}) — {r['afinidad_pct']}% afinidad · {int(r['votaciones_compartidas'])} votaciones"):
                st.caption("Votaciones donde **sí** coincidieron")
                df_coinc = cargar_coincidencias(leg_id, int(r['leg_id']))
                if df_coinc.empty:
                    st.write("No hubo coincidencias registradas.")
                else:
                    st.dataframe(
                        df_coinc[['fecha', 'asunto', 'voto', 'resultado']].rename(columns={
                            'fecha': 'Fecha',
                            'asunto': 'Asunto',
                            'voto': 'Voto compartido',
                            'resultado': 'Resultado'
                        }),
                        use_container_width=True,
                        hide_index=True
                    )