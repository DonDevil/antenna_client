"""Parse and validate cst_command_package payloads from the server."""

from __future__ import annotations

from typing import Dict, List, Any, Optional

from pydantic import BaseModel, ValidationError, ConfigDict, model_validator

from executor.v2_command_contract import V2CommandContractValidator
from utils.logger import get_logger


logger = get_logger(__name__)


class Command(BaseModel):
    """Individual command in the server command package."""

    model_config = ConfigDict(extra="allow")

    seq: int
    command: str
    params: Dict[str, Any]
    on_failure: str = "abort"
    checksum_scope: str = "command"

    @model_validator(mode="before")
    @classmethod
    def normalize_aliases(cls, data: Any) -> Any:
        """Accept both v1 and legacy alias field names."""
        if not isinstance(data, dict):
            return data
        normalized = dict(data)
        if "command" not in normalized and "type" in normalized:
            normalized["command"] = normalized["type"]
        if "params" not in normalized and "parameters" in normalized:
            normalized["params"] = normalized["parameters"]
        return normalized


class CommandPackage(BaseModel):
    """Current server command package schema."""

    model_config = ConfigDict(extra="allow")

    schema_version: str
    command_catalog_version: str
    session_id: str
    trace_id: str
    design_id: str
    iteration_index: int
    units: Dict[str, Any]
    predicted_dimensions: Dict[str, Any]
    predicted_metrics: Optional[Dict[str, Any]] = None
    commands: List[Command]
    expected_exports: List[str]
    safety_checks: List[str]


class CommandParser:
    """Parse and validate command packages"""

    SUPPORTED_SCHEMA_VERSIONS = (
        "cst_command_package.v1",
        "cst_command_package.v2",
    )

    def __init__(self) -> None:
        self._v2_contract_validator = V2CommandContractValidator()
    
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
            logger.info(
                f"Parsed command package {package.schema_version} "
                f"with {len(package.commands)} commands"
            )
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
        if package.schema_version not in self.SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(
                f"Unsupported package version: {package.schema_version} "
                f"(supported: {', '.join(self.SUPPORTED_SCHEMA_VERSIONS)})"
            )
        
        # Check commands are not empty
        if not package.commands:
            raise ValueError("Package contains no commands")
        
        # Validate each command
        previous_seq = 0
        for cmd in package.commands:
            if cmd.seq <= previous_seq:
                raise ValueError("Command sequence must be strictly increasing")
            previous_seq = cmd.seq
            if not cmd.command:
                raise ValueError(f"Command {cmd.seq} missing command name")
            if not isinstance(cmd.params, dict):
                raise ValueError(f"Command {cmd.seq} has invalid params payload")

        if package.schema_version == "cst_command_package.v2":
            self._v2_contract_validator.validate_package(package.model_dump())
        
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
            if f"{cmd.seq}:{cmd.command}" == command_id:
                return cmd
        
        raise ValueError(f"Command {command_id} not found in package")
    
    def get_execution_order(self, package: CommandPackage) -> List[Command]:
        """Get commands in execution order
        
        Args:
            package: CommandPackage
            
        Returns:
            List of commands in order
        """
        return sorted(package.commands, key=lambda cmd: cmd.seq)


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
