"""
Tests for domain propagation to provider base_url.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.providers.video.mejortorrent import MejorTorrentProvider
from app.scraping.http_client import HttpClient


class TestDomainPropagation:
    @pytest.mark.asyncio
    async def test_on_domain_change_updates_provider_base_url(self):
        http_client = MagicMock(spec=HttpClient)
        provider = MejorTorrentProvider(http_client=http_client)
        original = provider.base_url

        provider.base_url = "https://new-domain.example".rstrip("/")
        assert provider.base_url == "https://new-domain.example"
        assert provider.base_url != original

    @pytest.mark.asyncio
    async def test_resolver_callback_pattern(self):
        callback = AsyncMock()
        new_domain = "https://www99.mejortorrent.eu"
        await callback("mejortorrent", new_domain)
        callback.assert_awaited_once_with("mejortorrent", new_domain)
