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


class ProviderBlockedError(ScrapingError):
    """Raised when a provider returns a bot/challenge page instead of content."""
    pass


class DownloadError(WebTranslatorrError):
    """Raised when a download fails."""
    pass


class ValidationError(WebTranslatorrError):
    """Raised when request validation fails."""
    pass


class DownloadTooLargeError(DownloadError):
    """Raised when a download exceeds the configured size limit."""
    pass


class ZipBombError(DownloadError):
    """Raised when a ZIP archive exceeds safety limits."""
    pass
