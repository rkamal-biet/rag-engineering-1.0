"""One consistent log format for the whole application."""

import logging


def get_logger(name: str = "first_rag") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:                      # avoid duplicate handlers on re-import / reload
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                                               "%H:%M:%S"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger
