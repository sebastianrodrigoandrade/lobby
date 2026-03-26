# -*- coding: utf-8 -*-
"""
Lobby - Página de Alertas
Detección automática de anomalías patrimoniales
Diseñada para periodistas
"""
import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal
import urllib.parse

# ============================================
# FUNCIONES DE CARGA
# ============================================

@st.cache_data(ttl=3600)
def cargar_indicadores():
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT anio, ipc_acumulado as ipc FROM indicadores_anuales ORDER BY anio
        """))
        return {row[0]: float(row[1]) for row in result.fetchall()}
    finally:
        db.close()

@st.cache_data(ttl=3600)
def cargar_mediana_general():
    """Retorna la mediana de patrimonio del último año."""
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY patrimonio_neto) as mediana
            FROM ddjj_legisladores
            WHERE patrimonio_neto > 0 AND anio = 2024
        """))
        return float(result.scalar() or 0)
    finally:
        db.close()

@st.cache_data(ttl=3600)
def detectar_crecimiento_inusual(umbral_real=100):
    """
    Detecta legisladores cuyo patrimonio creció mucho más que la inflación.
    umbral_real: porcentaje de ganancia real para considerar alerta (ej: 100 = duplicó en términos reales)
    """
    db = SessionLocal()
    try:
        result = db.execute(text("""
            WITH datos AS (
                SELECT 
                    d.cuit,
                    d.funcionario_apellido_nombre as nombre,
                    CASE WHEN d.organismo ILIKE '%SENADO%' THEN 'Senadores' ELSE 'Diputados' END as camara,
                    l.bloque,
                    MAX(CASE WHEN d.anio = 2022 THEN d.patrimonio_neto END) as pat_2022,
                    MAX(CASE WHEN d.anio = 2024 THEN d.patrimonio_neto END) as pat_2024
                FROM ddjj_legisladores d
                LEFT JOIN legisladores l ON d.legislador_id = l.id
                WHERE d.patrimonio_neto > 0 AND d.anio IN (2022, 2024)
                GROUP BY d.cuit, d.funcionario_apellido_nombre, d.organismo, l.bloque
                HAVING COUNT(DISTINCT d.anio) = 2
            ),
            inflacion AS (
                SELECT 
                    (SELECT ipc_acumulado FROM indicadores_anuales WHERE anio = 2024) /
                    (SELECT ipc_acumulado FROM indicadores_anuales WHERE anio = 2022) as ratio_ipc
            )
            SELECT 
                d.nombre, d.camara, d.bloque,
                d.pat_2022, d.pat_2024,
                ((d.pat_2024 / d.pat_2022) - 1) * 100 as var_nominal,
                (((d.pat_2024 / d.pat_2022) / i.ratio_ipc) - 1) * 100 as var_real,
                d.pat_2024 / d.pat_2022 as multiplicador
            FROM datos d, inflacion i
            WHERE d.pat_2022 > 0
              AND (((d.pat_2024 / d.pat_2022) / i.ratio_ipc) - 1) * 100 > :umbral
            ORDER BY var_real DESC
        """), {'umbral': umbral_real})
        
        df = pd.DataFrame(result.fetchall(), columns=[
            'nombre', 'camara', 'bloque', 'pat_2022', 'pat_2024', 'var_nominal', 'var_real', 'multiplicador'
        ])
        for col in ['pat_2022', 'pat_2024', 'var_nominal', 'var_real', 'multiplicador']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    finally:
        db.close()

@st.cache_data(ttl=3600)
def detectar_caida_patrimonial(umbral_nominal=0):
    """
    Detecta legisladores cuyo patrimonio bajó en términos nominales.
    """
    db = SessionLocal()
    try:
        result = db.execute(text("""
            WITH datos AS (
                SELECT 
                    d.cuit,
                    d.funcionario_apellido_nombre as nombre,
                    CASE WHEN d.organismo ILIKE '%SENADO%' THEN 'Senadores' ELSE 'Diputados' END as camara,
                    l.bloque,
                    MAX(CASE WHEN d.anio = 2022 THEN d.patrimonio_neto END) as pat_2022,
                    MAX(CASE WHEN d.anio = 2024 THEN d.patrimonio_neto END) as pat_2024
                FROM ddjj_legisladores d
                LEFT JOIN legisladores l ON d.legislador_id = l.id
                WHERE d.patrimonio_neto > 0 AND d.anio IN (2022, 2024)
                GROUP BY d.cuit, d.funcionario_apellido_nombre, d.organismo, l.bloque
                HAVING COUNT(DISTINCT d.anio) = 2
            )
            SELECT 
                nombre, camara, bloque,
                pat_2022, pat_2024,
                ((pat_2024 / pat_2022) - 1) * 100 as var_nominal
            FROM datos
            WHERE pat_2022 > 0
              AND ((pat_2024 / pat_2022) - 1) * 100 < :umbral
            ORDER BY var_nominal ASC
        """), {'umbral': umbral_nominal})
        
        df = pd.DataFrame(result.fetchall(), columns=[
            'nombre', 'camara', 'bloque', 'pat_2022', 'pat_2024', 'var_nominal'
        ])
        for col in ['pat_2022', 'pat_2024', 'var_nominal']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    finally:
        db.close()

@st.cache_data(ttl=3600)
def detectar_patrimonio_alto_nuevos(umbral_patrimonio=500000000):
    """
    Detecta legisladores nuevos con patrimonio alto.
    """
    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 
                d.funcionario_apellido_nombre as nombre,
                CASE WHEN d.organismo ILIKE '%SENADO%' THEN 'Senadores' ELSE 'Diputados' END as camara,
                l.bloque,
                l.mandato_hasta,
                d.patrimonio_neto,
                d.anio
            FROM ddjj_legisladores d
            JOIN legisladores l ON d.legislador_id = l.id
            WHERE d.patrimonio_neto > :umbral
              AND d.anio = 2024
              AND l.mandato_hasta >= CURRENT_DATE
              AND NOT EXISTS (
                  SELECT 1 FROM ddjj_legisladores d2 
                  WHERE d2.cuit = d.cuit AND d2.anio < 2023
              )
            ORDER BY d.patrimonio_neto DESC
        """), {'umbral': umbral_patrimonio})
        
        df = pd.DataFrame(result.fetchall(), columns=[
            'nombre', 'camara', 'bloque', 'mandato_hasta', 'patrimonio', 'anio'
        ])
        df['patrimonio'] = pd.to_numeric(df['patrimonio'], errors='coerce')
        return df
    finally:
        db.close()

@st.cache_data(ttl=3600)
def detectar_perdedores_inflacion():
    """
    Detecta legisladores que perdieron contra la inflación (var_real negativa).
    """
    db = SessionLocal()
    try:
        result = db.execute(text("""
            WITH datos AS (
                SELECT 
                    d.cuit,
                    d.funcionario_apellido_nombre as nombre,
                    CASE WHEN d.organismo ILIKE '%SENADO%' THEN 'Senadores' ELSE 'Diputados' END as camara,
                    l.bloque,
                    MAX(CASE WHEN d.anio = 2022 THEN d.patrimonio_neto END) as pat_2022,
                    MAX(CASE WHEN d.anio = 2024 THEN d.patrimonio_neto END) as pat_2024
                FROM ddjj_legisladores d
                LEFT JOIN legisladores l ON d.legislador_id = l.id
                WHERE d.patrimonio_neto > 0 AND d.anio IN (2022, 2024)
                GROUP BY d.cuit, d.funcionario_apellido_nombre, d.organismo, l.bloque
                HAVING COUNT(DISTINCT d.anio) = 2
            ),
            inflacion AS (
                SELECT 
                    (SELECT ipc_acumulado FROM indicadores_anuales WHERE anio = 2024) /
                    (SELECT ipc_acumulado FROM indicadores_anuales WHERE anio = 2022) as ratio_ipc
            )
            SELECT 
                d.nombre, d.camara, d.bloque,
                d.pat_2022, d.pat_2024,
                ((d.pat_2024 / d.pat_2022) - 1) * 100 as var_nominal,
                (((d.pat_2024 / d.pat_2022) / i.ratio_ipc) - 1) * 100 as var_real
            FROM datos d, inflacion i
            WHERE d.pat_2022 > 0
              AND (((d.pat_2024 / d.pat_2022) / i.ratio_ipc) - 1) * 100 < 0
            ORDER BY var_real ASC
        """))
        
        df = pd.DataFrame(result.fetchall(), columns=[
            'nombre', 'camara', 'bloque', 'pat_2022', 'pat_2024', 'var_nominal', 'var_real'
        ])
        for col in ['pat_2022', 'pat_2024', 'var_nominal', 'var_real']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    finally:
        db.close()

# ============================================
# FUNCIONES DE FORMATO
# ============================================

def fmt_pesos(valor):
    if pd.isna(valor) or valor is None:
        return "-"
    if valor >= 1_000_000_000:
        return f"${valor/1_000_000_000:,.1f}B"
    if valor >= 1_000_000:
        return f"${valor/1_000_000:,.0f}M"
    return f"${valor:,.0f}"

def fmt_pct(valor):
    if pd.isna(valor) or valor is None:
        return "-"
    return f"{valor:+,.1f}%"

def generar_tweet(texto):
    """Genera URL para compartir en Twitter/X."""
    base_url = "https://twitter.com/intent/tweet"
    params = {"text": texto}
    return f"{base_url}?{urllib.parse.urlencode(params)}"

def generar_whatsapp(texto):
    """Genera URL para compartir en WhatsApp."""
    return f"https://wa.me/?text={urllib.parse.quote(texto)}"

def boton_compartir(texto_tweet, key):
    """Muestra botones para compartir en redes."""
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        st.link_button("Compartir en X", generar_tweet(texto_tweet), use_container_width=True)
    with col2:
        st.link_button("WhatsApp", generar_whatsapp(texto_tweet), use_container_width=True)

# ============================================
# RENDER
# ============================================

def render():
    st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
    st.title("Alertas Patrimoniales")
    st.markdown("<div class='page-subtitle'>Deteccion automatica de anomalias en declaraciones juradas - Herramienta para periodistas</div>", unsafe_allow_html=True)
    
    # Info del período
    st.info("**Periodo analizado:** 2022-2024 | **Inflacion acumulada:** 493% | **Fuente:** Oficina Anticorrupcion")
    
    # Cargar mediana para contexto
    mediana = cargar_mediana_general()
    
    # Tabs para cada tipo de alerta
    tab1, tab2, tab3, tab4 = st.tabs([
        "Crecimiento inusual", 
        "Caida patrimonial",
        "Nuevos con alto patrimonio",
        "Perdieron vs inflacion"
    ])
    
    # ========================================
    # TAB 1: CRECIMIENTO INUSUAL
    # ========================================
    with tab1:
        st.markdown("### Patrimonios que crecieron mas que la inflacion")
        
        df = detectar_crecimiento_inusual(umbral_real=100)
        
        if not df.empty:
            # Resumen ejecutivo para periodistas
            top_nombre = df.iloc[0]['nombre']
            top_mult = df.iloc[0]['multiplicador']
            
            st.markdown(f'''
            <div style="background: linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%); padding: 1.2rem; border-radius: 12px; margin-bottom: 1rem; border-left: 4px solid #F59E0B;">
                <div style="font-size: 1.1rem; font-weight: 600; color: #92400E; margin-bottom: 0.5rem;">HALLAZGO PRINCIPAL</div>
                <div style="font-size: 1rem; color: #1F2937;">
                    <strong>{len(df)} legisladores</strong> multiplicaron su patrimonio en terminos reales entre 2022 y 2024, 
                    mientras la inflacion acumulada fue del 493%. El caso mas extremo es <strong>{top_nombre}</strong>, 
                    cuyo patrimonio se multiplico por <strong>{top_mult:.1f}x</strong>.
                </div>
            </div>
            ''', unsafe_allow_html=True)
            
            # Tweet sugerido
            tweet_resumen = f"DATOS: {len(df)} legisladores argentinos multiplicaron su patrimonio en terminos reales entre 2022-2024, pese a una inflacion del 493%. El caso mas extremo: {top_nombre} (x{top_mult:.0f}). Fuente: DDJJ Oficina Anticorrupcion via @LobbyApp"
            boton_compartir(tweet_resumen, "share_crecimiento")
            
            # Botón exportar
            st.download_button(
                "Descargar datos completos (CSV)",
                df.to_csv(index=False).encode('utf-8'),
                "alertas_crecimiento_inusual.csv",
                "text/csv",
                use_container_width=True
            )
            
            st.markdown("---")
            st.markdown(f"**{len(df)} casos detectados** (ordenados por crecimiento real)")
            
            for i, (_, row) in enumerate(df.iterrows()):
                veces_mediana = row['pat_2024'] / mediana if mediana > 0 else 0
                
                st.markdown(f'''
                <div style="background: white; border-left: 4px solid #F59E0B; padding: 1rem; margin-bottom: 0.5rem; border-radius: 0 8px 8px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <div style="font-weight: 600; font-size: 1.1rem; color: #1F2937;">{row['nombre']}</div>
                            <div style="color: #6B7280; font-size: 0.9rem;">{row['camara']} · {row['bloque'] or 'Sin bloque'}</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="color: #059669; font-weight: 700; font-size: 1.2rem;">+{row['var_real']:.0f}% real</div>
                            <div style="color: #6B7280; font-size: 0.8rem;">({fmt_pct(row['var_nominal'])} nominal)</div>
                        </div>
                    </div>
                    <div style="margin-top: 0.8rem; padding-top: 0.8rem; border-top: 1px solid #E5E7EB;">
                        <div style="display: flex; gap: 2rem; flex-wrap: wrap;">
                            <div>
                                <span style="color: #6B7280; font-size: 0.85rem;">2022:</span>
                                <span style="font-weight: 600;"> {fmt_pesos(row['pat_2022'])}</span>
                            </div>
                            <div>
                                <span style="color: #6B7280; font-size: 0.85rem;">2024:</span>
                                <span style="font-weight: 600;"> {fmt_pesos(row['pat_2024'])}</span>
                            </div>
                            <div style="background: #FEF3C7; padding: 0.2rem 0.5rem; border-radius: 4px;">
                                <span style="color: #92400E; font-weight: 600;">x{row['multiplicador']:.1f}</span>
                                <span style="color: #92400E; font-size: 0.85rem;"> en 2 anios</span>
                            </div>
                            <div style="background: #DBEAFE; padding: 0.2rem 0.5rem; border-radius: 4px;">
                                <span style="color: #1E40AF; font-size: 0.85rem;">{veces_mediana:.1f}x la mediana</span>
                            </div>
                        </div>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
                
                # Botón compartir individual
                tweet_individual = f"{row['nombre']} ({row['camara']}) multiplico su patrimonio por {row['multiplicador']:.1f}x entre 2022-2024: de {fmt_pesos(row['pat_2022'])} a {fmt_pesos(row['pat_2024'])}. Fuente: DDJJ Oficina Anticorrupcion"
                with st.expander(f"Compartir caso de {row['nombre'].split()[0]}"):
                    boton_compartir(tweet_individual, f"share_crec_{i}")
        else:
            st.success("No se detectaron alertas de crecimiento inusual.")
    
    # ========================================
    # TAB 2: CAIDA PATRIMONIAL
    # ========================================
    with tab2:
        st.markdown("### Patrimonios que bajaron en terminos nominales")
        st.caption("Con inflacion del 493%, una caida nominal es muy inusual")
        
        df = detectar_caida_patrimonial(umbral_nominal=0)
        
        if not df.empty:
            st.markdown(f'''
            <div style="background: linear-gradient(135deg, #FEE2E2 0%, #FECACA 100%); padding: 1.2rem; border-radius: 12px; margin-bottom: 1rem; border-left: 4px solid #DC2626;">
                <div style="font-size: 1.1rem; font-weight: 600; color: #991B1B; margin-bottom: 0.5rem;">HALLAZGO PRINCIPAL</div>
                <div style="font-size: 1rem; color: #1F2937;">
                    <strong>{len(df)} legisladores</strong> declararon <strong>menos patrimonio</strong> en 2024 que en 2022, 
                    pese a una inflacion del 493%. Esto podria indicar ventas de activos, donaciones, 
                    o posibles inconsistencias en las declaraciones.
                </div>
            </div>
            ''', unsafe_allow_html=True)
            
            tweet_resumen = f"ALERTA: {len(df)} legisladores argentinos declararon MENOS patrimonio en 2024 que en 2022, pese a inflacion del 493%. Fuente: DDJJ Oficina Anticorrupcion via @LobbyApp"
            boton_compartir(tweet_resumen, "share_caida")
            
            st.download_button(
                "Descargar datos completos (CSV)",
                df.to_csv(index=False).encode('utf-8'),
                "alertas_caida_patrimonial.csv",
                "text/csv",
                use_container_width=True
            )
            
            st.markdown("---")
            
            for i, (_, row) in enumerate(df.iterrows()):
                st.markdown(f'''
                <div style="background: white; border-left: 4px solid #DC2626; padding: 1rem; margin-bottom: 0.5rem; border-radius: 0 8px 8px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <div style="font-weight: 600; font-size: 1.1rem;">{row['nombre']}</div>
                            <div style="color: #6B7280; font-size: 0.9rem;">{row['camara']} · {row['bloque'] or 'Sin bloque'}</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="color: #DC2626; font-weight: 700; font-size: 1.2rem;">{fmt_pct(row['var_nominal'])}</div>
                        </div>
                    </div>
                    <div style="margin-top: 0.5rem; font-size: 0.9rem; color: #6B7280;">
                        2022: {fmt_pesos(row['pat_2022'])} → 2024: {fmt_pesos(row['pat_2024'])}
                    </div>
                </div>
                ''', unsafe_allow_html=True)
        else:
            st.success("No se detectaron caidas patrimoniales nominales.")
    
    # ========================================
    # TAB 3: NUEVOS CON ALTO PATRIMONIO
    # ========================================
    with tab3:
        st.markdown("### Legisladores nuevos con patrimonio elevado")
        st.caption("Ingresaron al Congreso desde 2023 y declaran patrimonio superior a $500M")
        
        df = detectar_patrimonio_alto_nuevos(umbral_patrimonio=500_000_000)
        
        if not df.empty:
            top = df.iloc[0]
            
            st.markdown(f'''
            <div style="background: linear-gradient(135deg, #DBEAFE 0%, #BFDBFE 100%); padding: 1.2rem; border-radius: 12px; margin-bottom: 1rem; border-left: 4px solid #2563EB;">
                <div style="font-size: 1.1rem; font-weight: 600; color: #1E40AF; margin-bottom: 0.5rem;">HALLAZGO PRINCIPAL</div>
                <div style="font-size: 1rem; color: #1F2937;">
                    <strong>{len(df)} legisladores nuevos</strong> (mandato desde 2023) declaran patrimonios superiores a $500 millones. 
                    El mayor es <strong>{top['nombre']}</strong> con <strong>{fmt_pesos(top['patrimonio'])}</strong>.
                </div>
            </div>
            ''', unsafe_allow_html=True)
            
            tweet_resumen = f"{len(df)} legisladores nuevos en el Congreso argentino declaran patrimonios de mas de $500M. El mayor: {top['nombre']} con {fmt_pesos(top['patrimonio'])}. Fuente: DDJJ Oficina Anticorrupcion via @LobbyApp"
            boton_compartir(tweet_resumen, "share_nuevos")
            
            st.download_button(
                "Descargar datos completos (CSV)",
                df.to_csv(index=False).encode('utf-8'),
                "alertas_nuevos_alto_patrimonio.csv",
                "text/csv",
                use_container_width=True
            )
            
            st.markdown("---")
            
            for i, (_, row) in enumerate(df.iterrows()):
                veces_mediana = row['patrimonio'] / mediana if mediana > 0 else 0
                
                st.markdown(f'''
                <div style="background: white; border-left: 4px solid #2563EB; padding: 1rem; margin-bottom: 0.5rem; border-radius: 0 8px 8px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <div style="font-weight: 600; font-size: 1.1rem;">{row['nombre']}</div>
                            <div style="color: #6B7280; font-size: 0.9rem;">{row['camara']} · {row['bloque'] or 'Sin bloque'}</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="color: #2563EB; font-weight: 700; font-size: 1.2rem;">{fmt_pesos(row['patrimonio'])}</div>
                            <div style="background: #DBEAFE; padding: 0.2rem 0.5rem; border-radius: 4px; margin-top: 0.3rem;">
                                <span style="color: #1E40AF; font-size: 0.85rem;">{veces_mediana:.0f}x la mediana</span>
                            </div>
                        </div>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
        else:
            st.info("No se detectaron legisladores nuevos con patrimonio superior al umbral.")
    
    # ========================================
    # TAB 4: PERDIERON VS INFLACION
    # ========================================
    with tab4:
        st.markdown("### Legisladores que perdieron poder adquisitivo")
        st.caption("Su patrimonio crecio menos que la inflacion (493%)")
        
        df = detectar_perdedores_inflacion()
        
        if not df.empty:
            peor = df.iloc[0]
            
            st.markdown(f'''
            <div style="background: linear-gradient(135deg, #FFF7ED 0%, #FFEDD5 100%); padding: 1.2rem; border-radius: 12px; margin-bottom: 1rem; border-left: 4px solid #EA580C;">
                <div style="font-size: 1.1rem; font-weight: 600; color: #C2410C; margin-bottom: 0.5rem;">CONTEXTO</div>
                <div style="font-size: 1rem; color: #1F2937;">
                    <strong>{len(df)} legisladores</strong> declararon patrimonios que crecieron menos que la inflacion (493%), 
                    perdiendo poder adquisitivo. El caso mas extremo es <strong>{peor['nombre']}</strong> 
                    con una perdida real del <strong>{peor['var_real']:.1f}%</strong>.
                </div>
            </div>
            ''', unsafe_allow_html=True)
            
            st.download_button(
                "Descargar datos completos (CSV)",
                df.to_csv(index=False).encode('utf-8'),
                "alertas_perdieron_inflacion.csv",
                "text/csv",
                use_container_width=True
            )
            
            st.markdown("---")
            st.markdown(f"**Mostrando los 20 casos mas extremos** de {len(df)} total")
            
            for _, row in df.head(20).iterrows():
                color_bg = "#FEF2F2" if row['var_real'] < -50 else "#FFF7ED"
                color_border = "#DC2626" if row['var_real'] < -50 else "#EA580C"
                
                st.markdown(f'''
                <div style="background: {color_bg}; border-left: 4px solid {color_border}; padding: 0.8rem 1rem; margin-bottom: 0.4rem; border-radius: 0 8px 8px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <span style="font-weight: 600;">{row['nombre']}</span>
                            <span style="color: #6B7280; font-size: 0.85rem;"> · {row['camara']}</span>
                        </div>
                        <div style="color: #DC2626; font-weight: 600;">{fmt_pct(row['var_real'])} real</div>
                    </div>
                </div>
                ''', unsafe_allow_html=True)
            
            if len(df) > 20:
                st.caption(f"... y {len(df) - 20} casos mas en el CSV")
        else:
            st.success("Todos los legisladores superaron la inflacion.")
    
    # ========================================
    # METODOLOGIA
    # ========================================
    st.markdown("---")
    with st.expander("Metodologia y fuentes"):
        st.markdown("""
        **Fuentes de datos:**
        - Declaraciones Juradas Patrimoniales Integrales - Oficina Anticorrupcion (datos.jus.gob.ar)
        - Indice de Precios al Consumidor (IPC) - INDEC
        
        **Calculos:**
        - **Variacion nominal:** (Patrimonio 2024 / Patrimonio 2022 - 1) x 100
        - **Variacion real:** ((1 + var_nominal) / (1 + inflacion)) - 1
        - **Inflacion acumulada 2022-2024:** 493% (IPC INDEC)
        
        **Criterios de alerta:**
        - *Crecimiento inusual:* Variacion real > 100% (duplico patrimonio en terminos reales)
        - *Caida patrimonial:* Variacion nominal < 0% (bajo el monto declarado)
        - *Nuevos con alto patrimonio:* Sin DDJJ previas a 2023 y patrimonio > $500M
        
        **Limitaciones:**
        - Solo se comparan legisladores con DDJJ en ambos periodos (2022 y 2024)
        - No hay datos de 2023 disponibles
        - No se detectan omisiones o inconsistencias dentro de una misma DDJJ
        - El patrimonio declarado puede diferir del patrimonio real
        
        **Contacto:**
        Si encontras errores o tenes sugerencias, escribinos a [contacto]
        """)
    
    st.markdown("""
    <div style="text-align: center; color: #9CA3AF; font-size: 0.85rem; margin-top: 2rem;">
        Datos publicos procesados por Lobby · Plataforma de Inteligencia Publica
    </div>
    """, unsafe_allow_html=True)