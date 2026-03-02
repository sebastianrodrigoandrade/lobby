"""
Lobby - Página de Actividad
Votaciones, Sesiones, Comisiones
"""
import re
import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal

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
    titulo = limpiar(titulo or '')
    partes = titulo.split('.')
    return partes[0].strip()

NOMBRES_COMISIONES = {
    "caconstitucionales": "Asuntos Constitucionales",
    "clgeneral": "Legislación General",
    "creyculto": "Relaciones Exteriores y Culto",
    "cpyhacienda": "Presupuesto y Hacienda",
    "ceducacion": "Educación",
    "ccytecnologia": "Ciencia y Tecnología",
    "ccultura": "Cultura",
    "cjusticia": "Justicia",
    "cpyssocial": "Previsión y Seguridad Social",
    "casyspublica": "Acción Social y Salud Pública",
    "cfnjuventudes": "Familia, Niñez y Juventudes",
    "cpmayores": "Personas Mayores",
    "clpenal": "Legislación Penal",
    "cltrabajo": "Legislación del Trabajo",
    "cdnacional": "Defensa Nacional",
    "copublicas": "Obras Públicas",
    "cayganaderia": "Agricultura y Ganadería",
    "cfinanzas": "Finanzas",
    "cindustria": "Industria",
    "ccomercio": "Comercio",
    "ceycombust": "Energía y Combustibles",
    "cceinformatica": "Comunicaciones e Informática",
    "ctransportes": "Transportes",
    "ceydregional": "Economía y Desarrollo Regional",
    "camunicipales": "Asuntos Municipales",
    "cimaritimos": "Intereses Marítimos",
    "cvyourbano": "Vivienda y Ordenamiento Urbano",
    "cppyreglamento": "Peticiones, Poderes y Reglamento",
    "cjpolitico": "Juicio Político",
    "crnaturales": "Recursos Naturales",
    "cturismo": "Turismo",
    "ceconomia": "Economía",
    "cmineria": "Minería",
    "cdrogadiccion": "Prevención de Adicciones",
    "cdhygarantias": "Derechos Humanos y Garantías",
    "cacym": "Asuntos Cooperativos y Mutuales",
    "cmercosur": "Mercosur",
    "cpymes": "Pequeñas y Medianas Empresas",
    "cdconsumidor": "Defensa del Consumidor",
    "csinterior": "Seguridad Interior",
    "clexpresion": "Libertad de Expresión",
    "cdiscap": "Discapacidad",
    "cmujeresydiv": "Mujeres y Diversidad",
}


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
    return df


@st.cache_data(ttl=3600)
def cargar_detalle_votacion(acta_id):
    db = SessionLocal()
    result = db.execute(text("""
        SELECT l.nombre_completo, l.bloque, l.distrito, v.voto_individual
        FROM votos v
        JOIN legisladores l ON l.id = v.legislador_id
        WHERE v.acta_id = :acta_id
        ORDER BY l.bloque, l.nombre_completo
    """), {"acta_id": acta_id})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    df['bloque'] = df['bloque'].apply(limpiar)
    return df


@st.cache_data(ttl=3600)
def cargar_sesiones():
    db = SessionLocal()
    result = db.execute(text("""
        SELECT s.id, s.fecha, s.tipo_periodo, s.tipo_reunion,
               s.duracion_horas, s.hubo_quorum, s.periodo_id
        FROM sesiones s
        ORDER BY s.fecha DESC NULLS LAST
    """))
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


@st.cache_data(ttl=3600)
def cargar_temario_sesion(sesion_id):
    db = SessionLocal()
    result = db.execute(text("""
        SELECT item_nro, descripcion
        FROM temario_items
        WHERE sesion_id = :id
        ORDER BY item_nro
    """), {"id": sesion_id})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


@st.cache_data(ttl=3600)
def cargar_comisiones():
    db = SessionLocal()
    result = db.execute(text("""
        SELECT c.id, c.slug,
               COUNT(DISTINCT ci.id) as total_integrantes,
               COUNT(DISTINCT cr.id) as total_reuniones,
               COUNT(DISTINCT CASE WHEN cr.tipo = 'INVITADO' THEN cr.id END) as reuniones_con_invitados
        FROM comisiones c
        LEFT JOIN comision_integrantes ci ON ci.comision_id = c.id
        LEFT JOIN comision_reuniones cr ON cr.comision_id = c.id
        GROUP BY c.id, c.slug
        ORDER BY c.slug
    """))
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    df['nombre'] = df['slug'].map(NOMBRES_COMISIONES).fillna(df['slug'])
    return df


@st.cache_data(ttl=3600)
def cargar_integrantes(comision_id):
    db = SessionLocal()
    result = db.execute(text("""
        SELECT ci.cargo, ci.nombre_raw, ci.bloque, ci.distrito
        FROM comision_integrantes ci
        WHERE ci.comision_id = :id
        ORDER BY
            CASE ci.cargo
                WHEN 'PRESIDENTE' THEN 1
                WHEN 'VICEPRESIDENTE 1°' THEN 2
                WHEN 'VICEPRESIDENTE 2°' THEN 3
                WHEN 'SECRETARIO' THEN 4
                ELSE 5
            END
    """), {"id": comision_id})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


@st.cache_data(ttl=3600)
def cargar_reuniones(comision_id):
    db = SessionLocal()
    result = db.execute(text("""
        SELECT fecha, tipo, descripcion
        FROM comision_reuniones
        WHERE comision_id = :id
        ORDER BY fecha DESC
    """), {"id": comision_id})
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    return df


def render():
    """Renderiza la página de actividad"""
    
    st.title("Actividad Legislativa")
    st.markdown("<div class='page-subtitle'>Votaciones, sesiones y comisiones del Congreso</div>", unsafe_allow_html=True)

    tabs = st.tabs(["🗳️ Votaciones", "📋 Sesiones", "👥 Comisiones"])

    # ========== TAB VOTACIONES ==========
    with tabs[0]:
        col_f1, col_f2 = st.columns([3, 1])
        with col_f1:
            busqueda = st.text_input("🔍 Buscar por tema", placeholder="Ej: Presupuesto, Laboral...", key="vot_busq")
        with col_f2:
            limit = st.selectbox("Mostrar", [50, 100, 200, 500], index=1, key="vot_lim")

        df = cargar_votaciones(limit)
        
        if busqueda:
            df = df[df['titulo'].str.contains(busqueda, case=False, na=False)]

        total_leyes = df['tema_madre'].nunique()
        col1, col2, col3 = st.columns(3)
        col1.metric("Temas votados", total_leyes)
        col2.metric("Votaciones nominales", len(df))
        col3.metric("Período", f"{df['fecha'].min()} – {df['fecha'].max()}" if not df.empty else "—")

        st.markdown("---")

        grupos = df.groupby(['tema_madre', 'fecha'], sort=False)

        for (tema, fecha), grp in grupos:
            total_afirm = int(grp['votos_afirmativos'].fillna(0).max())
            total_neg = int(grp['votos_negativos'].fillna(0).max())

            with st.expander(f"**{tema}** — {fecha} · {total_afirm}✓ {total_neg}✗"):
                acta_id = int(grp.iloc[0]['acta_id'])
                df_detalle = cargar_detalle_votacion(acta_id)
                
                if not df_detalle.empty:
                    col_a, col_b = st.columns(2)
                    
                    with col_a:
                        afavor = df_detalle[df_detalle['voto_individual'] == 'AFIRMATIVO']
                        st.markdown(f"**🟢 A favor — {len(afavor)}**")
                        for bloque, grp_b in afavor.groupby('bloque'):
                            st.markdown(f"*{bloque or 'Sin bloque'}* ({len(grp_b)})")

                    with col_b:
                        encontra = df_detalle[df_detalle['voto_individual'] == 'NEGATIVO']
                        st.markdown(f"**🔴 En contra — {len(encontra)}**")
                        for bloque, grp_b in encontra.groupby('bloque'):
                            st.markdown(f"*{bloque or 'Sin bloque'}* ({len(grp_b)})")

    # ========== TAB SESIONES ==========
    with tabs[1]:
        df_ses = cargar_sesiones()

        if df_ses.empty:
            st.warning("No hay sesiones cargadas.")
        else:
            df_ses['fecha'] = pd.to_datetime(df_ses['fecha'])
            df_ses['año'] = df_ses['fecha'].dt.year
            df_ses['duracion_horas'] = pd.to_numeric(df_ses['duracion_horas'], errors='coerce')

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total sesiones", len(df_ses))
            col2.metric("Con quórum", df_ses[df_ses['hubo_quorum'] == 'Sí'].shape[0])
            col3.metric("Sin quórum", df_ses[df_ses['hubo_quorum'] == 'No'].shape[0])
            col4.metric("Duración promedio", f"{df_ses['duracion_horas'].mean():.1f}h")

            st.markdown("---")

            col_f1, col_f2 = st.columns(2)
            with col_f1:
                años = ["Todos"] + sorted(df_ses['año'].dropna().unique().astype(int).tolist(), reverse=True)
                año_sel = st.selectbox("Año", años, key="ses_año")
            with col_f2:
                tipos = ["Todos"] + sorted(df_ses['tipo_periodo'].dropna().unique().tolist())
                tipo_sel = st.selectbox("Tipo", tipos, key="ses_tipo")

            df_filtrado = df_ses.copy()
            if año_sel != "Todos":
                df_filtrado = df_filtrado[df_filtrado['año'] == int(año_sel)]
            if tipo_sel != "Todos":
                df_filtrado = df_filtrado[df_filtrado['tipo_periodo'] == tipo_sel]

            st.markdown("### Duración por sesión")
            if not df_filtrado.empty:
                chart_data = df_filtrado.set_index('fecha')[['duracion_horas']].sort_index()
                st.bar_chart(chart_data)

            st.dataframe(
                df_filtrado[['fecha', 'tipo_periodo', 'tipo_reunion', 'duracion_horas', 'hubo_quorum']].rename(columns={
                    'fecha': 'Fecha', 'tipo_periodo': 'Período', 'tipo_reunion': 'Tipo',
                    'duracion_horas': 'Duración (hs)', 'hubo_quorum': 'Quórum',
                }),
                use_container_width=True, hide_index=True
            )

    # ========== TAB COMISIONES ==========
    with tabs[2]:
        df_com = cargar_comisiones()

        col1, col2, col3 = st.columns(3)
        col1.metric("Comisiones", len(df_com))
        col2.metric("Reuniones", int(df_com['total_reuniones'].sum()))
        col3.metric("Con invitados", int(df_com['reuniones_con_invitados'].sum()))

        st.markdown("---")

        busqueda_com = st.text_input("🔍 Buscar comisión", placeholder="Ej: Justicia, Presupuesto...", key="com_busq")
        
        df_com_filtrado = df_com.copy()
        if busqueda_com:
            df_com_filtrado = df_com_filtrado[df_com_filtrado['nombre'].str.contains(busqueda_com, case=False, na=False)]

        col_lista, col_detalle = st.columns([1, 2])

        with col_lista:
            st.markdown("### Comisiones")
            st.dataframe(
                df_com_filtrado[['nombre', 'total_integrantes', 'total_reuniones']].rename(columns={
                    'nombre': 'Comisión', 'total_integrantes': 'Integrantes', 'total_reuniones': 'Reuniones',
                }),
                use_container_width=True, hide_index=True, height=400
            )

        with col_detalle:
            if not df_com_filtrado.empty:
                nombres_com = df_com_filtrado['nombre'].tolist()
                seleccionada = st.selectbox("Seleccionar comisión", nombres_com, key="com_sel")
                row = df_com_filtrado[df_com_filtrado['nombre'] == seleccionada].iloc[0]
                comision_id = int(row['id'])

                st.markdown(f"### {seleccionada}")
                
                col_c1, col_c2 = st.columns(2)
                col_c1.metric("Integrantes", int(row['total_integrantes']))
                col_c2.metric("Reuniones", int(row['total_reuniones']))

                sub_tabs = st.tabs(["Integrantes", "Reuniones"])

                with sub_tabs[0]:
                    df_int = cargar_integrantes(comision_id)
                    if df_int.empty:
                        st.info("Sin integrantes registrados.")
                    else:
                        st.dataframe(
                            df_int[['cargo', 'nombre_raw', 'bloque']].rename(columns={
                                'cargo': 'Cargo', 'nombre_raw': 'Nombre', 'bloque': 'Bloque'
                            }),
                            use_container_width=True, hide_index=True
                        )

                with sub_tabs[1]:
                    df_reu = cargar_reuniones(comision_id)
                    if df_reu.empty:
                        st.info("Sin reuniones registradas.")
                    else:
                        st.dataframe(
                            df_reu[['fecha', 'tipo', 'descripcion']].rename(columns={
                                'fecha': 'Fecha', 'tipo': 'Tipo', 'descripcion': 'Descripción'
                            }),
                            use_container_width=True, hide_index=True
                        )
