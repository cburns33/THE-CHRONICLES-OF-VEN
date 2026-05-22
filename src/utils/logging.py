"""Shared logger. Writes to data/sync.log and stdout."""

import logging
import os
from pathlib import Path
from src.utils.config import load_config

_configured = False


def get_logger(name: str = "inherited_cloud") -> logging.Logger:
    global _configured
    logger = logging.getLogger(name)

    if not _configured:
        cfg = load_config()
        log_path = Path(cfg["paths"]["log_path"])
        log_path.parent.mkdir(parents=True, exist_ok=True)

        level = logging.DEBUG if os.getenv("DEBUG", "").lower() == "true" else logging.INFO

        fmt = logging.Formatter(
            "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(fmt)

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(fmt)

        logger.setLevel(level)
        logger.addHandler(file_handler)
        logger.addHandler(stream_handler)
        logger.propagate = False
        _configured = True

    return logger
