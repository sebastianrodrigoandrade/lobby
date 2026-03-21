#!/usr/bin/env python3
"""
Scraper de Votaciones Nominales HCDN
====================================
Descarga y parsea las actas de votación en PDF desde votaciones.hcdn.gob.ar
"""

import requests
from pypdf import PdfReader
from io import BytesIO
import pandas as pd
import re
import os
import time
from datetime import datetime

BASE_URL = "https://votaciones.hcdn.gob.ar/pdf/acta"
OUTPUT_DIR = "data/votaciones_hcdn"


def descargar_pdf(acta_id):
    """Descarga un PDF de acta."""
    url = f"{BASE_URL}/{acta_id}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200 and len(r.content) > 1000:
            return r.content
    except:
        pass
    return None


def parsear_votos(text):
    """Extrae votos individuales del texto."""
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    votos = []
    votos_validos = ['AFIRMATIVO', 'NEGATIVO', 'ABSTENCION', 'AUSENTE']
    
    i = 0
    while i < len(lines) - 3:
        if ',' in lines[i] and lines[i].replace(',', '').replace(' ', '').replace('.', '').isalpha():
            nombre = lines[i]
            if i + 3 < len(lines) and lines[i + 3] in votos_validos:
                votos.append({
                    'legislador': nombre,
                    'bloque': lines[i + 1],
                    'distrito': lines[i + 2],
                    'voto': lines[i + 3]
                })
                i += 4
                continue
        i += 1
    
    return votos


def parsear_acta(pdf_content, acta_id):
    """Extrae metadata y votos de un PDF."""
    try:
        reader = PdfReader(BytesIO(pdf_content))
        text = ''.join([p.extract_text() + '\n' for p in reader.pages])
        
        # Metadata
        metadata = {'acta_id': acta_id}
        
        fecha = re.search(r'Fecha:\s*(\d{2}/\d{2}/\d{4})', text)
        metadata['fecha'] = fecha.group(1) if fecha else None
        
        hora = re.search(r'Hora:\s*(\d{2}:\d{2})', text)
        metadata['hora'] = hora.group(1) if hora else None
        
        periodo = re.search(r'(\d+).-\s*Per', text)
        metadata['periodo'] = int(periodo.group(1)) if periodo else None
        
        asunto = re.search(r'(O\.D\.\s*\d+[^\n]+)', text)
        if not asunto:
            asunto = re.search(r'(Expediente[^\n]+)', text)
        metadata['asunto'] = asunto.group(1).strip()[:300] if asunto else None
        
        if re.search(r'Resultado[^\n]*AFIRMATIVO', text):
            metadata['resultado'] = 'AFIRMATIVO'
        elif re.search(r'Resultado[^\n]*NEGATIVO', text):
            metadata['resultado'] = 'NEGATIVO'
        else:
            metadata['resultado'] = None
        
        af = re.search(r'Afirmativos\s*(\d+)', text)
        metadata['afirmativos'] = int(af.group(1)) if af else None
        
        neg = re.search(r'Negativos\s*(\d+)', text)
        metadata['negativos'] = int(neg.group(1)) if neg else None
        
        abst = re.search(r'Abstenciones\s*(\d+)', text)
        metadata['abstenciones'] = int(abst.group(1)) if abst else None
        
        aus = re.search(r'Ausentes\s*(\d+)', text)
        metadata['ausentes'] = int(aus.group(1)) if aus else None
        
        # Votos individuales
        votos = parsear_votos(text)
        for v in votos:
            v['acta_id'] = acta_id
            v['fecha'] = metadata['fecha']
        
        return metadata, votos
    
    except Exception as e:
        print(f"\n  Error parseando acta {acta_id}: {e}")
        return None, []


def main():
    print("=" * 60)
    print("SCRAPER VOTACIONES NOMINALES HCDN")
    print("=" * 60)
    print(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    PRIMERA = 1
    ULTIMA = 5881
    
    todas_las_actas = []
    todos_los_votos = []
    errores_consecutivos = 0
    actas_procesadas = 0
    
    print(f"Descargando actas {ULTIMA} a {PRIMERA}...")
    print()
    
    inicio = time.time()
    
    for acta_id in range(ULTIMA, PRIMERA - 1, -1):
        print(f"\r[{ULTIMA - acta_id + 1:4d}/{ULTIMA}] Acta {acta_id}... ", end="", flush=True)
        
        pdf = descargar_pdf(acta_id)
        
        if pdf:
            metadata, votos = parsear_acta(pdf, acta_id)
            
            if metadata:
                todas_las_actas.append(metadata)
                todos_los_votos.extend(votos)
                errores_consecutivos = 0
                actas_procesadas += 1
                print(f"{len(votos):3d} votos", end="")
            else:
                errores_consecutivos += 1
        else:
            errores_consecutivos += 1
        
        # Checkpoint cada 200 actas
        if actas_procesadas > 0 and actas_procesadas % 200 == 0:
            elapsed = time.time() - inicio
            rate = actas_procesadas / elapsed * 60
            print(f"\n  >> Checkpoint: {actas_procesadas} actas, {len(todos_los_votos):,} votos ({rate:.0f} actas/min)")
            pd.DataFrame(todas_las_actas).to_csv(f"{OUTPUT_DIR}/actas_checkpoint.csv", index=False)
            pd.DataFrame(todos_los_votos).to_csv(f"{OUTPUT_DIR}/votos_checkpoint.csv", index=False)
        
        if errores_consecutivos > 100:
            print(f"\n  >> Saltando hueco grande")
            errores_consecutivos = 0
        
        time.sleep(0.1)
    
    elapsed = time.time() - inicio
    
    print()
    print()
    print("=" * 60)
    print("RESULTADOS")
    print("=" * 60)
    print(f"Tiempo total: {elapsed/60:.1f} minutos")
    
    if todas_las_actas:
        df_actas = pd.DataFrame(todas_las_actas)
        df_actas.to_csv(f"{OUTPUT_DIR}/actas_hcdn.csv", index=False)
        print(f"Actas: {len(df_actas):,} guardadas")
        
        if 'periodo' in df_actas.columns:
            print("\nPor periodo:")
            for p, c in df_actas.groupby('periodo').size().sort_index().items():
                if p:
                    print(f"  {int(p)}: {c} actas")
    
    if todos_los_votos:
        df_votos = pd.DataFrame(todos_los_votos)
        df_votos.to_csv(f"{OUTPUT_DIR}/votos_hcdn.csv", index=False)
        print(f"\nVotos: {len(df_votos):,} guardados")
        
        print("\nPor tipo:")
        for v, c in df_votos.groupby('voto').size().items():
            print(f"  {v}: {c:,}")
    
    print()
    print("Completado!")


if __name__ == "__main__":
    main()