import io
import logging
import zipfile

from config import settings
from app.core.exceptions import ZipBombError

logger = logging.getLogger(__name__)


class ZipExtractor:
    @staticmethod
    def extract_epub_from_memory(zip_bytes: bytes) -> bytes | None:
        try:
            compressed_size = len(zip_bytes)
            if compressed_size == 0:
                return None

            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                entries = zf.infolist()
                if len(entries) > settings.ZIP_MAX_ENTRIES:
                    raise ZipBombError(
                        f"ZIP has too many entries: {len(entries)}"
                    )

                total_uncompressed = 0
                for file_info in entries:
                    file_size = file_info.file_size
                    total_uncompressed += file_size
                    if total_uncompressed > settings.ZIP_MAX_UNCOMPRESSED_BYTES:
                        raise ZipBombError("ZIP uncompressed size exceeds limit")
                    if compressed_size > 0:
                        ratio = total_uncompressed / compressed_size
                        if ratio > settings.ZIP_MAX_RATIO:
                            raise ZipBombError("ZIP compression ratio exceeds limit")

                    if file_info.filename.lower().endswith(".epub"):
                        logger.info(f"Extracting EPUB: {file_info.filename}")
                        with zf.open(file_info) as f:
                            return f.read()
        except ZipBombError:
            raise
        except zipfile.BadZipFile:
            logger.error("Los bytes proporcionados no corresponden a un archivo ZIP válido.")
        except Exception as e:
            logger.error(f"Error al extraer ZIP en memoria: {e}")

        return None
