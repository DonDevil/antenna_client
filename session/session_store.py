"""
SessionStore - In-memory session management with SQLite persistence

Responsible for:
- Session CRUD operations
- In-memory caching
- SQLite backend for persistence
- Design history tracking
"""

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from utils.logger import get_logger


logger = get_logger(__name__)


class Session:
    """Represents a single design session"""
    
    def __init__(self, session_id: str, user_request: str):
        """Initialize session
        
        Args:
            session_id: Unique session identifier
            user_request: Initial user request
        """
        self.session_id = session_id
        self.user_request = user_request
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.status = "active"  # active, completed, failed, paused
        self.command_package = None
        self.results = []
        self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dict"""
        return {
            "session_id": self.session_id,
            "user_request": self.user_request,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "command_package": self.command_package,
            "results": self.results,
            "metadata": self.metadata,
        }


class SessionStore:
    """In-memory session store with optional SQLite persistence"""
    
    def __init__(self):
        """Initialize session store
        
        TODO: Add SQLite backend initialization
        """
        self.sessions: Dict[str, Session] = {}
        logger.info("SessionStore initialized")
    
    def create_session(self, user_request: str) -> Session:
        """Create new session
        
        Args:
            user_request: Initial user request text
            
        Returns:
            Created Session object
        """
        session_id = str(uuid.uuid4())
        session = Session(session_id, user_request)
        self.sessions[session_id] = session
        logger.info(f"Created session: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve session by ID
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session object or None if not found
        """
        return self.sessions.get(session_id)
    
    def update_session_status(self, session_id: str, status: str) -> None:
        """Update session status
        
        Args:
            session_id: Session identifier
            status: New status (active, completed, failed, paused)
        """
        session = self.sessions.get(session_id)
        if session:
            session.status = status
            session.updated_at = datetime.now().isoformat()
            logger.info(f"Updated session {session_id} status: {status}")
    
    def store_command_package(self, session_id: str, package: Dict) -> None:
        """Store command package for session
        
        Args:
            session_id: Session identifier
            package: Command package from server
        """
        session = self.sessions.get(session_id)
        if session:
            session.command_package = package
            session.updated_at = datetime.now().isoformat()
            logger.debug(f"Stored command package for session {session_id}")
    
    def store_result(self, session_id: str, result: Dict) -> None:
        """Store execution result for session
        
        Args:
            session_id: Session identifier
            result: Execution result data
        """
        session = self.sessions.get(session_id)
        if session:
            session.results.append(result)
            session.updated_at = datetime.now().isoformat()
            logger.debug(f"Stored result for session {session_id}")
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions
        
        Returns:
            List of session dictionaries
        """
        return [s.to_dict() for s in self.sessions.values()]
    
    def delete_session(self, session_id: str) -> bool:
        """Delete session
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if deleted, False if not found
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
            return True
        return False
