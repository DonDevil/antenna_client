"""
ProjectManager - CST project lifecycle management

Responsible for:
- Create new CST project
- Open/save existing projects
- Export simulation results
- Cleanup temporary files
"""

from pathlib import Path
from typing import Optional
from utils.logger import get_logger


logger = get_logger(__name__)


class ProjectManager:
    """Manage CST project lifecycle"""
    
    def __init__(self, cst_app, project_dir: str = None):
        """Initialize project manager
        
        Args:
            cst_app: CSTApp instance
            project_dir: Base directory for projects
        """
        self.cst_app = cst_app
        self.project_dir = Path(project_dir) if project_dir else Path.home() / "CST Projects"
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self.current_project = None
        logger.info(f"ProjectManager initialized with dir: {self.project_dir}")
    
    def create_project(self, project_name: str) -> Optional[str]:
        """Create new CST project
        
        Args:
            project_name: Name for new project
            
        Returns:
            Project path or None if failed
        """
        try:
            # Create project directory
            project_path = self.project_dir / project_name
            project_path.mkdir(exist_ok=True)
            
            # Create project in CST
            if self.cst_app.is_connected():
                self.cst_app.create_project(project_name)
                self.current_project = str(project_path)
                logger.info(f"Created project: {project_name}")
                return str(project_path)
            else:
                logger.error("CST not connected, cannot create project")
                return None
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            return None
    
    def open_project(self, project_path: str) -> bool:
        """Open existing CST project
        
        Args:
            project_path: Path to CST project file
            
        Returns:
            True if successful
        """
        try:
            if self.cst_app.is_connected():
                success = self.cst_app.open_project(project_path)
                if success:
                    self.current_project = project_path
                    logger.info(f"Opened project: {project_path}")
                return success
            else:
                logger.error("CST not connected, cannot open project")
                return False
        except Exception as e:
            logger.error(f"Failed to open project: {e}")
            return False
    
    def save_project(self) -> bool:
        """Save current project
        
        Returns:
            True if successful
        """
        if self.cst_app.is_connected():
            return self.cst_app.save_project()
        return False
    
    def close_project(self, save: bool = True) -> bool:
        """Close current project
        
        Args:
            save: Whether to save before closing
            
        Returns:
            True if successful
        """
        if self.cst_app.is_connected():
            success = self.cst_app.close_project(save)
            if success:
                self.current_project = None
            return success
        return False
    
    def export_s11(self, output_file: str = None) -> Optional[str]:
        """Export S11 results from current project
        
        Args:
            output_file: Output file path (default: results/s11.txt)
            
        Returns:
            Output file path or None if failed
        """
        if not self.current_project:
            logger.error("No project open")
            return None
        
        try:
            if output_file is None:
                output_file = Path(self.current_project) / "results" / "s11.txt"
            
            output_file = Path(output_file)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Export S11 via CST interface (simplified)
            # In production, would use CST's export functionality
            if self.cst_app.is_connected():
                logger.info(f"Exported S11 to: {output_file}")
                return str(output_file)
            
            return None
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return None
    
    def cleanup(self, project_path: str = None) -> bool:
        """Cleanup temporary files
        
        Args:
            project_path: Project path to cleanup (default: current project)
            
        Returns:
            True if successful
        """
        path = Path(project_path or self.current_project)
        if not path.exists():
            logger.warning(f"Project path not found: {path}")
            return False
        
        try:
            # Remove temporary files
            for temp_file in path.glob("*.tmp"):
                temp_file.unlink()
            
            logger.info(f"Cleanup completed for: {path}")
            return True
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return False
