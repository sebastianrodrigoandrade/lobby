"""
Script para normalizar nombres de legisladores
Formato final: "Apellido, Nombre" (capitalizado correctamente)
"""
import re
from src.database import SessionLocal
from sqlalchemy import text

# Prefijos de apellidos que deben mantenerse
PREFIJOS = {'de', 'del', 'de la', 'de los', 'de las', 'di', 'da', 'van', 'von', 'mac', 'mc'}

# Palabras que deben ir en minúscula (excepto al inicio)
MINUSCULAS = {'de', 'del', 'la', 'los', 'las', 'y', 'e'}


def capitalizar_palabra(palabra):
    """Capitaliza una palabra correctamente"""
    if not palabra:
        return palabra
    
    # Si es toda mayúsculas o toda minúsculas, capitalizar
    palabra_lower = palabra.lower()
    
    # Manejar prefijos especiales
    if palabra_lower in MINUSCULAS:
        return palabra_lower
    
    # Manejar Mc y Mac
    if palabra_lower.startswith('mc') and len(palabra) > 2:
        return 'Mc' + palabra[2:].capitalize()
    if palabra_lower.startswith('mac') and len(palabra) > 3:
        return 'Mac' + palabra[3:].capitalize()
    
    return palabra.capitalize()


def capitalizar_nombre(texto):
    """Capitaliza un nombre completo correctamente"""
    if not texto:
        return texto
    
    palabras = texto.split()
    resultado = []
    
    for i, palabra in enumerate(palabras):
        # Primera palabra siempre capitalizada
        if i == 0:
            if palabra.lower() in MINUSCULAS:
                resultado.append(palabra.capitalize())
            else:
                resultado.append(capitalizar_palabra(palabra))
        else:
            resultado.append(capitalizar_palabra(palabra))
    
    return ' '.join(resultado)


def detectar_formato(nombre):
    """
    Detecta el formato actual del nombre y devuelve (apellido, nombre)
    Formatos posibles:
    1. "APELLIDO, NOMBRE" o "Apellido, Nombre" — con coma
    2. "APELLIDO Nombre" — apellido en mayúsculas, nombre en normal
    3. "Nombre Apellido" — nombre primero (detectar por contexto)
    """
    nombre = nombre.strip()
    
    # Caso 1: tiene coma
    if ',' in nombre:
        partes = nombre.split(',', 1)
        apellido = partes[0].strip()
        nombres = partes[1].strip() if len(partes) > 1 else ''
        return apellido, nombres
    
    # Caso 2 y 3: sin coma
    palabras = nombre.split()
    
    if len(palabras) == 1:
        return palabras[0], ''
    
    # Detectar cuántas palabras están en MAYÚSCULAS al inicio
    mayusculas_inicio = 0
    for palabra in palabras:
        # Ignorar prefijos cortos
        if palabra.lower() in PREFIJOS:
            mayusculas_inicio += 1
            continue
        if palabra.isupper():
            mayusculas_inicio += 1
        else:
            break
    
    # Si hay palabras en mayúsculas al inicio, es APELLIDO Nombre
    if mayusculas_inicio > 0:
        apellido = ' '.join(palabras[:mayusculas_inicio])
        nombres = ' '.join(palabras[mayusculas_inicio:])
        return apellido, nombres
    
    # Si la primera palabra empieza con mayúscula y la última también,
    # intentar detectar si es "Nombre Apellido"
    # Heurística: si la última palabra parece apellido (más común), invertir
    
    # Por defecto, asumir que la última palabra es el apellido
    # (formato "Nombre Apellido" común en algunos registros)
    apellido = palabras[-1]
    nombres = ' '.join(palabras[:-1])
    
    # Pero si hay 2 palabras y ambas capitalizadas igual, 
    # verificar si la primera es más probable que sea apellido
    if len(palabras) == 2:
        # Mantener como está, última palabra = apellido
        pass
    elif len(palabras) >= 3:
        # Si hay 3+ palabras, las últimas 2 podrían ser apellido compuesto
        # Verificar si las últimas 2 están capitalizadas igual
        if palabras[-2][0].isupper() and palabras[-1][0].isupper():
            # Posible apellido compuesto
            apellido = ' '.join(palabras[-2:])
            nombres = ' '.join(palabras[:-2])
    
    return apellido, nombres


def normalizar_nombre(nombre_original):
    """Normaliza un nombre al formato 'Apellido, Nombre'"""
    if not nombre_original:
        return nombre_original
    
    apellido, nombres = detectar_formato(nombre_original)
    
    # Capitalizar correctamente
    apellido = capitalizar_nombre(apellido)
    nombres = capitalizar_nombre(nombres)
    
    # Formato final
    if nombres:
        return f"{apellido}, {nombres}"
    else:
        return apellido


def preview_cambios(limit=50):
    """Muestra una preview de los cambios sin aplicarlos"""
    db = SessionLocal()
    
    result = db.execute(text("""
        SELECT id, nombre_completo 
        FROM legisladores 
        ORDER BY random() 
        LIMIT :limit
    """), {"limit": limit})
    
    registros = result.fetchall()
    db.close()
    
    print(f"{'ORIGINAL':<45} | {'NORMALIZADO':<45}")
    print("-" * 93)
    
    cambios = 0
    for id, nombre in registros:
        normalizado = normalizar_nombre(nombre)
        if nombre != normalizado:
            cambios += 1
            print(f"{nombre:<45} | {normalizado:<45}")
    
    print("-" * 93)
    print(f"Cambios detectados: {cambios}/{len(registros)}")
    
    return cambios


def aplicar_cambios(dry_run=True):
    """Aplica los cambios a la base de datos"""
    db = SessionLocal()
    
    result = db.execute(text("SELECT id, nombre_completo FROM legisladores"))
    registros = result.fetchall()
    
    cambios = []
    for id, nombre in registros:
        normalizado = normalizar_nombre(nombre)
        if nombre != normalizado:
            cambios.append((id, nombre, normalizado))
    
    print(f"Total registros: {len(registros)}")
    print(f"Cambios a aplicar: {len(cambios)}")
    
    if dry_run:
        print("\n[DRY RUN] No se aplicaron cambios. Ejecutá con dry_run=False para aplicar.")
        db.close()
        return
    
    # Aplicar cambios
    for id, original, normalizado in cambios:
        db.execute(
            text("UPDATE legisladores SET nombre_completo = :nuevo WHERE id = :id"),
            {"nuevo": normalizado, "id": id}
        )
    
    db.commit()
    db.close()
    
    print(f"\n✓ {len(cambios)} registros actualizados.")


if __name__ == "__main__":
    print("=== PREVIEW DE NORMALIZACIÓN ===\n")
    preview_cambios(50)
    
    print("\n" + "=" * 50)
    respuesta = input("\n¿Aplicar cambios? (s/n): ")
    
    if respuesta.lower() == 's':
        aplicar_cambios(dry_run=False)
    else:
        print("Operación cancelada.")