import json
import logging
import sys
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any

REQUEST_ID_CTX_VAR: ContextVar[str] = ContextVar("request_id", default="-")
RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
LEVEL_COLORS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[35m",
}
LOGGER_NAME_ALIASES = {
    "uvicorn.error": "uvicorn",
    "uvicorn.access": "uvicorn",
}

STANDARD_LOG_RECORD_KEYS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}
IGNORED_EXTRA_KEYS = {"color_message", "taskName"}


def set_request_id(request_id: str) -> Token[str]:
    return REQUEST_ID_CTX_VAR.set(request_id)


def reset_request_id(token: Token[str]) -> None:
    REQUEST_ID_CTX_VAR.reset(token)


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = REQUEST_ID_CTX_VAR.get("-")
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in STANDARD_LOG_RECORD_KEYS
            and key != "request_id"
            and key not in IGNORED_EXTRA_KEYS
        }
        if extras:
            payload["extra"] = extras

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=True)


class ConsoleFormatter(logging.Formatter):
    def __init__(self) -> None:
        super().__init__(datefmt="%H:%M:%S")
        self._use_colors = sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().astimezone().strftime(self.datefmt or "%H:%M:%S")
        level = f"{record.levelname:<8}"
        logger_name = LOGGER_NAME_ALIASES.get(record.name, record.name)
        message = record.getMessage()
        request_id = getattr(record, "request_id", "-")

        parts = [self._dim(timestamp), self._format_level(level), self._bold(logger_name), message]
        if request_id != "-":
            parts.append(self._dim(f"request_id={request_id}"))

        extras = self._collect_extras(record)
        if extras:
            parts.extend(f"{key}={self._stringify(value)}" for key, value in extras.items())

        output = " ".join(parts)
        if record.exc_info:
            output = f"{output}\n{self.formatException(record.exc_info)}"
        return output

    def _collect_extras(self, record: logging.LogRecord) -> dict[str, Any]:
        return {
            key: value
            for key, value in record.__dict__.items()
            if key not in STANDARD_LOG_RECORD_KEYS
            and key != "request_id"
            and key not in IGNORED_EXTRA_KEYS
        }

    def _stringify(self, value: Any) -> str:
        if isinstance(value, str):
            if any(char.isspace() for char in value):
                return json.dumps(value, ensure_ascii=True)
            return value
        return json.dumps(value, default=str, ensure_ascii=True)

    def _format_level(self, level: str) -> str:
        if not self._use_colors:
            return level
        color = LEVEL_COLORS.get(level.strip(), "")
        return f"{color}{level}{RESET}" if color else level

    def _dim(self, text: str) -> str:
        if not self._use_colors:
            return text
        return f"{DIM}{text}{RESET}"

    def _bold(self, text: str) -> str:
        if not self._use_colors:
            return text
        return f"{BOLD}{text}{RESET}"


def configure_logging(log_level: str, json_logs: bool = True) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestContextFilter())
    if json_logs:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(ConsoleFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(level)
    root_logger.addHandler(handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.setLevel(level)
        logger.propagate = True
