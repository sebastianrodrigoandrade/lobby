"""
actualizar.py — Orquestador de ingesta incremental
Corre semanalmente via GitHub Actions o manualmente con: python actualizar.py

Scripts que requieren ejecución manual (no automatizables):
  - ingestar_temario.py     (requiere CSV generado manualmente)
  - scrapear_reuniones.py   (requiere Selenium)
  - scrapear_sesiones.py    (requiere Selenium)
"""
import time
import os
from src.utils import logger

EN_ACTIONS = os.getenv('GITHUB_ACTIONS') == 'true'

def paso(nombre, fn):
    logger.info(f"\n{'='*50}")
    logger.info(f"PASO: {nombre}")
    logger.info('='*50)
    try:
        fn()
        logger.info(f"OK: {nombre} completado")
    except Exception as e:
        logger.error(f"FALLO: {nombre} - {e}")

if __name__ == "__main__":
    logger.info("=== ACTUALIZACION SEMANAL LOBBY ===")
    inicio = time.time()

    import ingesta_senado
    paso("Votaciones Senado", ingesta_senado.main)

    import ingestar_sesiones
    paso("Sesiones HCDN", ingestar_sesiones.main)

    import scrapear_comisiones
    paso("Comisiones", scrapear_comisiones.main)

    if not EN_ACTIONS:
        import scrapear_reuniones
        paso("Reuniones de comisiones", scrapear_reuniones.main)
    else:
        logger.info("SKIP: Reuniones (requiere Selenium, correr manualmente)")

    minutos = (time.time() - inicio) / 60
    logger.info(f"\n=== FIN - {minutos:.1f} minutos ===")
