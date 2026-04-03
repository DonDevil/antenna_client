"""
CommandParser - Parse and validate command packages from server

Responsible for:
- Validate command package structure
- Extract individual commands
- Validate command parameters
- Handle versioning
"""

from typing import Dict, List, Any
from pydantic import BaseModel, ValidationError
from utils.logger import get_logger


logger = get_logger(__name__)


class Command(BaseModel):
    """Individual command in package"""
    id: str
    type: str  # e.g., "create_project", "set_units", "create_patch"
    parameters: Dict[str, Any]
    on_failure: str = "abort"  # abort, skip, retry


class CommandPackage(BaseModel):
    """Command package from server"""
    package_version: str
    commands: List[Command]
    policy: Dict[str, Any] = {}  # execution policy


class CommandParser:
    """Parse and validate command packages"""
    
    SUPPORTED_VERSION = "1.0"
    
    def parse_package(self, package_data: Dict[str, Any]) -> CommandPackage:
        """Parse command package
        
        Args:
            package_data: Raw package dict from server
            
        Returns:
            Validated CommandPackage
            
        Raises:
            ValidationError: If package doesn't match schema
        """
        try:
            package = CommandPackage(**package_data)
            logger.info(f"Parsed command package v{package.package_version} with {len(package.commands)} commands")
            return package
        except ValidationError as e:
            logger.error(f"Command package validation failed: {e}")
            raise
    
    def validate_package(self, package: CommandPackage) -> bool:
        """Validate package structure and content
        
        Args:
            package: CommandPackage to validate
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If package is invalid
        """
        # Check version compatibility
        if package.package_version != self.SUPPORTED_VERSION:
            raise ValueError(
                f"Unsupported package version: {package.package_version} "
                f"(supported: {self.SUPPORTED_VERSION})"
            )
        
        # Check commands are not empty
        if not package.commands:
            raise ValueError("Package contains no commands")
        
        # Validate each command
        for cmd in package.commands:
            if not cmd.id:
                raise ValueError("Command missing ID")
            if not cmd.type:
                raise ValueError(f"Command {cmd.id} missing type")
            if not cmd.parameters:
                raise ValueError(f"Command {cmd.id} missing parameters")
        
        logger.info(f"Package validation successful: {len(package.commands)} commands valid")
        return True
    
    def extract_command(self, package: CommandPackage, command_id: str) -> Command:
        """Extract specific command from package
        
        Args:
            package: CommandPackage
            command_id: Command ID to extract
            
        Returns:
            Command object
            
        Raises:
            ValueError: If command not found
        """
        for cmd in package.commands:
            if cmd.id == command_id:
                return cmd
        
        raise ValueError(f"Command {command_id} not found in package")
    
    def get_execution_order(self, package: CommandPackage) -> List[Command]:
        """Get commands in execution order
        
        Args:
            package: CommandPackage
            
        Returns:
            List of commands in order
        """
        return package.commands  # Already in order from server


class CommandValidator:
    """Validate command parameters"""
    
    def validate_frequency(self, freq_ghz: float) -> bool:
        """Validate frequency parameter
        
        Args:
            freq_ghz: Frequency in GHz
            
        Returns:
            True if valid
        """
        return 0.1 <= freq_ghz <= 300
    
    def validate_bandwidth(self, bw_mhz: float) -> bool:
        """Validate bandwidth parameter
        
        Args:
            bw_mhz: Bandwidth in MHz
            
        Returns:
            True if valid
        """
        return 1 <= bw_mhz <= 10000
    
    def validate_dimension(self, dimension_mm: float) -> bool:
        """Validate physical dimension
        
        Args:
            dimension_mm: Dimension in millimeters
            
        Returns:
            True if valid
        """
        return 0.1 <= dimension_mm <= 10000
