# -*- coding: utf-8 -*-
"""
Lobby - Página de Alertas
Detección automática de anomalías patrimoniales
"""
import streamlit as st
import pandas as pd
from sqlalchemy import text
from src.database import SessionLocal

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
                (((d.pat_2024 / d.pat_2022) / i.ratio_ipc) - 1) * 100 as var_real
            FROM datos d, inflacion i
            WHERE d.pat_2022 > 0
              AND (((d.pat_2024 / d.pat_2022) / i.ratio_ipc) - 1) * 100 > :umbral
            ORDER BY var_real DESC
        """), {'umbral': umbral_real})
        
        df = pd.DataFrame(result.fetchall(), columns=[
            'nombre', 'camara', 'bloque', 'pat_2022', 'pat_2024', 'var_nominal', 'var_real'
        ])
        for col in ['pat_2022', 'pat_2024', 'var_nominal', 'var_real']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    finally:
        db.close()

@st.cache_data(ttl=3600)
def detectar_caida_patrimonial(umbral_nominal=-20):
    """
    Detecta legisladores cuyo patrimonio bajó en términos nominales.
    umbral_nominal: porcentaje de caída nominal (ej: -20 = bajó 20% o más)
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
def detectar_patrimonio_alto_nuevos(umbral_patrimonio=500000000, anio_inicio_min=2023):
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
        return f"${valor/1_000_000:,.1f}M"
    return f"${valor:,.0f}"

def fmt_pct(valor):
    if pd.isna(valor) or valor is None:
        return "-"
    return f"{valor:+,.1f}%"

# ============================================
# RENDER
# ============================================

def render():
    st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
    st.title("��� Alertas Patrimoniales")
    st.markdown("<div class='page-subtitle'>Detección automática de anomalías en declaraciones juradas</div>", unsafe_allow_html=True)
    
    # Info del período
    st.info("��� **Período analizado:** 2022-2024 | **Inflación acumulada:** 493%")
    
    # Tabs para cada tipo de alerta
    tab1, tab2, tab3, tab4 = st.tabs([
        " Crecimiento inusual", 
        " Caída patrimonial",
        " Nuevos con alto patrimonio",
        " Perdieron vs inflación"
    ])
    
    with tab1:
        st.markdown("### Legisladores con crecimiento muy superior a la inflación")
        st.caption("Patrimonio creció más del doble en términos reales (descontando inflación)")
        
        df = detectar_crecimiento_inusual(umbral_real=100)
        
        if not df.empty:
            st.metric("Alertas detectadas", len(df))
            
            for _, row in df.iterrows():
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"""
                    <div style='background: #FEF3C7; border-left: 4px solid #F59E0B; padding: 1rem; margin-bottom: 0.5rem; border-radius: 0 8px 8px 0;'>
                        <div style='font-weight: 600; font-size: 1.1rem;'>{row['nombre']}</div>
                        <div style='color: #6B7280; font-size: 0.9rem;'>{row['camara']} · {row['bloque'] or '-'}</div>
                        <div style='margin-top: 0.5rem;'>
                            <span style='color: #059669; font-weight: 600;'>Var. real: {fmt_pct(row['var_real'])}</span>
                            <span style='color: #6B7280;'> (nominal: {fmt_pct(row['var_nominal'])})</span>
                        </div>
                        <div style='font-size: 0.85rem; color: #6B7280;'>
                            2022: {fmt_pesos(row['pat_2022'])} → 2024: {fmt_pesos(row['pat_2024'])}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.success("No se detectaron alertas de crecimiento inusual.")
    
    with tab2:
        st.markdown("### Legisladores con caída patrimonial nominal")
        st.caption("El patrimonio declarado bajó respecto al período anterior (muy inusual con alta inflación)")
        
        df = detectar_caida_patrimonial(umbral_nominal=0)
        
        if not df.empty:
            st.metric("Alertas detectadas", len(df))
            
            for _, row in df.iterrows():
                st.markdown(f"""
                <div style='background: #FEE2E2; border-left: 4px solid #DC2626; padding: 1rem; margin-bottom: 0.5rem; border-radius: 0 8px 8px 0;'>
                    <div style='font-weight: 600; font-size: 1.1rem;'>{row['nombre']}</div>
                    <div style='color: #6B7280; font-size: 0.9rem;'>{row['camara']} · {row['bloque'] or '-'}</div>
                    <div style='margin-top: 0.5rem;'>
                        <span style='color: #DC2626; font-weight: 600;'>Var. nominal: {fmt_pct(row['var_nominal'])}</span>
                    </div>
                    <div style='font-size: 0.85rem; color: #6B7280;'>
                        2022: {fmt_pesos(row['pat_2022'])} → 2024: {fmt_pesos(row['pat_2024'])}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("No se detectaron caídas patrimoniales nominales.")
    
    with tab3:
        st.markdown("### Legisladores nuevos con patrimonio elevado")
        st.caption("Ingresaron al Congreso recientemente y declaran patrimonio superior a $500M")
        
        df = detectar_patrimonio_alto_nuevos(umbral_patrimonio=500_000_000)
        
        if not df.empty:
            st.metric("Alertas detectadas", len(df))
            
            for _, row in df.iterrows():
                st.markdown(f"""
                <div style='background: #DBEAFE; border-left: 4px solid #2563EB; padding: 1rem; margin-bottom: 0.5rem; border-radius: 0 8px 8px 0;'>
                    <div style='font-weight: 600; font-size: 1.1rem;'>{row['nombre']}</div>
                    <div style='color: #6B7280; font-size: 0.9rem;'>{row['camara']} · {row['bloque'] or '-'}</div>
                    <div style='margin-top: 0.5rem;'>
                        <span style='color: #2563EB; font-weight: 600;'>Patrimonio: {fmt_pesos(row['patrimonio'])}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No se detectaron legisladores nuevos con patrimonio superior al umbral.")
    
    with tab4:
        st.markdown("### Legisladores que perdieron contra la inflación")
        st.caption("Su patrimonio creció menos que la inflación (perdieron poder adquisitivo)")
        
        df = detectar_perdedores_inflacion()
        
        if not df.empty:
            st.metric("Total", len(df))
            st.caption(f"De {len(df)} legisladores con datos 2022-2024, estos perdieron poder adquisitivo")
            
            # Mostrar solo los 20 que más perdieron
            for _, row in df.head(20).iterrows():
                color_bg = "#FEF2F2" if row['var_real'] < -50 else "#FFF7ED"
                color_border = "#DC2626" if row['var_real'] < -50 else "#F97316"
                
                st.markdown(f"""
                <div style='background: {color_bg}; border-left: 4px solid {color_border}; padding: 0.8rem 1rem; margin-bottom: 0.4rem; border-radius: 0 8px 8px 0;'>
                    <div style='display: flex; justify-content: space-between; align-items: center;'>
                        <div>
                            <span style='font-weight: 600;'>{row['nombre']}</span>
                            <span style='color: #6B7280; font-size: 0.85rem;'> · {row['camara']}</span>
                        </div>
                        <div style='color: #DC2626; font-weight: 600;'>{fmt_pct(row['var_real'])} real</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            
            if len(df) > 20:
                st.caption(f"... y {len(df) - 20} más")
        else:
            st.success("Todos los legisladores superaron la inflación.")
    
    # Metodología
    st.markdown("---")
    with st.expander(" Metodología"):
        st.markdown("""
        **Fuentes de datos:**
        - Declaraciones Juradas Patrimoniales Integrales de la Oficina Anticorrupción
        - Índice de Precios al Consumidor (IPC) del INDEC
        
        **Cálculos:**
        - **Variación nominal:** (Patrimonio 2024 / Patrimonio 2022 - 1) × 100
        - **Variación real:** (Variación nominal / Inflación acumulada) - 1
        - **Inflación acumulada 2022-2024:** 493%
        
        **Criterios de alerta:**
        - *Crecimiento inusual:* Variación real > 100% (duplicó patrimonio en términos reales)
        - *Caída patrimonial:* Variación nominal < 0% (bajó el monto declarado)
        - *Nuevos con alto patrimonio:* Sin DDJJ previas a 2023 y patrimonio > $500M
        
        **Limitaciones:**
        - Solo se comparan legisladores con DDJJ en ambos períodos
        - No se detectan omisiones o inconsistencias dentro de una misma DDJJ
        - El patrimonio declarado puede diferir del patrimonio real
        """)
