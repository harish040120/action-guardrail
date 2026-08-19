import logging
import sys
from pythonjsonlogger import jsonlogger


def get_logger(name: str = "action-guardrail"):
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)

    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
