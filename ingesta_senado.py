import requests
from bs4 import BeautifulSoup
from datetime import datetime
from sqlalchemy import text
from src.database import SessionLocal
from src.utils import logger
import time
import warnings
warnings.filterwarnings('ignore')

BASE = "https://www.senado.gob.ar"
MAX_ID = 2700  # actualizar periódicamente

def get_acta_con_retry(url, max_intentos=3):
    for intento in range(max_intentos):
        try:
            r = requests.get(url, timeout=20, verify=False)
            return r
        except Exception as e:
            if intento < max_intentos - 1:
                time.sleep(2 ** intento)
            else:
                raise e

def parsear_acta(acta_id):
    url = f"{BASE}/votaciones/detalleActa/{acta_id}"
    r = get_acta_con_retry(url)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, 'html.parser')
    texto = soup.get_text(separator='\n', strip=True)
    if 'Senador' not in texto and 'AFIRMATIVO' not in texto:
        return None

    metadata = {
        'acta_id': acta_id, 'titulo': '', 'fecha': None, 'resultado': '',
        'afirmativos': 0, 'negativos': 0, 'abstenciones': 0, 'ausentes': 0,
    }
    lineas = [l.strip() for l in texto.split('\n') if l.strip()]
    for i, linea in enumerate(lineas):
        if linea.startswith('Acta Nro:'):
            if i + 1 < len(lineas):
                metadata['titulo'] = lineas[i + 1]
        if '/' in linea and len(linea) <= 12:
            try:
                metadata['fecha'] = datetime.strptime(linea[:10], '%d/%m/%Y').date()
            except:
                pass
        if 'AFIRMATIVOS' in linea:
            try: metadata['afirmativos'] = int(lineas[i - 1])
            except: pass
        if 'NEGATIVOS' in linea:
            try: metadata['negativos'] = int(lineas[i - 1])
            except: pass
        if 'ABSTENCIONES' in linea:
            try: metadata['abstenciones'] = int(lineas[i - 1])
            except: pass
        if 'AUSENTES' in linea:
            try: metadata['ausentes'] = int(lineas[i - 1])
            except: pass

    votos = []
    tabla = soup.find('table')
    if tabla:
        for fila in tabla.find_all('tr')[1:]:
            celdas = fila.find_all('td')
            if len(celdas) >= 4:
                nombre = celdas[1].get_text(strip=True)
                bloque = celdas[2].get_text(strip=True)
                provincia = celdas[3].get_text(strip=True)
                voto = celdas[4].get_text(strip=True) if len(celdas) > 4 else ''
                if nombre and voto:
                    votos.append({'nombre': nombre, 'bloque': bloque, 'provincia': provincia, 'voto': voto})

    return metadata, votos


def main():
    logger.info("=== INGESTA VOTACIONES SENADO ===")
    session = SessionLocal()
    try:
        # ✅ Arrancar desde el último acta conocido
        row = session.execute(
            text("SELECT COALESCE(MAX(acta_id), 0) FROM actas_cabecera WHERE camara = 'Senado'")
        ).fetchone()
        ultimo_id = row[0]
        logger.info(f"Ultimo acta en DB: {ultimo_id} — arrancando desde {ultimo_id + 1}")

        cache_senadores = {
            row[1]: row[0] for row in session.execute(
                text("SELECT id, nombre_completo FROM legisladores WHERE camara = 'Senadores'")
            ).fetchall()
        }
        logger.info(f"Senadores en cache: {len(cache_senadores)}")

        actas_nuevas = 0
        votos_nuevos = 0
        vacias_consecutivas = 0

        for acta_id in range(ultimo_id + 1, MAX_ID + 1):
            try:
                resultado = parsear_acta(acta_id)
                if not resultado:
                    vacias_consecutivas += 1
                    if vacias_consecutivas >= 20:
                        logger.info(f"20 actas vacías consecutivas — fin de datos en ID {acta_id}")
                        break
                    continue

                vacias_consecutivas = 0
                metadata, votos = resultado
                if not votos:
                    continue

                session.execute(text("""
                    INSERT INTO actas_cabecera
                        (acta_id, titulo, fecha, resultado,
                         votos_afirmativos, votos_negativos, abstenciones, ausentes, camara)
                    VALUES
                        (:acta_id, :titulo, :fecha, :resultado,
                         :afirmativos, :negativos, :abstenciones, :ausentes, 'Senado')
                    ON CONFLICT (acta_id) DO NOTHING
                """), metadata)

                for v in votos:
                    nombre = v['nombre']
                    if nombre not in cache_senadores:
                        res = session.execute(text("""
                            INSERT INTO legisladores (nombre_completo, camara, bloque, distrito)
                            VALUES (:nombre, 'Senadores', :bloque, :provincia)
                            ON CONFLICT DO NOTHING RETURNING id
                        """), {'nombre': nombre, 'bloque': v['bloque'], 'provincia': v['provincia']})
                        row = res.fetchone()
                        if row:
                            cache_senadores[nombre] = row[0]

                    legislador_id = cache_senadores.get(nombre)
                    if not legislador_id:
                        continue

                    session.execute(text("""
                        INSERT INTO votos (legislador_id, acta_id, voto_individual)
                        VALUES (:leg_id, :acta_id, :voto)
                    """), {'leg_id': legislador_id, 'acta_id': acta_id, 'voto': v['voto']})
                    votos_nuevos += 1

                actas_nuevas += 1
                if actas_nuevas % 50 == 0:
                    session.commit()
                    logger.info(f"  Actas: {actas_nuevas} | Votos: {votos_nuevos} | ID: {acta_id}")

                time.sleep(0.3)

            except Exception as e:
                logger.warning(f"  Error en acta {acta_id}: {e}")
                continue

        session.commit()
        logger.info(f"Ingesta completa — Actas nuevas: {actas_nuevas} | Votos nuevos: {votos_nuevos}")

    except Exception as e:
        logger.error(f"Error fatal: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
