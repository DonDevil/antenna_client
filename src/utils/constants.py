"""
Constants - Application-wide constants and defaults
"""

# API Defaults
DEFAULT_SERVER_URL = "http://localhost:8000"
DEFAULT_API_TIMEOUT_SEC = 60
DEFAULT_RETRY_COUNT = 3
DEFAULT_RETRY_BACKOFF = 2.0

# CST Defaults
DEFAULT_CST_EXECUTABLE = r"C:\Program Files\CST Studio Suite 2024\CST Studio.exe"
DEFAULT_CST_PROJECT_DIR = r"C:\Users\{username}\Documents\CST Projects"
DEFAULT_UNITS = "mm"
DEFAULT_FREQUENCY_UNITS = "ghz"

# UI Defaults
DEFAULT_WINDOW_WIDTH = 1200
DEFAULT_WINDOW_HEIGHT = 800
DEFAULT_THEME = "light"  # light or dark

# Logging
LOG_LEVEL = "INFO"
MAX_LOG_FILE_SIZE_MB = 10
LOG_BACKUP_COUNT = 5

# Application Info
APP_NAME = "Antenna Optimization Client"
APP_VERSION = "0.1.0"
APP_AUTHOR = "Antenna Optimization Team"
