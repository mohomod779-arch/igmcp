from __future__ import annotations

import uvicorn

from igmcp.config import get_settings
from igmcp.logging import configure_logging
from igmcp.server import create_app


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
