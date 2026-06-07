import logging
import os
import sys


DEFAULT_LOG_LEVEL = os.getenv("APP_LOG_LEVEL", "INFO").upper()


class ServiceFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        if not hasattr(record, "service"):
            record.service = "application"
        return super().format(record)


def configure_logging(service_name: str, level: str | None = None) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        ServiceFormatter(
            fmt="%(asctime)s %(levelname)s [%(service)s] %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel((level or DEFAULT_LOG_LEVEL).upper())

    service_logger = logging.getLogger(service_name)
    service_logger = logging.LoggerAdapter(service_logger, {"service": service_name})
    service_logger.info("logging_configured")


def get_logger(name: str, service_name: str) -> logging.LoggerAdapter:
    return logging.LoggerAdapter(logging.getLogger(name), {"service": service_name})
