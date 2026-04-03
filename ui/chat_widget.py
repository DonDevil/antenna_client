"""
ChatWidget - Conversational interface for antenna design requests

Responsible for:
- Message display (user/assistant)
- User input capture
- Message history scrolling
- Markdown rendering support
- Message persistence to session
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QScrollArea, QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QFont
from datetime import datetime


class ChatWidget(QWidget):
    """Widget for chat-based antenna design interface"""
    
    # Signal emitted when user submits a message
    message_submitted = Signal(str)
    
    def __init__(self):
        super().__init__()
        self.messages = []
        self.init_ui()
    
    def init_ui(self):
        """Initialize chat widget layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Message display area
        self.message_display = QTextEdit()
        self.message_display.setReadOnly(True)
        self.message_display.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 8px;
                font-family: "Segoe UI", Arial;
                font-size: 11pt;
            }
        """)
        layout.addWidget(self.message_display)
        
        # Input area
        input_layout = QHBoxLayout()
        
        self.input_field = QTextEdit()
        self.input_field.setMaximumHeight(70)
        self.input_field.setPlaceholderText("Enter design request... (Press Enter to send, Shift+Enter for new line)")
        self.input_field.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #cccccc;
                border-radius: 4px;
                padding: 8px;
                font-family: "Segoe UI", Arial;
                font-size: 10pt;
            }
            QTextEdit:focus {
                border: 2px solid #1976d2;
                color: #000000;
            }
        """)
        
        # Handle Enter key for send
        self.input_field.keyPressEvent = self._handle_key_press
        input_layout.addWidget(self.input_field)
        
        self.send_button = QPushButton("Send")
        self.send_button.setMaximumWidth(80)
        self.send_button.setMinimumHeight(50)
        self.send_button.setStyleSheet("""
            QPushButton {
                background-color: #1976d2;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1565c0;
            }
            QPushButton:pressed {
                background-color: #0d47a1;
            }
        """)
        self.send_button.clicked.connect(self.on_send)
        input_layout.addWidget(self.send_button)
        
        layout.addLayout(input_layout)
    
    def _handle_key_press(self, event):
        """Handle key press in input field
        
        Behavior:
        - Enter: send message
        - Shift+Enter: insert new line
        - Escape: clear input
        """
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            # If Shift is held, insert newline
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                QTextEdit.keyPressEvent(self.input_field, event)
            else:
                # Enter without Shift -> send message
                self.on_send()
        elif event.key() == Qt.Key.Key_Escape:
            # Clear input on Escape
            self.input_field.clear()
        else:
            QTextEdit.keyPressEvent(self.input_field, event)
    
    def on_send(self):
        """Handle send button click"""
        text = self.input_field.toPlainText().strip()
        if text:
            self.add_message(text, "user")
            self.message_submitted.emit(text)
            self.input_field.clear()
    
    def add_message(self, text: str, sender: str = "user"):
        """Add message to chat display
        
        Args:
            text: Message content
            sender: "user" or "assistant"
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        cursor = self.message_display.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        
        # Format for different senders
        if sender == "user":
            fmt = QTextCharFormat()
            fmt.setForeground(QColor("#1976d2"))
            fmt.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            cursor.insertText(f"You ({timestamp}):\n", fmt)
            
            fmt_content = QTextCharFormat()
            fmt_content.setForeground(QColor("#333333"))
            cursor.insertText(f"{text}\n\n", fmt_content)
        else:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor("#2e7d32"))
            fmt.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            cursor.insertText(f"Assistant ({timestamp}):\n", fmt)
            
            fmt_content = QTextCharFormat()
            fmt_content.setForeground(QColor("#333333"))
            cursor.insertText(f"{text}\n\n", fmt_content)
        
        self.message_display.setTextCursor(cursor)
        self.messages.append({"sender": sender, "text": text, "timestamp": timestamp})
    
    def display_markdown(self, markdown_text: str):
        """Display markdown-formatted text as assistant message
        
        Args:
            markdown_text: Markdown content to render
        """
        # For now, just display as plain text
        # TODO: Implement proper markdown rendering
        self.add_message(markdown_text, "assistant")
    
    def clear_history(self):
        """Clear chat history"""
        self.message_display.clear()
        self.messages = []
    
    def get_messages(self) -> list:
        """Get all messages
        
        Returns:
            List of message dictionaries
        """
        return self.messages
