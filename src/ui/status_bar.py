"""
StatusBar - Status indicators for connection and execution

Responsible for:
- Server connection status display
- CST availability indicator
- Execution progress bar
- Error/warning notifications
"""

from PySide6.QtWidgets import QStatusBar, QProgressBar, QLabel
from PySide6.QtCore import Qt, Signal


class AppStatusBar(QStatusBar):
    """Custom status bar for application status indicators"""
    
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        """Initialize status bar widgets"""
        # Server status indicator
        self.server_label = QLabel("Server: Disconnected")
        self.addWidget(self.server_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        self.addPermanentWidget(self.progress_bar)
        
        # CST status indicator
        self.cst_label = QLabel("CST: Not Available")
        self.addPermanentWidget(self.cst_label)
    
    def set_server_connected(self, connected: bool):
        """Update server status indicator
        
        Args:
            connected: True if connected to server
        """
        status = "Connected" if connected else "Disconnected"
        self.server_label.setText(f"Server: {status}")
    
    def set_cst_available(self, available: bool):
        """Update CST availability indicator
        
        Args:
            available: True if CST is available
        """
        status = "Available" if available else "Not Available"
        self.cst_label.setText(f"CST: {status}")
    
    def set_progress(self, current: int, total: int):
        """Update progress bar
        
        Args:
            current: Current progress value
            total: Total progress value
        """
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_bar.setVisible(total > 0)
    
    def show_message(self, message: str, timeout_ms: int = 5000):
        """Display status message
        
        Args:
            message: Message to display
            timeout_ms: Message display duration in milliseconds
        """
        self.showMessage(message, timeout_ms)
