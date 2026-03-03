# -*- coding: utf-8 -*-
"""
Crea tablas e ingesta indicadores economicos: tipo de cambio, IPC, RIPTE
Fuentes: BCRA, INDEC, APIs publicas
"""
import pandas as pd
import requests
from datetime import datetime
from sqlalchemy import text
from dotenv import load_dotenv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.database import SessionLocal

load_dotenv()

def crear_tablas(db):
    """Crea las tablas de indicadores si no existen."""
    
    # Tabla de tipo de cambio
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS tipo_cambio (
            id SERIAL PRIMARY KEY,
            fecha DATE NOT NULL UNIQUE,
            dolar_oficial NUMERIC(12,2),
            dolar_blue NUMERIC(12,2),
            dolar_mep NUMERIC(12,2),
            fuente VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    # Tabla de IPC
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS ipc_mensual (
            id SERIAL PRIMARY KEY,
            anio INT NOT NULL,
            mes INT NOT NULL,
            indice NUMERIC(12,4),
            variacion_mensual NUMERIC(8,4),
            variacion_interanual NUMERIC(8,4),
            fuente VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(anio, mes)
        )
    """))
    
    # Tabla de RIPTE
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS ripte (
            id SERIAL PRIMARY KEY,
            anio INT NOT NULL,
            mes INT NOT NULL,
            valor NUMERIC(12,2),
            variacion_mensual NUMERIC(8,4),
            variacion_interanual NUMERIC(8,4),
            fuente VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(anio, mes)
        )
    """))
    
    # Tabla de indicadores anuales (para comparacion simplificada)
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS indicadores_anuales (
            id SERIAL PRIMARY KEY,
            anio INT NOT NULL UNIQUE,
            dolar_promedio NUMERIC(12,2),
            dolar_fin_anio NUMERIC(12,2),
            ipc_acumulado NUMERIC(10,4),
            ripte_promedio NUMERIC(12,2),
            inflacion_anual NUMERIC(8,4),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """))
    
    db.commit()
    print("Tablas de indicadores creadas.")

def ingestar_tipo_cambio_manual(db):
    """Ingesta tipo de cambio con datos historicos conocidos."""
    
    # Datos de dolar oficial promedio anual (fuente: BCRA)
    datos_dolar = [
        # (anio, mes, dia, oficial, blue, mep)
        # Fin de cada año - valores aproximados de referencia
        (2019, 12, 31, 59.89, 72.0, 75.0),
        (2020, 12, 31, 84.15, 166.0, 145.0),
        (2021, 12, 31, 102.75, 207.0, 197.0),
        (2022, 12, 31, 177.16, 346.0, 332.0),
        (2023, 12, 31, 808.45, 1025.0, 985.0),
        (2024, 12, 31, 1032.0, 1180.0, 1150.0),  # Estimado
    ]
    
    for anio, mes, dia, oficial, blue, mep in datos_dolar:
        fecha = f"{anio}-{mes:02d}-{dia:02d}"
        db.execute(text("""
            INSERT INTO tipo_cambio (fecha, dolar_oficial, dolar_blue, dolar_mep, fuente)
            VALUES (:fecha, :oficial, :blue, :mep, 'manual')
            ON CONFLICT (fecha) DO UPDATE SET
                dolar_oficial = :oficial,
                dolar_blue = :blue,
                dolar_mep = :mep
        """), {
            'fecha': fecha,
            'oficial': oficial,
            'blue': blue,
            'mep': mep
        })
    
    db.commit()
    print(f"Tipo de cambio: {len(datos_dolar)} registros insertados")

def ingestar_indicadores_anuales(db):
    """Ingesta indicadores anuales consolidados para comparacion."""
    
    # Datos consolidados por año
    # Fuentes: INDEC, BCRA, datos publicos
    indicadores = [
        # (anio, dolar_prom, dolar_fin, ipc_acum, ripte_prom, inflacion_anual)
        (2019, 48.24, 59.89, 100.0, 45000, 53.8),
        (2020, 70.58, 84.15, 136.1, 52000, 36.1),
        (2021, 95.13, 102.75, 206.3, 72000, 50.9),
        (2022, 130.79, 177.16, 401.4, 120000, 94.8),
        (2023, 288.17, 808.45, 1241.9, 280000, 211.4),
        (2024, 920.0, 1032.0, 2380.0, 580000, 118.8),  # Estimado
    ]
    
    for anio, dolar_prom, dolar_fin, ipc_acum, ripte_prom, inflacion in indicadores:
        db.execute(text("""
            INSERT INTO indicadores_anuales 
            (anio, dolar_promedio, dolar_fin_anio, ipc_acumulado, ripte_promedio, inflacion_anual)
            VALUES (:anio, :dolar_prom, :dolar_fin, :ipc, :ripte, :inflacion)
            ON CONFLICT (anio) DO UPDATE SET
                dolar_promedio = :dolar_prom,
                dolar_fin_anio = :dolar_fin,
                ipc_acumulado = :ipc,
                ripte_promedio = :ripte,
                inflacion_anual = :inflacion
        """), {
            'anio': anio,
            'dolar_prom': dolar_prom,
            'dolar_fin': dolar_fin,
            'ipc': ipc_acum,
            'ripte': ripte_prom,
            'inflacion': inflacion
        })
    
    db.commit()
    print(f"Indicadores anuales: {len(indicadores)} registros insertados")

def intentar_api_bcra(db):
    """Intenta obtener datos del BCRA via API."""
    try:
        # API publica del BCRA para tipo de cambio
        url = "https://api.bcra.gob.ar/estadisticas/v2.0/principalesvariables"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print("API BCRA disponible - datos obtenidos")
            return data
    except Exception as e:
        print(f"API BCRA no disponible: {e}")
    return None

def main():
    db = SessionLocal()
    
    print("=" * 60)
    print("INGESTA DE INDICADORES ECONOMICOS")
    print("=" * 60)
    
    # 1. Crear tablas
    print("\n1. Creando tablas...")
    crear_tablas(db)
    
    # 2. Intentar API BCRA
    print("\n2. Consultando APIs...")
    intentar_api_bcra(db)
    
    # 3. Ingestar datos manuales
    print("\n3. Ingresando datos historicos...")
    ingestar_tipo_cambio_manual(db)
    ingestar_indicadores_anuales(db)
    
    # 4. Mostrar resumen
    print("\n" + "=" * 60)
    print("RESUMEN DE INDICADORES:")
    
    result = db.execute(text("SELECT COUNT(*) FROM tipo_cambio"))
    print(f"  Tipo de cambio: {result.scalar()} registros")
    
    result = db.execute(text("SELECT COUNT(*) FROM indicadores_anuales"))
    print(f"  Indicadores anuales: {result.scalar()} registros")
    
    print("\nIndicadores anuales cargados:")
    result = db.execute(text("""
        SELECT anio, dolar_fin_anio, inflacion_anual 
        FROM indicadores_anuales ORDER BY anio
    """))
    for r in result:
        print(f"  {r[0]}: USD {r[1]:.2f} | Inflacion {r[2]:.1f}%")
    
    db.close()
    print("\nProceso completado.")

if __name__ == "__main__":
    main()