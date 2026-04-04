# -*- coding: utf-8 -*-
"""
Scrapear asistencia de sesiones del Senado desde diarios de sesiones PDF.
"""
import requests
import pdfplumber
import re
import os
import time
from io import BytesIO
from bs4 import BeautifulSoup
from datetime import datetime
from sqlalchemy import text, create_engine
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DATABASE_URL = f'postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?sslmode=require'


def obtener_sesiones(anio):
    """Obtiene lista de sesiones de un año."""
    url = "https://www.senado.gob.ar/parlamentario/sesiones/busquedaTac"
    
    # POST con el año
    data = {
        'busqueda_proyectos[ordenDelDiaPeriodoTac]': str(anio)
    }
    
    response = requests.post(url, data=data, timeout=30)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    sesiones = []
    
    # Buscar links a diarios
    for link in soup.find_all('a', href=True):
        href = link['href']
        if '/descargarDiario' in href:
            # Extraer ID de sesión
            match = re.search(r'/parlamentario/sesiones/(\d+)/descargarDiario', href)
            if match:
                sesion_id = match.group(1)
                sesiones.append({
                    'id': sesion_id,
                    'url': f"https://www.senado.gob.ar{href}"
                })
    
    return sesiones


def extraer_asistencia_pdf(pdf_content):
    """Extrae asistencia de un PDF en memoria."""
    presentes = []
    ausentes = []
    licencias = []
    fecha = None
    tipo_sesion = None
    reunion_nro = None
    
    try:
        with pdfplumber.open(BytesIO(pdf_content)) as pdf:
            for i, page in enumerate(pdf.pages[:5]):
                text = page.extract_text()
                if not text:
                    continue
                
                # Extraer metadata de página 1
                if i == 0:
                    fecha_match = re.search(r'(\d{1,2} de \w+ de \d{4})', text)
                    if fecha_match:
                        fecha = fecha_match.group(1)
                    
                    reunion_match = re.search(r'(\d+)° REUNIÓN', text)
                    if reunion_match:
                        reunion_nro = int(reunion_match.group(1))
                    
                    if 'ordinaria' in text.lower():
                        tipo_sesion = 'Ordinaria'
                    elif 'especial' in text.lower():
                        tipo_sesion = 'Especial'
                    elif 'preparatoria' in text.lower():
                        tipo_sesion = 'Preparatoria'
                    elif 'extraordinaria' in text.lower():
                        tipo_sesion = 'Extraordinaria'
                
                # Buscar página con PRESENTES
                if 'PRESENTES:' in text or 'PRESENTES' in text.upper():
                    lines = text.split('\n')
                    seccion = None
                    
                    for line in lines:
                        line = line.strip()
                        
                        if 'PRESENTES:' in line or line == 'PRESENTES':
                            seccion = 'presentes'
                            continue
                        elif 'AUSENTE' in line.upper():
                            seccion = 'ausentes'
                            # Puede haber nombres en la misma línea después de "AUSENTE:"
                            resto = re.sub(r'AUSENTES?:', '', line, flags=re.IGNORECASE).strip()
                            if resto:
                                line = resto
                            else:
                                continue
                        elif 'LICENCIA' in line.upper():
                            seccion = 'licencias'
                            continue
                        elif 'Dirección General' in line:
                            break
                        
                        if seccion and line:
                            # Extraer nombres - pueden estar en 2 columnas
                            # Limpiar y separar posibles nombres
                            nombres = re.findall(r'([A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ\'\s]+,\s+[A-Za-záéíóúñü\s\.]+?)(?=[A-ZÁÉÍÓÚÑÜ]{2,}|$)', line + ' ')
                            
                            if not nombres:
                                # Intentar formato simple
                                if ',' in line and len(line) > 5:
                                    nombres = [line]
                            
                            for nombre in nombres:
                                nombre = nombre.strip()
                                # Limpiar nombre
                                nombre = re.sub(r'\s+', ' ', nombre)
                                if len(nombre) > 5 and ',' in nombre:
                                    if seccion == 'presentes':
                                        presentes.append(nombre)
                                    elif seccion == 'ausentes':
                                        ausentes.append(nombre)
                                    elif seccion == 'licencias':
                                        licencias.append(nombre)
                    
                    break
    except Exception as e:
        print(f"Error procesando PDF: {e}")
        return None
    
    return {
        'fecha': fecha,
        'tipo_sesion': tipo_sesion,
        'reunion_nro': reunion_nro,
        'presentes': list(set(presentes)),
        'ausentes': list(set(ausentes)),
        'licencias': list(set(licencias))
    }


def parsear_fecha(fecha_str):
    """Convierte '18 de marzo de 2026' a datetime."""
    meses = {
        'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4,
        'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8,
        'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
    }
    
    try:
        match = re.match(r'(\d{1,2}) de (\w+) de (\d{4})', fecha_str)
        if match:
            dia = int(match.group(1))
            mes = meses.get(match.group(2).lower())
            anio = int(match.group(3))
            if mes:
                return datetime(anio, mes, dia).date()
    except:
        pass
    return None


def main():
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Crear tablas si no existen
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS sesiones_senado (
                id SERIAL PRIMARY KEY,
                sesion_id VARCHAR(20) UNIQUE,
                fecha DATE,
                tipo VARCHAR(50),
                reunion_nro INTEGER,
                presentes INTEGER,
                ausentes INTEGER,
                licencias INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS asistencia_senado (
                id SERIAL PRIMARY KEY,
                sesion_id VARCHAR(20),
                senador_nombre VARCHAR(200),
                estado VARCHAR(20),
                legislador_id INTEGER REFERENCES legisladores(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_asist_sen_sesion ON asistencia_senado(sesion_id);
            CREATE INDEX IF NOT EXISTS idx_asist_sen_leg ON asistencia_senado(legislador_id);
        '''))
        conn.commit()
        print("Tablas creadas/verificadas")
    
    # Scrapear años 2019-2026
    for anio in range(2026, 2018, -1):
        print(f"\n=== Año {anio} ===")
        
        sesiones = obtener_sesiones(anio)
        print(f"Encontradas {len(sesiones)} sesiones")
        
        for sesion in sesiones:
            sesion_id = sesion['id']
            
            # Verificar si ya existe
            with engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT 1 FROM sesiones_senado WHERE sesion_id = :id"
                ), {'id': sesion_id})
                if result.fetchone():
                    print(f"  Sesión {sesion_id} ya existe, saltando...")
                    continue
            
            print(f"  Descargando sesión {sesion_id}...")
            
            try:
                response = requests.get(sesion['url'], timeout=60)
                if response.status_code != 200:
                    print(f"    Error HTTP {response.status_code}")
                    continue
                
                asistencia = extraer_asistencia_pdf(response.content)
                if not asistencia:
                    print(f"    No se pudo extraer asistencia")
                    continue
                
                fecha = parsear_fecha(asistencia['fecha']) if asistencia['fecha'] else None
                
                print(f"    Fecha: {fecha}, Presentes: {len(asistencia['presentes'])}, Ausentes: {len(asistencia['ausentes'])}")
                
                with engine.connect() as conn:
                    # Insertar sesión
                    conn.execute(text('''
                        INSERT INTO sesiones_senado (sesion_id, fecha, tipo, reunion_nro, presentes, ausentes, licencias)
                        VALUES (:sid, :fecha, :tipo, :reunion, :pres, :aus, :lic)
                        ON CONFLICT (sesion_id) DO NOTHING
                    '''), {
                        'sid': sesion_id,
                        'fecha': fecha,
                        'tipo': asistencia['tipo_sesion'],
                        'reunion': asistencia['reunion_nro'],
                        'pres': len(asistencia['presentes']),
                        'aus': len(asistencia['ausentes']),
                        'lic': len(asistencia['licencias'])
                    })
                    
                    # Insertar asistencia
                    for nombre in asistencia['presentes']:
                        conn.execute(text('''
                            INSERT INTO asistencia_senado (sesion_id, senador_nombre, estado)
                            VALUES (:sid, :nombre, 'PRESENTE')
                        '''), {'sid': sesion_id, 'nombre': nombre})
                    
                    for nombre in asistencia['ausentes']:
                        conn.execute(text('''
                            INSERT INTO asistencia_senado (sesion_id, senador_nombre, estado)
                            VALUES (:sid, :nombre, 'AUSENTE')
                        '''), {'sid': sesion_id, 'nombre': nombre})
                    
                    for nombre in asistencia['licencias']:
                        conn.execute(text('''
                            INSERT INTO asistencia_senado (sesion_id, senador_nombre, estado)
                            VALUES (:sid, :nombre, 'LICENCIA')
                        '''), {'sid': sesion_id, 'nombre': nombre})
                    
                    conn.commit()
                
                time.sleep(2)  # Pausa entre descargas
                
            except Exception as e:
                print(f"    Error: {e}")
                continue
    
    # Estadísticas finales
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM sesiones_senado"))
        print(f"\n=== Total sesiones: {result.scalar()} ===")
        
        result = conn.execute(text("SELECT COUNT(*) FROM asistencia_senado"))
        print(f"Total registros asistencia: {result.scalar()}")


if __name__ == '__main__':
    main()
