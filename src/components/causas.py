# -*- coding: utf-8 -*-
"""
Componente para mostrar menciones judiciales de legisladores.
Usa datos del archivo CIJ (Centro de Informacion Judicial).
"""
import streamlit as st
from sqlalchemy import text

def get_menciones_legislador(db, legislador_id: int):
    """Obtiene las menciones judiciales de un legislador."""
    query = text("""
        SELECT n.titulo, n.fecha, n.url, n.palabra_clave, m.tipo_match
        FROM menciones_cij m
        JOIN noticias_judiciales n ON m.noticia_id = n.id
        WHERE m.legislador_id = :leg_id
        ORDER BY n.fecha DESC
    """)
    return db.execute(query, {"leg_id": legislador_id}).fetchall()

def mostrar_menciones_legislador(db, legislador_id: int, legislador_nombre: str):
    """Muestra las menciones judiciales en el perfil del legislador."""
    menciones = get_menciones_legislador(db, legislador_id)
    
    if not menciones:
        return
    
    st.markdown("---")
    st.subheader(f"Menciones en noticias judiciales ({len(menciones)})")
    
    st.caption("""
        Aviso: Estas son menciones en noticias del archivo CIJ. 
        Una mencion no implica culpabilidad ni condena. El legislador puede aparecer 
        como querellante, testigo, o en contexto informativo.
    """)
    
    for mencion in menciones:
        titulo, fecha, url, palabra_clave, tipo_match = mencion
        with st.expander(f"{titulo[:80]}..." if len(titulo) > 80 else titulo):
            st.write(f"**Fecha:** {fecha}")
            st.write(f"**Palabra clave:** {palabra_clave}")
            st.write(f"**Tipo de match:** {tipo_match}")
            st.markdown(f"[Ver noticia completa]({url})")

def get_ranking_menciones(db, camara: str = None, min_menciones: int = 1):
    """Obtiene el ranking de legisladores por menciones."""
    where_clause = ""
    params = {"min": min_menciones}
    
    if camara and camara != "Todas":
        where_clause = "WHERE l.camara = :camara"
        params["camara"] = camara
    
    query = text(f"""
        SELECT l.id, l.nombre_completo, l.bloque, l.camara, COUNT(*) as menciones
        FROM menciones_cij m
        JOIN legisladores l ON m.legislador_id = l.id
        {where_clause}
        GROUP BY l.id, l.nombre_completo, l.bloque, l.camara
        HAVING COUNT(*) >= :min
        ORDER BY menciones DESC
    """)
    return db.execute(query, params).fetchall()

def get_estadisticas_generales(db):
    """Obtiene estadisticas generales de menciones."""
    stats = {}
    
    result = db.execute(text("SELECT COUNT(*) FROM noticias_judiciales"))
    stats['total_noticias'] = result.scalar()
    
    result = db.execute(text("SELECT COUNT(*) FROM menciones_cij"))
    stats['total_menciones'] = result.scalar()
    
    result = db.execute(text("SELECT COUNT(DISTINCT legislador_id) FROM menciones_cij"))
    stats['legisladores_mencionados'] = result.scalar()
    
    return stats