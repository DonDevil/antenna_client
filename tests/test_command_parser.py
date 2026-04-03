"""
Test command parsing and validation
"""

import pytest
from executor.command_parser import CommandPackage, Command, CommandParser


def test_command_parsing():
    """Test command parsing"""
    cmd_data = {
        "id": "cmd_1",
        "type": "create_project",
        "parameters": {"name": "Test Project"},
        "on_failure": "abort"
    }
    
    cmd = Command(**cmd_data)
    assert cmd.id == "cmd_1"
    assert cmd.type == "create_project"


def test_command_package_parsing():
    """Test command package parsing"""
    pkg_data = {
        "package_version": "1.0",
        "commands": [
            {
                "id": "cmd_1",
                "type": "create_project",
                "parameters": {"name": "Test"}
            }
        ]
    }
    
    package = CommandPackage(**pkg_data)
    assert package.package_version == "1.0"
    assert len(package.commands) == 1


def test_command_parser():
    """Test CommandParser"""
    parser = CommandParser()
    
    pkg_data = {
        "package_version": "1.0",
        "commands": [
            {
                "id": "cmd_1",
                "type": "create_project",
                "parameters": {"name": "Test"}
            }
        ]
    }
    
    package = parser.parse_package(pkg_data)
    assert package is not None
    
    # Test validation
    assert parser.validate_package(package) == True
