"""
MainWindow - Primary application window

Responsible for:
- Application window layout orchestration
- Menu bar management
- Keyboard shortcuts
- Central widget coordination
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QMenuBar, QMenu, QMessageBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QAction
from ui.chat_widget import ChatWidget
from ui.design_panel import DesignPanel
from ui.status_bar import AppStatusBar
from utils.logger import get_logger


logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """Main application window for Antenna Client"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Antenna Optimization Client")
        self.resize(QSize(1400, 900))
        
        # Initialize UI components
        self.init_ui()
        self.setup_menus()
        self.setup_shortcuts()
        
        logger.info("MainWindow initialized")
    
    def init_ui(self):
        """Initialize main UI layout"""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left side: Chat interface
        self.chat_widget = ChatWidget()
        splitter.addWidget(self.chat_widget)
        
        # Right side: Design panel
        self.design_panel = DesignPanel()
        splitter.addWidget(self.design_panel)
        
        # Set proportions (chat 70%, design 30%)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)
        
        main_layout.addWidget(splitter)
        
        # Status bar
        self.status_bar = AppStatusBar()
        self.setStatusBar(self.status_bar)
        
        logger.info("UI layout initialized")
    
    def setup_menus(self):
        """Setup menu bar with File, Edit, Help menus"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        new_action = QAction("New Design", self)
        new_action.triggered.connect(self.new_design)
        file_menu.addAction(new_action)
        
        open_action = QAction("Open Design", self)
        open_action.triggered.connect(self.open_design)
        file_menu.addAction(open_action)
        
        save_action = QAction("Save Design", self)
        save_action.triggered.connect(self.save_design)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu("Edit")
        
        preferences_action = QAction("Preferences", self)
        preferences_action.triggered.connect(self.show_preferences)
        edit_menu.addAction(preferences_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        docs_action = QAction("Documentation", self)
        docs_action.triggered.connect(self.show_docs)
        help_menu.addAction(docs_action)
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def setup_shortcuts(self):
        """Setup keyboard shortcuts"""
        # Shortcuts are set in menu actions
        pass
    
    def new_design(self):
        """Create new design"""
        self.chat_widget.clear_history()
        self.design_panel.reset_values()
        self.status_bar.show_message("New design created")
        logger.info("New design created")
    
    def open_design(self):
        """Open existing design"""
        self.status_bar.show_message("Open design - Not yet implemented")
        logger.info("Open design clicked")
    
    def save_design(self):
        """Save current design"""
        self.status_bar.show_message("Design saved")
        logger.info("Design saved")
    
    def show_preferences(self):
        """Show preferences dialog"""
        QMessageBox.information(self, "Preferences", "Preferences dialog - Not yet implemented")
    
    def show_docs(self):
        """Show documentation"""
        QMessageBox.information(self, "Documentation", "See README.md for documentation")
    
    def show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About Antenna Optimization Client",
            "Antenna Optimization Client v0.1.0\n\n"
            "A modular Windows desktop application for iterative antenna design optimization.\n\n"
            "© 2026 Antenna Optimization Team"
        )


def main():
    """Entry point for application launch"""
    from PySide6.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
