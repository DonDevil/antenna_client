"""
ChatHistory - Persistent chat message storage

Responsible for:
- Store chat messages to session
- Retrieve chat history by session ID
- Export chat logs
"""

from typing import List, Dict, Any
from datetime import datetime


class ChatHistory:
    """Manages chat message persistence"""
    
    def __init__(self, session_id: str):
        """Initialize chat history for session
        
        Args:
            session_id: Session identifier
        """
        self.session_id = session_id
        self.messages: List[Dict[str, Any]] = []
    
    def add_message(self, sender: str, text: str, timestamp: str = None) -> None:
        """Add message to history
        
        Args:
            sender: "user" or "assistant"
            text: Message content
            timestamp: Optional timestamp (defaults to now)
        """
        if not timestamp:
            timestamp = datetime.now().isoformat()
        
        self.messages.append({
            "sender": sender,
            "text": text,
            "timestamp": timestamp
        })
    
    def get_messages(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get messages from history
        
        Args:
            limit: Maximum number of messages to return (most recent)
            
        Returns:
            List of message dictionaries
        """
        if limit:
            return self.messages[-limit:]
        return self.messages
    
    def clear(self) -> None:
        """Clear all messages"""
        self.messages = []
    
    def export_to_dict(self) -> Dict[str, Any]:
        """Export history to dict
        
        Returns:
            Dictionary representation
        """
        return {
            "session_id": self.session_id,
            "message_count": len(self.messages),
            "messages": self.messages
        }
