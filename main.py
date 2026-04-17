#!/usr/bin/env python3
"""
WebTranslatorr - Universal Torznab Proxy
Entry point for the application.
"""

import uvicorn
from config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.server:app",
        host=settings.HOST,
        port=settings.PORT,
        log_level=settings.LOG_LEVEL.lower(),
        reload=False,
    )
