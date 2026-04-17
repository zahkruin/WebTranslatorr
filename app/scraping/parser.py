"""
Helpers de BeautifulSoup / lxml para parsing HTML.
"""

from bs4 import BeautifulSoup
from typing import Optional


def parse_html(html: str) -> BeautifulSoup:
    """Parsea HTML con lxml."""
    return BeautifulSoup(html, "lxml")


def extract_text(element, default: str = "") -> str:
    """Extrae texto limpio de un elemento."""
    if element is None:
        return default
    return element.get_text(strip=True)


def extract_href(element, default: str = "") -> str:
    """Extrae el atributo href de un elemento."""
    if element is None:
        return default
    return element.get("href", default)


def safe_int(text: str, default: int = 0) -> int:
    """Convierte texto a entero de forma segura."""
    try:
        return int(text)
    except (ValueError, TypeError):
        return default
