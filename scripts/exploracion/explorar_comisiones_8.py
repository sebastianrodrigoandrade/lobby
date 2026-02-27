import re

MESES = {'enero','febrero','marzo','abril','mayo','junio','julio','agosto',
         'septiembre','octubre','noviembre','diciembre'}

def limpiar_encoding(texto):
    reemplazos = {'¾': 'ó', 'ß': 'á', '±': 'ñ', 'Ý': 'í', '┴': 'Á'}
    for mal, bien in reemplazos.items():
        texto = texto.replace(mal, bien)
    return texto

frases_test = [
    "Fue invitado el diputado Emiliano Rafael Estrada.",
    "Fueron invitados el Secretario de Educación, Dr. Carlos Torrendell y el Subsecretario de Políticas Universitarias, Lic. Alejandro Álvarez.",
    "Fue invitado el Sr. Luis Har y la Sra. Clara Marman.",
    "fue invitado el secretario de Finanzas de la Nación.",
    "Director del CELADE, Director del INDEC, Paola Bohorquez, director del Instituto Nacional",
    "Marcelo Ferraris, Comité Federal de Transporte",
    "Carlos Alberto Monfroni",
]

# Patrón simple: buscar título + nombre propio
patron = re.compile(
    r'(?:Dr\.|Dra\.|Lic\.|Mg\.|Ing\.|Sr\.|Sra\.|Prof\.)\s*'
    r'([A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]+(?:\s+[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]+){1,3})',
)

# Patrón para diputado/senador + nombre
patron2 = re.compile(
    r'(?:diputad[oa]|senad[oa]r[a]?)\s+'
    r'([A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]+(?:\s+[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]+){1,3})',
    re.IGNORECASE
)

for frase in frases_test:
    frase = limpiar_encoding(frase)
    encontrados = [m.group(1) for m in patron.finditer(frase)]
    encontrados += [m.group(1) for m in patron2.finditer(frase)]
    print(f"INPUT:  {frase[:80]}")
    print(f"OUTPUT: {encontrados}")
    print()