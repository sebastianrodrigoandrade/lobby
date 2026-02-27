import re
import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal
from src.styles import apply_styles, show_logo
show_logo()
apply_styles()

st.set_page_config(page_title="Comisiones — Lobby", layout="wide")

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
    "cmtyprevisionales": "Sistemas, Medios de Comunicación y Libertad de Expresión",
    "cpydhumano": "Población y Desarrollo Humano",
    "cdeportes": "Deportes",
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

MESES = {'enero','febrero','marzo','abril','mayo','junio','julio','agosto',
         'septiembre','octubre','noviembre','diciembre'}

def limpiar_encoding(texto):
    reemplazos = {
        '¾': 'ó', 'ß': 'á', '±': 'ñ', 'Ý': 'í',
        '┴': 'Á', 'É': 'É', 'Ú': 'Ú',
    }
    for mal, bien in reemplazos.items():
        texto = texto.replace(mal, bien)
    return texto

def extraer_nombres_propios(frase):
    frase = limpiar_encoding(frase)
    nombres = []

    patron_titulo = re.compile(
        r'(?:Dr\.|Dra\.|Lic\.|Mg\.|Ing\.|Sr\.|Sra\.|Prof\.)\s*'
        r'([A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]+(?:\s+[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]+){1,3})'
    )
    patron_cargo = re.compile(
        r'(?:diputad[oa]|senad[oa]r[a]?)\s+'
        r'([A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]+(?:\s+[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]+){1,3})',
        re.IGNORECASE
    )

    for m in patron_titulo.finditer(frase):
        nombre = m.group(1).strip()
        if nombre.lower() not in MESES:
            nombres.append(nombre)

    for m in patron_cargo.finditer(frase):
        nombre = m.group(1).strip()
        if nombre.lower() not in MESES and nombre not in nombres:
            nombres.append(nombre)

    return nombres

def extraer_invitados(texto):
    if not texto:
        return '—'
    todos_nombres = []
    todos_genericos = []
    for frase in texto.split(' | '):
        frase_lower = frase.lower()
        nombres = extraer_nombres_propios(frase)
        todos_nombres.extend(nombres)
        if not nombres:
            if 'especialistas' in frase_lower:
                todos_genericos.append('Especialistas')
            elif 'organizaciones' in frase_lower or 'ong' in frase_lower:
                todos_genericos.append('ONGs')
            elif 'expertos' in frase_lower:
                todos_genericos.append('Expertos')
            elif 'funcionarios' in frase_lower:
                todos_genericos.append('Funcionarios')
            elif 'familiares' in frase_lower:
                todos_genericos.append('Familiares')
    unicos_nombres = list(dict.fromkeys(todos_nombres))
    unicos_genericos = list(dict.fromkeys(todos_genericos))
    resultado = unicos_nombres[:5] + [g for g in unicos_genericos if g not in unicos_nombres]
    return ', '.join(resultado[:6]) if resultado else '—'


@st.cache_data(ttl=3600)
def cargar_comisiones():
    db = SessionLocal()
    result = db.execute(text("""
        SELECT c.id, c.slug,
               COUNT(DISTINCT ci.id) as total_integrantes,
               COUNT(DISTINCT cr.id) as total_reuniones,
               COUNT(DISTINCT CASE WHEN cr.tipo = 'INVITADO' THEN cr.id END) as reuniones_con_invitados,
               STRING_AGG(DISTINCT CASE WHEN cr.tipo = 'INVITADO' THEN cr.descripcion END, ' | ') as invitados_raw
        FROM comisiones c
        LEFT JOIN comision_integrantes ci ON ci.comision_id = c.id
        LEFT JOIN comision_reuniones cr ON cr.comision_id = c.id
        GROUP BY c.id, c.slug
        ORDER BY c.slug
    """))
    df = pd.DataFrame(result.fetchall(), columns=result.keys())
    db.close()
    df['nombre'] = df['slug'].map(NOMBRES_COMISIONES).fillna(df['slug'])
    df['invitados'] = df['invitados_raw'].apply(extraer_invitados)
    return df

@st.cache_data(ttl=3600)
def cargar_integrantes(comision_id):
    db = SessionLocal()
    result = db.execute(text("""
        SELECT ci.cargo, ci.nombre_raw, ci.bloque, ci.distrito, ci.legislador_id
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


# ---------------------------------------------------------
st.title("Comisiones")
st.markdown("<div class='page-subtitle'>Cámara de Diputados · Comisiones Permanentes</div>", unsafe_allow_html=True)

df_com = cargar_comisiones()

col1, col2, col3 = st.columns(3)
col1.metric("Comisiones permanentes", len(df_com))
col2.metric("Total reuniones", int(df_com['total_reuniones'].sum()))
col3.metric("Reuniones c/ invitados externos", int(df_com['reuniones_con_invitados'].sum()))

st.divider()

st.subheader("Todas las comisiones")
st.dataframe(
    df_com[['nombre', 'total_integrantes', 'total_reuniones', 'reuniones_con_invitados', 'invitados']].rename(columns={
        'nombre': 'Comisión',
        'total_integrantes': 'Integrantes',
        'total_reuniones': 'Reuniones',
        'reuniones_con_invitados': 'Reuniones c/ invitados',
        'invitados': 'Invitados registrados',
    }),
    use_container_width=True,
    hide_index=True
)

st.divider()

st.subheader("Detalle de comisión")

nombres_opciones = df_com['nombre'].tolist()
busqueda = st.text_input("Buscar comisión", placeholder="Ej: Justicia, Presupuesto, Trabajo...")
if busqueda:
    nombres_opciones = [n for n in nombres_opciones if busqueda.lower() in n.lower()]

if not nombres_opciones:
    st.info("No se encontró la comisión.")
    st.stop()

seleccionada = st.selectbox("Seleccionar comisión", nombres_opciones)
row = df_com[df_com['nombre'] == seleccionada].iloc[0]
comision_id = int(row['id'])

col1, col2, col3 = st.columns(3)
col1.metric("Integrantes", int(row['total_integrantes']))
col2.metric("Reuniones", int(row['total_reuniones']))
col3.metric("Reuniones c/ invitados", int(row['reuniones_con_invitados']))

tabs = st.tabs(["Integrantes", "Reuniones"])

with tabs[0]:
    df_int = cargar_integrantes(comision_id)
    if df_int.empty:
        st.info("Esta comisión aún no tiene integrantes registrados — composición pendiente de constitución formal.")
    else:
        autoridades = df_int[df_int['cargo'] != 'VOCAL']
        vocales = df_int[df_int['cargo'] == 'VOCAL']
        if not autoridades.empty:
            st.markdown("**Autoridades**")
            st.dataframe(
                autoridades[['cargo', 'nombre_raw', 'bloque', 'distrito']].rename(columns={
                    'cargo': 'Cargo', 'nombre_raw': 'Nombre',
                    'bloque': 'Bloque', 'distrito': 'Distrito',
                }),
                use_container_width=True, hide_index=True
            )
        if not vocales.empty:
            st.markdown("**Vocales**")
            st.dataframe(
                vocales[['nombre_raw', 'bloque', 'distrito']].rename(columns={
                    'nombre_raw': 'Nombre', 'bloque': 'Bloque', 'distrito': 'Distrito',
                }),
                use_container_width=True, hide_index=True
            )

with tabs[1]:
    df_reu = cargar_reuniones(comision_id)
    if df_reu.empty:
        st.info("No hay reuniones registradas.")
    else:
        solo_invitados = st.checkbox("Mostrar solo reuniones con invitados externos")
        df_mostrar = df_reu[df_reu['tipo'] == 'INVITADO'] if solo_invitados else df_reu
        st.markdown(f"**{len(df_mostrar)} reuniones**")
        st.dataframe(
            df_mostrar[['fecha', 'tipo', 'descripcion']].rename(columns={
                'fecha': 'Fecha', 'tipo': 'Tipo', 'descripcion': 'Descripción',
            }),
            use_container_width=True, hide_index=True
        )