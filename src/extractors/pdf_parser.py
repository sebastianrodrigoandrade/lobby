# src/extractors/pdf_parser.py
import re
from pdfminer.high_level import extract_text
from src.utils import logger

class SessionDiaryProcessor:
    # Regex pre-compilados para mejor rendimiento
    RE_AFIRMATIVOS = re.compile(r"AFIRMATIVOS\s*\.+\s*(\d+)", re.IGNORECASE)
    RE_NEGATIVOS = re.compile(r"NEGATIVOS\s*\.+\s*(\d+)", re.IGNORECASE)
    
    def process_pdf(self, pdf_path):
        logger.info(f"Procesando PDF: {pdf_path}")
        try:
            text = extract_text(pdf_path)
            
            resultados = {
                'votos_afirmativos': 0,
                'votos_negativos': 0,
                'texto_raw': text[:500] + "..." # Guardamos un snippet para debug
            }
            
            # Buscar patrones
            match_af = self.RE_AFIRMATIVOS.search(text)
            if match_af:
                resultados['votos_afirmativos'] = int(match_af.group(1))
                
            match_neg = self.RE_NEGATIVOS.search(text)
            if match_neg:
                resultados['votos_negativos'] = int(match_neg.group(1))
            
            return resultados
            
        except Exception as e:
            logger.error(f"Error procesando PDF {pdf_path}: {e}")
            return None