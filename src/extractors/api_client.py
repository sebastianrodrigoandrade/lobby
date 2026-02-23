import requests
import pandas as pd
import numpy as np
from src.utils import logger


class SessionDiaryProcessor:
    def process_pdf(self, pdf_path):
        logger.info(f"Procesando PDF: {pdf_path}")
        return {"resultado": "datos extraídos"}


class ArgentinaDatosClient:
    """Cliente para Votaciones Nominales HCDN - descarga directa de CSV"""

    URL_DETALLES = "https://datos.hcdn.gob.ar:443/dataset/2e08ab84-09f4-4aac-86b3-9573ca9810db/resource/262cc543-3186-401b-b35e-dcdb2635976d/download/detalle-actas-datos-generales-2.4.csv"

    def get_votes_history(self, chamber: str):
        try:
            logger.info("Descargando votaciones nominales (CSV directo)...")
            df = pd.read_csv(self.URL_DETALLES, encoding='utf-8')
            logger.info(f"Descargados {len(df)} registros de votación.")
            return df.to_dict(orient='records')
        except Exception as e:
            logger.warning(f"No se pudo obtener votaciones: {e}")
            return []


class OpenDataPortalClient:
    """
    Cliente para la API CKAN de Datos HCDN.
    Con paginación completa para cubrir todos los períodos históricos.
    """
    RESOURCE_ID = "22b2d52c-7a0e-426b-ac0a-a3326c388ba6"
    BASE_URL = "https://datos.hcdn.gob.ar/api/3/action/datastore_search"
    PAGE_SIZE = 1000  # Máximo recomendado por la API

    def _get_valid_string(self, value):
        if value is None:
            return None
        s = str(value).strip()
        if s.lower() in ['', 'nan', 'none', 'null', 'nil']:
            return None
        return s

    def extract_hcdn_bills(self):
        try:
            logger.info("Conectando a la API de Datos HCDN (con paginación)...")

            all_records = []
            offset = 0

            while True:
                params = {
                    "resource_id": self.RESOURCE_ID,
                    "limit": self.PAGE_SIZE,
                    "offset": offset
                }

                response = requests.get(
                    self.BASE_URL, params=params,
                    verify=False, timeout=60
                )
                response.raise_for_status()
                data = response.json()

                if not data.get("success"):
                    logger.error("La API respondió success=False")
                    break

                records = data["result"]["records"]
                total = data["result"].get("total", 0)

                if not records:
                    break

                all_records.extend(records)
                offset += len(records)

                logger.info(f"  Descargados {offset}/{total} registros...")

                # Si ya tenemos todos, salir
                if offset >= total:
                    break

            logger.info(f"Total descargado: {len(all_records)} registros crudos.")

            if not all_records:
                return pd.DataFrame()

            clean_rows = []
            registros_sin_id = 0

            for row in all_records:
                r = {k.lower().strip(): v for k, v in row.items()}

                expediente = self._get_valid_string(r.get('exp_diputados'))
                if not expediente:
                    expediente = self._get_valid_string(r.get('exp_senado'))
                if not expediente:
                    p_id = self._get_valid_string(r.get('proyecto_id'))
                    if p_id:
                        expediente = f"INTERNAL-{p_id}"

                if not expediente:
                    registros_sin_id += 1
                    continue

                clean_rows.append({
                    'nro_expediente': expediente,
                    'titulo': self._get_valid_string(r.get('titulo')) or "Sin Título",
                    'fecha_ingreso': self._get_valid_string(r.get('publicacion_fecha')),
                    'estado': self._get_valid_string(r.get('tipo')) or "Desconocido",
                    'autores': self._get_valid_string(r.get('autor')) or "Sin Autor"
                })

            df = pd.DataFrame(clean_rows)

            if registros_sin_id > 0:
                logger.warning(f"Descartados {registros_sin_id} registros sin ID.")

            if not df.empty:
                df['nro_expediente'] = df['nro_expediente'].astype(str)
                df = df[~df['nro_expediente'].isin(['None', '', 'nan'])]

            logger.info(f"DATOS PROCESADOS: {len(df)} proyectos válidos listos para insertar.")
            return df

        except Exception as e:
            logger.error(f"Error procesando datos API: {e}")
            return pd.DataFrame()


class AudienciasScraper:
    BASE_URL = "https://audiencias.mininterior.gob.ar"

    def scrape_hearings(self, legislador_nombre):
        logger.info(f"Scrapeando audiencias para: {legislador_nombre}")
        search_url = f"{self.BASE_URL}/buscar?sujeto={legislador_nombre}"
        try:
            response = requests.get(search_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table', {'id': 'tablaAudiencias'})
            if not table:
                logger.warning(f"No se encontró tabla de audiencias para {legislador_nombre} (o cambió la web).")
                return []
            audiencias = []
            rows = table.find_all('tr')[1:]
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 4:
                    audiencias.append({
                        'fecha': cols[0].text.strip(),
                        'solicitante': cols[1].text.strip(),
                        'motivo': cols[2].text.strip(),
                    })
            return audiencias
        except Exception as e:
            logger.error(f"Error scrapeando audiencias: {e}")
            return []