"""
VBAExecutor - VBA macro injection and execution in CST

Responsible for:
- Inject VBA macro into CST
- Execute macro via add_to_history
- Parse return values
- Handle VBA runtime errors
"""

from typing import Optional, Any
from utils.logger import get_logger


logger = get_logger(__name__)


class VBAExecutor:
    """Execute VBA macros in CST Studio"""
    
    def __init__(self, cst_app):
        """Initialize VBA executor
        
        Args:
            cst_app: CSTApp instance with active connection
        """
        self.cst_app = cst_app
        logger.info("VBAExecutor initialized")
    
    def execute_macro(self, macro_code: str) -> bool:
        """Execute VBA macro in CST
        
        Args:
            macro_code: VBA code to execute
            
        Returns:
            True if successful, False otherwise
        """
        if not self.cst_app.is_connected() or self.cst_app.mws is None:
            logger.error("CST not connected")
            return False
        
        try:
            self.cst_app.mws.add_to_history("VBA Code", macro_code)
            self.cst_app.mws.full_history_rebuild()
            logger.info("VBA macro executed successfully")
            return True
        except Exception as e:
            logger.error(f"VBA execution failed: {e}")
            return False
    
    def execute_vb_statement(self, statement: str) -> Any:
        """Execute single VB statement
        
        Args:
            statement: VB statement to execute
            
        Returns:
            Result of statement or None
        """
        if not self.cst_app.is_connected() or self.cst_app.mws is None:
            logger.error("CST not connected")
            return None
        
        try:
            result = self.mws.EvaluateExpression(statement)
            logger.debug(f"VB statement executed: {statement}")
            return result
        except Exception as e:
            logger.error(f"VB statement failed: {e}")
            return None
    
    def define_material(self, name: str, epsilon_r: float, loss_tangent: float = 0.0) -> bool:
        """Define material in CST
        
        Args:
            name: Material name
            epsilon_r: Relative permittivity
            loss_tangent: Loss tangent (default 0 for lossless)
            
        Returns:
            True if successful
        """
        vba_code = f"""
        With Material
            .Reset
            .Name "{name}"
            .Folder ""
            .Epsilon {epsilon_r}
            .TangentD {loss_tangent}
            .Create
        End With
        """
        return self.execute_macro(vba_code)
    
    def create_rectangle(self, name: str, x_min: float, x_max: float,
                        y_min: float, y_max: float, z_min: float, z_max: float,
                        material: str = "PEC") -> bool:
        """Create rectangular solid in CST
        
        Args:
            name: Shape name
            x_min, x_max, y_min, y_max, z_min, z_max: Bounding box coordinates
            material: Material name (default PEC = Perfect Electric Conductor)
            
        Returns:
            True if successful
        """
        vba_code = f"""
        With Brick
            .Reset
            .Name "{name}"
            .Component "component1"
            .Material "{material}"
            .Xmin {x_min}
            .Xmax {x_max}
            .Ymin {y_min}
            .Ymax {y_max}
            .Zmin {z_min}
            .Zmax {z_max}
            .Create
        End With
        """
        return self.execute_macro(vba_code)
    
    def run_solver(self) -> bool:
        """Run CST transient solver
        
        Returns:
            True if successful
        """
        vba_code = """
        With Solver
            .Start
        End With
        """
        return self.execute_macro(vba_code)
