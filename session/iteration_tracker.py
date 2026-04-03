"""
IterationTracker - Track design iterations and convergence

Responsible for:
- Track iteration metadata
- Detect convergence
- Compare iterations
"""

from typing import Dict, List, Any, Optional
from utils.logger import get_logger


logger = get_logger(__name__)


class IterationTracker:
    """Track and manage design iterations"""
    
    def __init__(self):
        """Initialize iteration tracker"""
        self.iterations: List[Dict[str, Any]] = []
        logger.info("IterationTracker initialized")
    
    def add_iteration(self, session_id: str, iteration_num: int,
                     design_params: Dict, results: Dict) -> None:
        """Record iteration
        
        Args:
            session_id: Session ID
            iteration_num: Iteration number
            design_params: Design parameters
            results: Measurement results
        """
        iteration = {
            "session_id": session_id,
            "iteration": iteration_num,
            "design_params": design_params,
            "results": results,
        }
        self.iterations.append(iteration)
        logger.info(f"Recorded iteration {iteration_num} for session {session_id}")
    
    def detect_convergence(self, session_id: str, threshold: float = 0.01) -> bool:
        """Detect if design has converged
        
        Args:
            session_id: Session ID
            threshold: Convergence threshold (default 1%)
            
        Returns:
            True if converged
        """
        session_iters = [i for i in self.iterations if i["session_id"] == session_id]
        
        if len(session_iters) < 2:
            return False
        
        # Compare last two iterations
        last = session_iters[-1]["results"]
        prev = session_iters[-2]["results"]
        
        # Check if metrics changed less than threshold
        if "center_frequency_ghz" in last and "center_frequency_ghz" in prev:
            freq_change = abs(last["center_frequency_ghz"] - prev["center_frequency_ghz"])
            if freq_change < threshold:
                logger.info("Design converged")
                return True
        
        return False
    
    def compare_iterations(self, session_id: str, iter1: int, iter2: int) -> Dict:
        """Compare two iterations
        
        Args:
            session_id: Session ID
            iter1: First iteration number
            iter2: Second iteration number
            
        Returns:
            Comparison dict
        """
        iters = {i["iteration"]: i for i in self.iterations if i["session_id"] == session_id}
        
        comparison = {
            "iter1": iter1,
            "iter2": iter2,
            "differences": {},
        }
        
        if iter1 in iters and iter2 in iters:
            results1 = iters[iter1]["results"]
            results2 = iters[iter2]["results"]
            
            for key in results1:
                if key in results2:
                    comp_val = {
                        "value1": results1[key],
                        "value2": results2[key],
                        "change": results2[key] - results1[key],
                    }
                    comparison["differences"][key] = comp_val
        
        return comparison
    
    def get_iteration_history(self, session_id: str) -> List[Dict]:
        """Get iteration history
        
        Args:
            session_id: Session ID
            
        Returns:
            List of iterations
        """
        return [i for i in self.iterations if i["session_id"] == session_id]
