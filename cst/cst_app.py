"""
CSTApp - COM interface to CST Studio Suite

Responsible for:
- Connect to CST via COM
- Application lifecycle (launch, close)
- MWS (Model Workspace) access
- Error handling for COM failures
"""

from typing import Optional
import platform
from utils.logger import get_logger


logger = get_logger(__name__)


class CSTApp:
    """COM interface to CST Studio Suite"""
    
    def __init__(self, executable_path: str = None):
        """Initialize CST application interface
        
        Args:
            executable_path: Path to CST Studio executable
        """
        self.executable_path = executable_path or r"C:\Program Files\CST Studio Suite 2024\CST Studio.exe"
        self.app = None
        self.mws = None
        self.connected = False
        
        logger.info("CSTApp initialized")
    
    def connect(self) -> bool:
        """Connect to CST via COM
        
        Returns:
            True if connected successfully
        """
        if platform.system() != "Windows":
            logger.error("CST requires Windows")
            return False
        
        try:
            # Try to create COM object for existing instance
            import win32com.client
            try:
                self.app = win32com.client.GetObject(class_="CSTStudio.Application")
                logger.info("Connected to existing CST instance")
            except:
                # Create new instance
                self.app = win32com.client.Dispatch("CSTStudio.Application")
                logger.info("Created new CST instance")
            
            self.connected = True
            return True
        except Exception as e:
            logger.error(f"Failed to connect to CST: {e}")
            return False
    
    def create_project(self, project_name: str) -> Optional[str]:
        """Create new CST project
        
        Args:
            project_name: Name for new project
            
        Returns:
            Project file path or None if failed
        """
        if not self.connected or not self.app:
            logger.error("Not connected to CST")
            return None
        
        try:
            # Create new project
            # self.mws = self.app.NewMWS(project_name)
            logger.info(f"Created project: {project_name}")
            # TODO: Implement actual project creation
            return None
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            return None
    
    def open_project(self, project_path: str) -> bool:
        """Open existing CST project
        
        Args:
            project_path: Path to .cst project file
            
        Returns:
            True if project opened
        """
        if not self.connected or not self.app:
            logger.error("Not connected to CST")
            return False
        
        try:
            # self.mws = self.app.OpenFile(project_path)
            logger.info(f"Opened project: {project_path}")
            # TODO: Implement actual file opening
            return True
        except Exception as e:
            logger.error(f"Failed to open project: {e}")
            return False
    
    def execute_macro(self, macro_code: str) -> bool:
        """Execute VBA macro in CST
        
        Args:
            macro_code: VBA macro code
            
        Returns:
            True if executed successfully
        """
        if not self.mws:
            logger.error("No active project")
            return False
        
        try:
            # Execute VBA macro
            # self.mws.Evaluate(macro_code)
            logger.debug("Macro executed")
            # TODO: Implement actual macro execution
            return True
        except Exception as e:
            logger.error(f"Failed to execute macro: {e}")
            return False
    
    def get_project_path(self) -> Optional[str]:
        """Get path of currently open project
        
        Returns:
            Project file path or None
        """
        if not self.mws:
            return None
        
        try:
            # path = self.mws.GetProjectPath()
            # TODO: Implement actual path retrieval
            return None
        except Exception as e:
            logger.error(f"Failed to get project path: {e}")
            return None
    
    def close_project(self, save: bool = False) -> bool:
        """Close active project
        
        Args:
            save: Whether to save project before closing
            
        Returns:
            True if closed successfully
        """
        if not self.mws:
            return True
        
        try:
            # if save:
            #     self.mws.Save()
            # self.mws.Quit()
            self.mws = None
            logger.info("Project closed")
            # TODO: Implement actual close
            return True
        except Exception as e:
            logger.error(f"Failed to close project: {e}")
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from CST
        
        Returns:
            True if disconnected
        """
        try:
            self.close_project(save=False)
            # if self.app:
            #     self.app.Quit()
            self.app = None
            self.connected = False
            logger.info("Disconnected from CST")
            return True
        except Exception as e:
            logger.error(f"Failed to disconnect: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if connected to CST
        
        Returns:
            True if connected
        """
        return self.connected and self.app is not None
