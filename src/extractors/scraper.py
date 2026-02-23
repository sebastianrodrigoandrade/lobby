import requests
from bs4 import BeautifulSoup
from src.utils import logger

class AudienciasScraper:
    """
    Scraper para el Registro Único de Audiencias.
    """
    BASE_URL = "https://audiencias.mininterior.gob.ar"
    
    def scrape_hearings(self, legislador_nombre):
        logger.info(f"Scrapeando audiencias para: {legislador_nombre}")
        
        # Simulamos búsqueda GET (ajustar según la web real)
        search_url = f"{self.BASE_URL}/buscar?sujeto={legislador_nombre}"
        
        try:
            response = requests.get(search_url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Traceability Check
            table = soup.find('table', {'id': 'tablaAudiencias'})
            if not table:
                # No es crítico si no hay tabla, puede ser que no tenga audiencias
                logger.warning(f"No se encontró tabla de audiencias para {legislador_nombre} (o cambió la web).")
                return []
            
            audiencias = []
            rows = table.find_all('tr')[1:] # Skip header
            
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    audiencias.append({
                        'fecha': cols[0].text.strip(),
                        'solicitante': cols[1].text.strip(),
                        'motivo': cols[2].text.strip(),
                    })
            return audiencias
            
        except Exception as e:
            logger.error(f"Error scrapeando audiencias: {e}")
            return []