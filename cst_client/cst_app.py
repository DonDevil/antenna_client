"""CST Studio interface wrapper backed by the official CST Python API."""

from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Optional

from utils.logger import get_logger


logger = get_logger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"Failed to load CST config: {exc}")
        return {}


class CSTApp:
    """Thin wrapper over the CST design environment and active 3D project."""
    
    def __init__(self, executable_path: str = None, project_dir: str = None):
        self.executable_path = executable_path or r"C:\Program Files\CST Studio Suite 2024\CST Studio.exe"
        config = _load_config()
        configured_project_dir = config.get("cst", {}).get("project_dir")
        self.project_dir = Path(project_dir or configured_project_dir or (Path.home() / "CST Projects"))
        self.project_dir.mkdir(parents=True, exist_ok=True)

        self.app = None
        self.project = None
        self.mws = None
        self.connected = False
        self._history_counter = 0
        
        logger.info("CSTApp initialized")

    def _sync_project_handles(self) -> None:
        self.mws = self.project.model3d if self.project is not None else None

    def _refresh_active_project(self) -> None:
        if self.app is None:
            return
        try:
            self.project = self.app.active_project() if self.app.has_active_project() else self.project
            self._sync_project_handles()
        except Exception as exc:
            logger.debug(f"Failed to refresh active CST project handle: {exc}")
    
    def connect(self) -> bool:
        """Connect to a running CST design environment or create one."""
        if platform.system() != "Windows":
            logger.error("CST requires Windows")
            return False
        
        try:
            import cst.interface

            self.app = cst.interface.DesignEnvironment.connect_to_any_or_new()
            self.project = self.app.active_project() if self.app.has_active_project() else None
            self._sync_project_handles()
            self.connected = True
            if self.project is not None:
                logger.info(f"Connected to CST with active project: {self.project.filename()}")
            else:
                logger.info("Connected to CST without an active project")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to CST: {e}")
            return False
    
    def create_project(self, project_name: str) -> Optional[str]:
        """Create a new MWS project and persist it with the requested filename."""
        if not self.connected or self.app is None:
            logger.error("Not connected to CST")
            return None
        
        try:
            safe_name = "_".join(project_name.strip().split()) or "command_console_project"
            self.project = self.app.new_mws()
            self._sync_project_handles()
            project_path = self.project_dir / f"{safe_name}.cst"
            self.mws.SaveAs(str(project_path.resolve()), True)
            self._refresh_active_project()
            logger.info(f"Created project: {project_path}")
            return str(project_path.resolve())
        except Exception as e:
            logger.error(f"Failed to create project: {e}")
            return None
    
    def open_project(self, project_path: str) -> bool:
        """Open an existing CST project file."""
        if not self.connected or self.app is None:
            logger.error("Not connected to CST")
            return False
        
        try:
            self.project = self.app.open_project(str(Path(project_path).resolve()))
            self._sync_project_handles()
            self._refresh_active_project()
            logger.info(f"Opened project: {project_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to open project: {e}")
            return False
    
    def execute_macro(self, macro_code: str, title: str = "copilot_macro") -> bool:
        """Execute VBA macro by adding it to CST history and rebuilding."""
        if not self.mws:
            logger.error("No active project")
            return False
        
        try:
            self._refresh_active_project()
            if not self.mws:
                logger.error("No active project after refresh")
                return False
            self._history_counter += 1
            history_title = f"{title}_{self._history_counter:03d}"
            self.mws.add_to_history(history_title, macro_code)
            self.mws.full_history_rebuild()
            self._refresh_active_project()
            logger.debug(f"Macro executed via CST history: {history_title}")
            return True
        except Exception as e:
            logger.error(f"Failed to execute macro: {e}")
            return False
    
    def get_project_path(self) -> Optional[str]:
        """Get the currently open CST project path."""
        if self.project is None:
            return None
        
        try:
            return str(self.project.filename())
        except Exception as e:
            logger.error(f"Failed to get project path: {e}")
            return None
    
    def close_project(self, save: bool = False) -> bool:
        """Close the active project."""
        if self.project is None:
            return True
        
        try:
            if save:
                self.project.save()
            self.project.close()
            self.project = None
            self.mws = None
            logger.info("Project closed")
            return True
        except Exception as e:
            logger.error(f"Failed to close project: {e}")
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from CST and release handles."""
        try:
            self.close_project(save=False)
            if self.app is not None:
                try:
                    self.app.close()
                except Exception:
                    pass
            self.app = None
            self.project = None
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
