"""
Main Entry Point - Application launcher

Usage:
    python main.py
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from utils.logger import get_logger
from utils.constants import APP_NAME, APP_VERSION


logger = get_logger(__name__)


def main():
    """Main application entry point"""
    logger.info(f"Starting {APP_NAME} v{APP_VERSION}")
    
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    logger.info("Application started successfully")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
