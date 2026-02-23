from src.database import engine, Base
from src.models import ActaCabecera
Base.metadata.create_all(bind=engine)
print("Tabla creada")