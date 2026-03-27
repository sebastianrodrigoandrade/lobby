#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Descarga CSVs de detalle de DDJJ desde datos.jus.gob.ar
- Bienes
- Deudas
- Grupo familiar
"""
import os
import urllib.request

# URLs de los recursos
RECURSOS = {
    'bienes_2024': 'https://datos.jus.gob.ar/dataset/4680199f-6234-4262-8a2a-8f7993bf784d/resource/ffa28585-9adb-473e-9627-0ffe1938d288/download/declaraciones-juradas-bienes-2024-consolidado-al-20251222.csv',
    'deudas_2024': 'https://datos.jus.gob.ar/dataset/4680199f-6234-4262-8a2a-8f7993bf784d/resource/dd1c30e2-e773-47fd-ac80-9afaf3f1baa4/download/declaraciones-juradas-deudas-2024-consolidado-al-20251222.csv',
    'grupo_familiar_2024': 'https://datos.jus.gob.ar/dataset/4680199f-6234-4262-8a2a-8f7993bf784d/resource/aeb174ff-26b5-4586-827f-872afdc52b49/download/declaraciones-juradas-grupo-familiar-2024-consolidado-al-20251222.csv',
}

# Directorio de destino
DESTINO = 'data/ddjj_detalle'

def descargar():
    os.makedirs(DESTINO, exist_ok=True)
    
    for nombre, url in RECURSOS.items():
        archivo = os.path.join(DESTINO, f'{nombre}.csv')
        print(f'Descargando {nombre}...')
        
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=120) as response:
                contenido = response.read()
            
            with open(archivo, 'wb') as f:
                f.write(contenido)
            
            # Tamaño
            size_mb = len(contenido) / (1024 * 1024)
            print(f'  OK: {size_mb:.1f} MB -> {archivo}')
            
        except Exception as e:
            print(f'  ERROR: {e}')
    
    print('\nDescarga completa!')

if __name__ == '__main__':
    descargar()
