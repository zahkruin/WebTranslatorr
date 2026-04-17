"""
Genera XML de errores Torznab (códigos 100, 200, 201...).
"""

from xml.etree.ElementTree import Element, SubElement, tostring


class TorznabErrors:
    """Errores estándar Torznab."""

    # Códigos de error
    INCORRECT_API_KEY = 100
    ACCOUNT_SUSPENDED = 101
    MAX_API_REACHED = 102
    MAX_DOWNLOAD_REACHED = 103
    NO_SEARCH_RESULTS = 200
    MISSING_SEARCH_PARAM = 201
    INVALID_CAT = 202
    MAX_ITEMS_REACHED = 300
    SERVER_ERROR = 500

    @staticmethod
    def error_xml(code: int, description: str) -> str:
        """Genera XML de error Torznab."""
        error = Element("error", attrib={
            "code": str(code),
            "description": description,
        })
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(error, encoding="unicode")

    @classmethod
    def incorrect_api_key(cls) -> str:
        return cls.error_xml(cls.INCORRECT_API_KEY, "Incorrect API Key")

    @classmethod
    def account_suspended(cls) -> str:
        return cls.error_xml(cls.ACCOUNT_SUSPENDED, "Account suspended")

    @classmethod
    def no_search_results(cls) -> str:
        return cls.error_xml(cls.NO_SEARCH_RESULTS, "No search results found")

    @classmethod
    def missing_search_param(cls) -> str:
        return cls.error_xml(cls.MISSING_SEARCH_PARAM, "Missing search parameter (q)")

    @classmethod
    def invalid_category(cls) -> str:
        return cls.error_xml(cls.INVALID_CAT, "Invalid category")

    @classmethod
    def server_error(cls, msg: str = "Server error") -> str:
        return cls.error_xml(cls.SERVER_ERROR, msg)
