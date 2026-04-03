"""
Test VBA generation
"""

import pytest
from executor.vba_generator import VBAGenerator


def test_vba_generation_create_project():
    """Test VBA macro generation for create_project"""
    gen = VBAGenerator()
    
    macro = gen.generate_macro("create_project", {"name": "MyProject"})
    assert macro is not None
    assert "MyProject" in macro


def test_vba_generation_set_units():
    """Test VBA macro generation for set_units"""
    gen = VBAGenerator()
    
    macro = gen.generate_macro("set_units", {"units": "mm"})
    assert macro is not None
    assert "mm" in macro


def test_vba_generation_package():
    """Test complete VBA script generation"""
    gen = VBAGenerator()
    
    macros = [
        gen.generate_macro("create_project", {"name": "Test"}),
        gen.generate_macro("set_units", {"units": "mm"})
    ]
    
    script = gen.generate_package_script(macros)
    assert script is not None
    assert "Option Explicit" in script
    assert "ErrorHandler" in script
