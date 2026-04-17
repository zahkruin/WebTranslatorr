import io
import zipfile
import logging

logger = logging.getLogger(__name__)

class ZipExtractor:
    @staticmethod
    def extract_epub_from_memory(zip_bytes: bytes) -> bytes | None:
        """
        Toma los bytes de un archivo ZIP, lo procesa en memoria y 
        devuelve los bytes del primer archivo .epub que encuentre.
        Devuelve None si no encuentra ningún epub.
        """
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                for file_info in zf.infolist():
                    if file_info.filename.lower().endswith('.epub'):
                        logger.info(f"Extracting EPUB: {file_info.filename}")
                        with zf.open(file_info) as f:
                            return f.read()
        except zipfile.BadZipFile:
            logger.error("Los bytes proporcionados no corresponden a un archivo ZIP válido.")
        except Exception as e:
            logger.error(f"Error al extraer ZIP en memoria: {e}")
        
        return None
