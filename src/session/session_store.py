"""
SessionStore - In-memory session management with file-based persistence

Responsible for:
- Session CRUD operations
- In-memory caching
- JSON file persistence for recovery
- Design history tracking  
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from utils.logger import get_logger


logger = get_logger(__name__)

# Directory for persisting sessions
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SESSION_DIR = PROJECT_ROOT / "test_checkpoints"


class Session:
    """Represents a single design session"""
    
    def __init__(self, session_id: str, user_request: str, trace_id: Optional[str] = None, design_id: Optional[str] = None):
        """Initialize session
        
        Args:
            session_id: Unique session identifier from server
            user_request: Initial user request
            trace_id: Trace ID from server
            design_id: Design ID from server
        """
        self.session_id = session_id
        self.trace_id = trace_id
        self.design_id = design_id
        self.user_request = user_request
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.status = "active"  # active, completed, failed, paused
        self.current_iteration = 0
        self.command_package: Optional[Dict[str, Any]] = None
        self.results: List[Dict[str, Any]] = []
        self.metadata: Dict[str, Any] = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dict"""
        return {
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "design_id": self.design_id,
            "user_request": self.user_request,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "current_iteration": self.current_iteration,
            "command_package": self.command_package,
            "results": self.results,
            "metadata": self.metadata,
        }


class SessionStore:
    """In-memory session store with file-based persistence"""
    
    def __init__(self):
        """Initialize session store with file persistence"""
        self.sessions: Dict[str, Session] = {}
        
        # Ensure session directory exists
        SESSION_DIR.mkdir(parents=True, exist_ok=True)
        
        # Load existing sessions from disk
        self._load_sessions_from_disk()
        logger.info(f"SessionStore initialized with {len(self.sessions)} persisted sessions")
    
    def create_session(self, user_request: str, session_id: Optional[str] = None, 
                      trace_id: Optional[str] = None, design_id: Optional[str] = None) -> Session:
        """Create new session
        
        Args:
            user_request: Initial user request text
            session_id: Optional session ID (from server)
            trace_id: Optional trace ID (from server)
            design_id: Optional design ID (from server)
            
        Returns:
            Created Session object
        """
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            session.user_request = user_request
            if trace_id:
                session.trace_id = trace_id
            if design_id:
                session.design_id = design_id
            session.updated_at = datetime.now().isoformat()
            self._persist_session(session)
            logger.info(f"Updated session: {session_id}")
            return session

        if not session_id:
            session_id = str(uuid.uuid4())
        
        session = Session(session_id, user_request, trace_id, design_id)
        self.sessions[session_id] = session
        self._persist_session(session)
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
            self._persist_session(session)
            logger.info(f"Updated session {session_id} status: {status}")
    
    def update_session_metadata(self, session_id: str, trace_id: Optional[str] = None, 
                               design_id: Optional[str] = None) -> None:
        """Update session with server-provided metadata
        
        Args:
            session_id: Session identifier
            trace_id: Trace ID from server
            design_id: Design ID from server
        """
        session = self.sessions.get(session_id)
        if session:
            if trace_id:
                session.trace_id = trace_id
            if design_id:
                session.design_id = design_id
            session.updated_at = datetime.now().isoformat()
            self._persist_session(session)
    
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
            self._persist_session(session)
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
            session.current_iteration += 1
            session.updated_at = datetime.now().isoformat()
            self._persist_session(session)
            logger.debug(f"Stored result for session {session_id}")

    def update_session_metadata_map(self, session_id: str, metadata: Dict[str, Any]) -> bool:
        """Merge metadata into a session and persist it.

        Args:
            session_id: Session identifier
            metadata: Metadata fields to merge into the session

        Returns:
            True if the session exists and was updated
        """
        session = self.sessions.get(session_id)
        if not session:
            return False

        session.metadata.update(metadata)
        session.updated_at = datetime.now().isoformat()
        self._persist_session(session)
        logger.debug(f"Updated metadata for session {session_id}")
        return True
    
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
            # Also delete persisted file
            session_file = SESSION_DIR / f"{session_id}.json"
            if session_file.exists():
                session_file.unlink()
            logger.info(f"Deleted session: {session_id}")
            return True
        return False
    
    def _persist_session(self, session: Session) -> None:
        """Persist session to JSON file
        
        Args:
            session: Session object to persist
        """
        try:
            session_file = SESSION_DIR / f"{session.session_id}.json"
            with open(session_file, "w") as f:
                json.dump(session.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist session {session.session_id}: {e}")
    
    def _load_sessions_from_disk(self) -> None:
        """Load all persisted sessions from disk"""
        try:
            for session_file in SESSION_DIR.glob("*.json"):
                try:
                    with open(session_file, "r") as f:
                        data = json.load(f)
                    
                    session_id = data.get("session_id")
                    if session_id and session_id not in self.sessions:
                        # Reconstruct session from persisted data
                        session = Session(
                            session_id,
                            data.get("user_request", ""),
                            data.get("trace_id"),
                            data.get("design_id")
                        )
                        session.created_at = data.get("created_at", session.created_at)
                        session.updated_at = data.get("updated_at", session.updated_at)
                        session.status = data.get("status", "active")
                        session.current_iteration = data.get("current_iteration", 0)
                        session.command_package = data.get("command_package")
                        session.results = data.get("results", [])
                        session.metadata = data.get("metadata", {})
                        
                        self.sessions[session_id] = session
                        logger.info(f"Loaded persisted session: {session_id}")
                except Exception as e:
                    logger.error(f"Failed to load session from {session_file}: {e}")
        except Exception as e:
            logger.error(f"Failed to load sessions from disk: {e}")

