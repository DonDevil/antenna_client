"""
ChatMessageHandler - Handle chat messages and server communication

Responsible for:
- Sending user messages to server
- Receiving and parsing server responses
- Updating chat with responses
- Error handling and retry logic
"""

import asyncio
import json
from typing import Optional
from PySide6.QtCore import QThread, Signal
from comm.server_connector import ServerConnector
from comm.request_builder import RequestBuilder
from comm.response_handler import ResponseHandler
from utils.logger import get_logger
from pathlib import Path


logger = get_logger(__name__)


class MessageSenderWorker(QThread):
    """Worker thread for sending messages to server"""
    
    # Signals
    response_received = Signal(str)  # Server response text
    error_occurred = Signal(str)     # Error message
    
    def __init__(self, user_message: str):
        super().__init__()
        self.user_message = user_message
        self.server_connector = None
        self.request_builder = None
        self.response_handler = None
    
    def run(self):
        """Send message to server and get response"""
        try:
            # Load configuration
            config_path = Path(__file__).parent.parent / "config.json"
            with open(config_path, "r") as f:
                config = json.load(f)
            
            base_url = config.get("server", {}).get("base_url", "http://localhost:8000")
            
            # Run async operation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                response_text = loop.run_until_complete(
                    self._send_message_async(base_url)
                )
            finally:
                loop.close()  # Properly close the event loop
            
            if response_text:
                self.response_received.emit(response_text)
            else:
                self.error_occurred.emit("No response from server")
        
        except Exception as e:
            logger.error(f"Error sending message: {type(e).__name__} - {str(e)}")
            self.error_occurred.emit(f"Error: {str(e)}")
    
    async def _send_message_async(self, base_url: str) -> Optional[str]:
        """Send message to server asynchronously
        
        Args:
            base_url: Server base URL
            
        Returns:
            Response text or None if error
        """
        try:
            # Build request
            request_builder = RequestBuilder()
            optimize_request = request_builder.build_optimize_request(
                user_text=self.user_message
            )
            
            logger.info(f"Sending message to server: {self.user_message}")
            
            # Send to server (10 second timeout for optimization requests)
            async with ServerConnector(base_url, timeout_sec=10) as connector:
                response_data = await connector.post(
                    "/api/v1/optimize",
                    json=optimize_request.model_dump()
                )
            
            logger.info(f"Server response: {response_data}")
            
            # Parse response
            response_handler = ResponseHandler()
            optimize_response = response_handler.parse_optimize_response(response_data)
            
            # Extract message based on status
            if optimize_response.status == "success":
                if optimize_response.command_package:
                    return f"Antenna design optimized!\n\nCommand Package:\n{json.dumps(optimize_response.command_package, indent=2)}"
                else:
                    return "Design optimization completed successfully."
            
            elif optimize_response.status == "clarification_required":
                return f"Need clarification: {optimize_response.clarification}"
            
            elif optimize_response.status == "error":
                return f"Server error: {optimize_response.error_message}"
            
            else:
                return f"Unknown response status: {optimize_response.status}"
        
        except Exception as e:
            error_str = str(e)
            logger.error(f"Failed to send message: {e}")
            
            # Try to extract server error message
            if "422" in error_str:
                return "❌ Message rejected by server. Must be at least 10 characters with valid antenna specs."
            elif "Connection" in error_str or "refused" in error_str:
                return "❌ Cannot connect to server. Is the server running at 192.168.234.89:8000?"
            else:
                return f"❌ Server error: {error_str[:100]}"


class ChatMessageHandler:
    """Manage chat messages and server communication"""
    
    def __init__(self, chat_widget, server_base_url: str = None):
        """Initialize chat message handler
        
        Args:
            chat_widget: Reference to ChatWidget
            server_base_url: Optional server URL override
        """
        self.chat_widget = chat_widget
        self.server_base_url = server_base_url
        self.current_worker = None
        
        # Connect chat signal
        self.chat_widget.message_submitted.connect(self.handle_user_message)
    
    def handle_user_message(self, message: str):
        """Handle user message submission
        
        Args:
            message: User's message text
        """
        logger.info(f"User message received: {message}")
        
        # Validate message length (server requires minLength: 10)
        if len(message) < 10:
            error_msg = "❌ Message too short. Please provide at least 10 characters (e.g., 'I need a 2.4 GHz antenna')"
            self.chat_widget.add_message(error_msg, "system")
            logger.warning(f"Message rejected - too short: {len(message)} chars")
            return
        
        # Show loading indicator
        self.chat_widget.add_message("⏳ Sending to server...", "system")
        
        # Create and start worker thread
        self.current_worker = MessageSenderWorker(message)
        self.current_worker.response_received.connect(self.on_response_received)
        self.current_worker.error_occurred.connect(self.on_error_occurred)
        self.current_worker.start()
    
    def on_response_received(self, response: str):
        """Handle server response
        
        Args:
            response: Response text from server
        """
        logger.info(f"Response received: {response}")
        
        # Remove loading indicator and add response
        if self.chat_widget.messages and self.chat_widget.messages[-1].get("text") == "⏳ Sending to server...":
            self.chat_widget.messages.pop()
            self._refresh_chat_display()
        
        # Add response (check if error)
        if response.startswith("❌"):
            self.chat_widget.add_message(response, "assistant")
        else:
            self.chat_widget.add_message(response, "assistant")
    
    def on_error_occurred(self, error: str):
        """Handle error during message send
        
        Args:
            error: Error message
        """
        logger.error(f"Error occurred: {error}")
        
        # Remove loading indicator
        if self.chat_widget.messages and self.chat_widget.messages[-1].get("text") == "⏳ Sending to server...":
            self.chat_widget.messages.pop()
            self._refresh_chat_display()
        
        # Add error message with helpful hint
        if error == "No response from server":
            error_msg = "❌ No response from server. Try a longer message with antenna specs (e.g., '2.4 GHz patch antenna')"
        else:
            error_msg = f"❌ {error}"
        
        self.chat_widget.add_message(error_msg, "assistant")
    
    def _refresh_chat_display(self):
        """Refresh the chat display to reflect current messages"""
        self.chat_widget.message_display.clear()
        for msg in self.chat_widget.messages:
            sender = msg.get("sender", "user")
            text = msg.get("text", "")
            
            # Determine if it's a system message
            if sender == "system":
                continue  # Skip system messages
            
            # Re-add the message with proper formatting
            # We'll just append text directly since add_message will format it
            timestamp = msg.get("timestamp", "")
            cursor = self.chat_widget.message_display.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            
            from PySide6.QtGui import QTextCharFormat, QColor, QFont
            from PySide6.QtWidgets import QTextEdit
            
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
            
            self.chat_widget.message_display.setTextCursor(cursor)
