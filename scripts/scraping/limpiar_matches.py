"""
Limpieza de Falsos Positivos en Matches de Causas
=================================================

Filtra los matches que son falsos positivos (apellidos comunes
que coinciden pero no son el legislador).

Uso:
    python limpiar_matches.py
"""

import os
import re
import pandas as pd
from datetime import datetime
from unidecode import unidecode

# Directorio de datos
DATA_DIR = "data/archivo_cij"


def normalizar(texto):
    """Normaliza texto para comparación"""
    if not texto:
        return ""
    # Quitar tildes y convertir a mayúsculas
    texto = unidecode(str(texto)).upper()
    # Quitar caracteres especiales
    texto = re.sub(r'[^A-Z\s]', '', texto)
    return texto


def extraer_nombre_apellido(nombre_completo):
    """Extrae apellido y primer nombre de un nombre completo"""
    nombre_completo = nombre_completo.strip()
    
    # Quitar sufijos como "(suspendido Art 70 C.n.)"
    nombre_completo = re.sub(r'\([^)]+\)', '', nombre_completo).strip()
    
    if ',' in nombre_completo:
        partes = nombre_completo.split(',', 1)
        apellido = partes[0].strip()
        nombres = partes[1].strip() if len(partes) > 1 else ''
        primer_nombre = nombres.split()[0] if nombres.split() else ''
    else:
        partes = nombre_completo.split()
        apellido = partes[0] if partes else ''
        primer_nombre = partes[1] if len(partes) > 1 else ''
    
    return apellido, primer_nombre


def es_match_valido(legislador_nombre, noticia_titulo):
    """
    Verifica si el match es válido (no es falso positivo)
    
    Criterios:
    1. El apellido + primer nombre aparecen juntos en la noticia
    2. O el nombre completo aparece
    3. Excepciones para apellidos muy comunes que requieren más contexto
    """
    apellido, primer_nombre = extraer_nombre_apellido(legislador_nombre)
    
    titulo_norm = normalizar(noticia_titulo)
    apellido_norm = normalizar(apellido)
    nombre_norm = normalizar(primer_nombre)
    
    # Apellidos muy comunes que generan muchos falsos positivos
    apellidos_comunes = [
        'RODRIGUEZ', 'GONZALEZ', 'FERNANDEZ', 'LOPEZ', 'MARTINEZ',
        'GARCIA', 'SANCHEZ', 'PEREZ', 'ROMERO', 'DIAZ', 'TORRES',
        'RUIZ', 'RAMIREZ', 'FLORES', 'CASTRO', 'MORALES', 'ORTIZ',
        'SILVA', 'GUTIERREZ', 'HERNANDEZ', 'SOTO', 'JUEZ', 'RAMON'
    ]
    
    # Si el apellido es muy común, requerir apellido + nombre juntos
    if apellido_norm in apellidos_comunes:
        # Buscar "APELLIDO, NOMBRE" o "NOMBRE APELLIDO"
        patron1 = apellido_norm + r'[,\s]+' + nombre_norm
        patron2 = nombre_norm + r'\s+' + apellido_norm
        
        if re.search(patron1, titulo_norm) or re.search(patron2, titulo_norm):
            return True, "nombre_completo"
        else:
            return False, "apellido_comun_sin_nombre"
    
    # Para apellidos menos comunes, verificar contexto
    # El apellido debe aparecer como nombre propio (mayúscula inicial en original)
    
    # Buscar el apellido en el título original
    titulo_orig = noticia_titulo
    
    # Verificar que aparezca como nombre propio (después de comillas, al inicio, etc.)
    patron_nombre_propio = r'(?:"|"|«|\b)' + re.escape(apellido) + r'(?:\s|,|"|"|»)'
    
    if re.search(patron_nombre_propio, titulo_orig, re.IGNORECASE):
        # Parece ser un nombre propio, verificar si hay más contexto
        # Buscar si también aparece el primer nombre cerca
        if nombre_norm and nombre_norm in titulo_norm:
            return True, "apellido_con_nombre"
        else:
            # Solo apellido, marcar como posible
            return True, "solo_apellido_verificar"
    
    return False, "no_match"


def limpiar_matches(filepath):
    """Limpia falsos positivos del archivo de matches"""
    
    print(f"Procesando: {filepath}")
    
    df = pd.read_csv(filepath)
    print(f"Total matches originales: {len(df)}")
    
    # Aplicar filtro
    resultados = []
    for _, row in df.iterrows():
        es_valido, razon = es_match_valido(
            row['legislador_nombre'],
            row['noticia_titulo']
        )
        resultados.append({
            **row.to_dict(),
            'match_valido': es_valido,
            'razon_match': razon
        })
    
    df_resultado = pd.DataFrame(resultados)
    
    # Estadísticas
    validos = df_resultado[df_resultado['match_valido'] == True]
    invalidos = df_resultado[df_resultado['match_valido'] == False]
    
    print(f"\nMatches válidos: {len(validos)}")
    print(f"Falsos positivos filtrados: {len(invalidos)}")
    
    # Mostrar razones
    print("\nRazones de matches válidos:")
    print(validos['razon_match'].value_counts())
    
    print("\nRazones de filtrado:")
    print(invalidos['razon_match'].value_counts())
    
    # Guardar archivo limpio
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Solo válidos
    output_validos = filepath.replace('.csv', '_limpio.csv')
    validos.to_csv(output_validos, index=False, encoding='utf-8-sig')
    print(f"\nGuardado: {output_validos}")
    
    # Todos con flag
    output_todos = filepath.replace('.csv', '_con_flag.csv')
    df_resultado.to_csv(output_todos, index=False, encoding='utf-8-sig')
    print(f"Guardado: {output_todos}")
    
    # Mostrar legisladores con matches válidos
    print("\n" + "=" * 50)
    print("LEGISLADORES CON CAUSAS VERIFICADAS:")
    print("=" * 50)
    
    for nombre in validos['legislador_nombre'].unique():
        causas = validos[validos['legislador_nombre'] == nombre]
        print(f"\n{nombre} ({len(causas)} noticias):")
        for _, c in causas.head(3).iterrows():
            print(f"   - {c['noticia_titulo'][:70]}...")
    
    return validos


def main():
    print("=" * 60)
    print("LIMPIEZA DE FALSOS POSITIVOS")
    print("=" * 60)
    
    # Buscar archivo de matches más reciente
    archivos = [f for f in os.listdir(DATA_DIR) if f.startswith('matches_legisladores_') and f.endswith('.csv')]
    
    if not archivos:
        print("No se encontraron archivos de matches")
        return
    
    # Ordenar por fecha (más reciente primero)
    archivos.sort(reverse=True)
    filepath = os.path.join(DATA_DIR, archivos[0])
    
    # Limpiar
    try:
        from unidecode import unidecode
    except ImportError:
        print("Instalando unidecode...")
        os.system("pip install unidecode")
        from unidecode import unidecode
    
    validos = limpiar_matches(filepath)
    
    print("\n" + "=" * 60)
    print("LIMPIEZA COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    main()
