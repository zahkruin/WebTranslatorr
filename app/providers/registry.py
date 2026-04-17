"""
Registro central de providers.
Patrón Singleton + Service Locator.
"""

import logging
from typing import Optional

from app.providers.base import BaseProvider
from app.core.exceptions import ProviderNotFoundError
from app.core.categories import CategoryMapper


class ProviderRegistry:
    """
    Registro central de providers.
    """

    def __init__(self):
        self._providers: dict[str, BaseProvider] = {}

    def register(self, provider: BaseProvider) -> None:
        """Registra un provider."""
        self._providers[provider.provider_id] = provider
        logging.info(f"Provider registrado: {provider.display_name} ({provider.provider_id})")

    def get(self, provider_id: str) -> BaseProvider:
        """Obtiene un provider por ID."""
        if provider_id not in self._providers:
            raise ProviderNotFoundError(f"Provider '{provider_id}' no registrado")
        return self._providers[provider_id]

    def get_by_categories(self, categories: list[int]) -> list[BaseProvider]:
        """Devuelve providers que soporten al menos una de las categorías pedidas."""
        matched = []
        for provider in self._providers.values():
            caps = provider.get_capabilities()
            if any(cat in caps.supported_categories for cat in categories):
                matched.append(provider)
            elif any(self._parent_match(cat, caps.supported_categories) for cat in categories):
                matched.append(provider)
        return matched

    def get_by_content_type(self, content_type: str) -> list[BaseProvider]:
        """Devuelve providers por tipo de contenido (books, movies, tv)."""
        matched = []
        for provider in self._providers.values():
            caps = provider.get_capabilities()
            if content_type == "books" and caps.supports_book_search:
                matched.append(provider)
            elif content_type == "movies" and caps.supports_movie_search:
                matched.append(provider)
            elif content_type == "tv" and caps.supports_tv_search:
                matched.append(provider)
        return matched

    def get_all(self) -> list[BaseProvider]:
        """Devuelve todos los providers registrados."""
        return list(self._providers.values())

    def unregister(self, provider_id: str) -> None:
        """Desregistra un provider."""
        if provider_id in self._providers:
            del self._providers[provider_id]
            logging.info(f"Provider desregistrado: {provider_id}")

    def clear(self) -> None:
        """Limpia todos los providers."""
        self._providers.clear()

    @staticmethod
    def _parent_match(requested_cat: int, supported: list[int]) -> bool:
        """Verifica si la categoría padre está soportada."""
        parent = CategoryMapper.get_parent_category(requested_cat)
        return parent in supported


# Instancia global del registro
registry = ProviderRegistry()
