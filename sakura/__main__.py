"""Entry point for Sakura."""

import logging
import os

from .core import run

if __name__ == "__main__":
    # Configure logging
    log_level = logging.DEBUG if os.getenv("SAKURA_DEBUG") else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    run()
