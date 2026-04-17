"""
Custom exceptions for WebTranslatorr.
"""


class WebTranslatorrError(Exception):
    """Base exception for all application errors."""
    pass


class ProviderNotFoundError(WebTranslatorrError):
    """Raised when a requested provider is not registered."""
    pass


class ProviderError(WebTranslatorrError):
    """Raised when a provider fails to perform an operation."""
    pass


class ScrapingError(WebTranslatorrError):
    """Raised when web scraping fails."""
    pass


class DownloadError(WebTranslatorrError):
    """Raised when a download fails."""
    pass


class ValidationError(WebTranslatorrError):
    """Raised when request validation fails."""
    pass
