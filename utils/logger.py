"""
Logger - Structured logging configuration.

Provides:
- Multiple handlers (console, file, rotating)
- Log levels (DEBUG, INFO, WARNING, ERROR)
- Windows-safe console output for Unicode-rich UI messages
"""

import logging
import logging.handlers
from pathlib import Path


# Create logs directory
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "antenna_client.log"
LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class SafeConsoleHandler(logging.StreamHandler):
    """Console handler that degrades gracefully on legacy Windows encodings."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
        except UnicodeEncodeError:
            try:
                msg = self.format(record)
                stream = self.stream
                encoding = getattr(stream, "encoding", None) or "utf-8"
                safe_msg = msg.encode(encoding, errors="replace").decode(encoding, errors="replace")
                stream.write(safe_msg + self.terminator)
                self.flush()
            except Exception:
                self.handleError(record)


def get_logger(name: str) -> logging.Logger:
    """Get configured logger for module
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Skip if logger already configured
    if logger.handlers:
        return logger
    
    logger.setLevel(LOG_LEVEL)
    logger.propagate = False
    
    # Console handler
    console_handler = SafeConsoleHandler()
    console_handler.setLevel(LOG_LEVEL)
    console_formatter = logging.Formatter(LOG_FORMAT)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler with rotation
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            LOG_FILE,
            encoding="utf-8",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(LOG_LEVEL)
        file_formatter = logging.Formatter(LOG_FORMAT)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Could not setup file logging: {e}")
    
    return logger
