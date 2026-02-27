import os

# Contenido de prueba para el CSV
contenido_csv = """expediente;fecha;tipo;titulo;sumario
1234-D-2024;2024-03-01;LEY;PROYECTO DE LEY DE EJEMPLO;Este proyecto ingresó a la base de datos exitosamente.
5678-D-2024;2024-03-15;RESOLUCION;OTRO PROYECTO;Segunda prueba de carga.
"""

# Crear el archivo
nombre_archivo = "proyectos.csv"
with open(nombre_archivo, "w", encoding="utf-8") as f:
    f.write(contenido_csv)

print(f"✅ ¡LISTO! Archivo creado en: {os.path.abspath(nombre_archivo)}")
print("Ahora ejecuta 'python main.py' y debería funcionar.")