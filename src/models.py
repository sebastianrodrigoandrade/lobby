# src/models.py
from sqlalchemy import Column, Integer, String, Date, ForeignKey, Text, Index, text
from sqlalchemy.orm import relationship
from src.database import Base

class Legislador(Base):
    __tablename__ = 'legisladores'
    
    id = Column(Integer, primary_key=True, index=True)
    nombre_completo = Column(String, nullable=False)
    dni_cuit = Column(String, nullable=True)
    camara = Column(String)
    bloque = Column(String)
    distrito = Column(String)
    mandato_hasta = Column(Date, nullable=True)
    
    votos = relationship("Voto", back_populates="legislador")
    audiencias = relationship("Audiencia", back_populates="legislador")

Index(
    'ix_legisladores_dni_cuit',
    Legislador.dni_cuit,
    unique=True,
    postgresql_where=text("dni_cuit IS NOT NULL")
)

class Proyecto(Base):
    __tablename__ = 'proyectos'
    
    id = Column(Integer, primary_key=True, index=True)
    nro_expediente = Column(String, unique=True, nullable=False)
    titulo = Column(Text)
    fecha_ingreso = Column(Date)
    estado = Column(String)
    autores = Column(Text)
    
    votos = relationship("Voto", back_populates="proyecto")

class Sesion(Base):
    __tablename__ = 'sesiones'
    
    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(Date)
    tipo_periodo = Column(String)       # Ordinaria / Extraordinaria / Prórroga
    tipo_reunion = Column(String)       # Especial, Minoría, Informativa, etc.
    duracion_horas = Column(String)
    hubo_quorum = Column(String)
    periodo_id = Column(String)         # Ej: HCDN142R22
    diario_sesion_url = Column(String)
    
    votos = relationship("Voto", back_populates="sesion")

class Voto(Base):
    __tablename__ = 'votos'
    
    id = Column(Integer, primary_key=True, index=True)
    # ✅ ID único del CSV para deduplicación
    acta_detalle_id = Column(Integer, nullable=True)
    acta_id = Column(Integer, nullable=True)
    sesion_id = Column(Integer, ForeignKey('sesiones.id'), nullable=True)
    proyecto_id = Column(Integer, ForeignKey('proyectos.id'), nullable=True)
    legislador_id = Column(Integer, ForeignKey('legisladores.id'))
    voto_individual = Column(String)
    resultado_general = Column(String)
    
    legislador = relationship("Legislador", back_populates="votos")
    proyecto = relationship("Proyecto", back_populates="votos")
    sesion = relationship("Sesion", back_populates="votos")

# ✅ Índice único para evitar votos duplicados a nivel DB
Index(
    'ix_votos_acta_detalle_id',
    Voto.acta_detalle_id,
    unique=True,
    postgresql_where=text("acta_detalle_id IS NOT NULL")
)

class Audiencia(Base):
    __tablename__ = 'audiencias'
    
    id = Column(Integer, primary_key=True, index=True)
    legislador_id = Column(Integer, ForeignKey('legisladores.id'))
    solicitante = Column(String)
    motivo = Column(Text)
    fecha = Column(Date)
    
    legislador = relationship("Legislador", back_populates="audiencias")
    
class ActaCabecera(Base):
    __tablename__ = 'actas_cabecera'
    
    id = Column(Integer, primary_key=True, index=True)
    acta_id = Column(Integer, nullable=False)
    sesion_id = Column(String)
    nroperiodo = Column(Integer)
    tipo_periodo = Column(String)
    reunion = Column(Integer)
    fecha = Column(Date)
    hora = Column(String)
    titulo = Column(Text)
    resultado = Column(String)
    votos_afirmativos = Column(Integer)
    votos_negativos = Column(Integer)
    abstenciones = Column(Integer)
    ausentes = Column(Integer)

Index(
    'ix_actas_cabecera_acta_id',
    ActaCabecera.acta_id,
    unique=True
)