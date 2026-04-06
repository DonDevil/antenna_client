"""
DesignStore - Design specifications storage and retrieval

Responsible for:
- Store design specifications by unique ID
- Retrieve designs by ID
- List all designs
- Update design status
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from utils.logger import get_logger


logger = get_logger(__name__)


class Design:
    """Represents a single design"""
    
    def __init__(self, design_id: str, specifications: Dict[str, Any]):
        """Initialize design
        
        Args:
            design_id: Unique design identifier
            specifications: Design specifications dict
        """
        self.design_id = design_id
        self.specifications = specifications
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.status = "draft"  # draft, active, completed, archived
        self.iterations = []
        self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "design_id": self.design_id,
            "specifications": self.specifications,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "iterations": self.iterations,
            "metadata": self.metadata
        }


class DesignStore:
    """Store for managing designs"""
    
    def __init__(self):
        """Initialize design store"""
        self.designs: Dict[str, Design] = {}
        logger.info("DesignStore initialized")
    
    def create_design(self, design_id: str, specifications: Dict[str, Any]) -> Design:
        """Create new design
        
        Args:
            design_id: Unique design identifier
            specifications: Design specifications
            
        Returns:
            Created Design object
        """
        if design_id in self.designs:
            logger.warning(f"Design {design_id} already exists, overwriting")
        
        design = Design(design_id, specifications)
        self.designs[design_id] = design
        logger.info(f"Created design: {design_id}")
        return design
    
    def get_design(self, design_id: str) -> Optional[Design]:
        """Get design by ID
        
        Args:
            design_id: Design identifier
            
        Returns:
            Design object or None if not found
        """
        return self.designs.get(design_id)
    
    def update_design(self, design_id: str, updates: Dict[str, Any]) -> bool:
        """Update design
        
        Args:
            design_id: Design identifier
            updates: Dictionary of updates
            
        Returns:
            True if updated, False if not found
        """
        design = self.designs.get(design_id)
        if not design:
            return False
        
        if "specifications" in updates:
            design.specifications.update(updates["specifications"])
        if "status" in updates:
            design.status = updates["status"]
        if "metadata" in updates:
            design.metadata.update(updates["metadata"])
        
        design.updated_at = datetime.now().isoformat()
        logger.debug(f"Updated design: {design_id}")
        return True
    
    def add_iteration(self, design_id: str, iteration_data: Dict[str, Any]) -> bool:
        """Add iteration to design
        
        Args:
            design_id: Design identifier
            iteration_data: Iteration data
            
        Returns:
            True if added, False if design not found
        """
        design = self.designs.get(design_id)
        if not design:
            return False
        
        design.iterations.append(iteration_data)
        return True
    
    def list_designs(self, status: str = None) -> List[Dict[str, Any]]:
        """List all designs, optionally filtered by status
        
        Args:
            status: Optional status filter
            
        Returns:
            List of design dictionaries
        """
        designs = self.designs.values()
        if status:
            designs = [d for d in designs if d.status == status]
        return [d.to_dict() for d in designs]
    
    def delete_design(self, design_id: str) -> bool:
        """Delete design
        
        Args:
            design_id: Design identifier
            
        Returns:
            True if deleted, False if not found
        """
        if design_id in self.designs:
            del self.designs[design_id]
            logger.info(f"Deleted design: {design_id}")
            return True
        return False
