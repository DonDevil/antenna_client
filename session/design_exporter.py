"""
DesignExporter - Export designs to JSON/CSV formats

Responsible for:
- Export design to JSON
- Export design to CSV
- Export iteration history
"""

import json
import csv
from typing import Dict, Any, List
from datetime import datetime
from utils.logger import get_logger


logger = get_logger(__name__)


class DesignExporter:
    """Export designs in various formats"""
    
    def export_to_json(self, design_dict: Dict[str, Any], filepath: str) -> bool:
        """Export design to JSON file
        
        Args:
            design_dict: Design dictionary
            filepath: Output file path
            
        Returns:
            True if successful
        """
        try:
            with open(filepath, 'w') as f:
                json.dump(design_dict, f, indent=2)
            logger.info(f"Exported design to JSON: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to export to JSON: {e}")
            return False
    
    def export_to_csv(self, designs: List[Dict[str, Any]], filepath: str) -> bool:
        """Export designs to CSV file
        
        Args:
            designs: List of design dictionaries
            filepath: Output file path
            
        Returns:
            True if successful
        """
        try:
            if not designs:
                return False
            
            with open(filepath, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=designs[0].keys())
                writer.writeheader()
                writer.writerows(designs)
            
            logger.info(f"Exported designs to CSV: {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to export to CSV: {e}")
            return False
