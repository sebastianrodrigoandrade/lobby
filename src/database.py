# src/database.py
import os
import urllib.parse  # <--- IMPORTANTE: Importar esta librería
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Cargar variables de entorno
load_dotenv()

DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_HOST = os.getenv('DB_HOST')
DB_NAME = os.getenv('DB_NAME')
DB_PORT = os.getenv('DB_PORT', '5432')

if not all([DB_USER, DB_PASS, DB_HOST, DB_NAME]):
    raise ValueError("Faltan variables de entorno en el archivo .env")

# 2. CODIFICAR CREDENCIALES (El paso clave para arreglar tu error)
# Esto convierte caracteres como 'ó', '@', 'ñ' en formato seguro para URL (%F3, %40, etc.)
safe_user = urllib.parse.quote_plus(DB_USER)
safe_pass = urllib.parse.quote_plus(DB_PASS)

# 3. Construir URL de conexión usando las credenciales saneadas
DATABASE_URL = f"postgresql+psycopg2://{safe_user}:{safe_pass}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# 4. Crear el motor
engine = create_engine(DATABASE_URL, echo=False)

# 5. Crear la fábrica de sesiones
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 6. Base para los modelos
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()