"""
College Search Tools Package
===========================

Auto-discovery and registration system for Strands AI agent tools.

This module automatically discovers and imports all tool modules in the package,
ensuring that @tool decorated functions are registered with the Strands framework
without requiring manual imports in the main application.

Architecture:
- Automatic module discovery using pkgutil.iter_modules()
- Dynamic imports using importlib.import_module()
- Exclusion system for utility modules and configuration files
- Registration happens at import time via @tool decorators

Tools Included:
- schools_search: Search for colleges and universities by various criteria
- programs_search: Find academic programs and degrees
- school_detail: Get detailed information about specific institutions
- college_jokes: Provide lighthearted college-related humor
- meta: Metadata mappings and utility functions

Excluded Modules:
- scorecard_base: Base utility class (not a tool)
- __init__.py: This initialization module
- __pycache__: Python cache directory

Usage:
    # Import this package to auto-register all tools
    from tools import *
    
    # Or import specific modules if needed
    from tools import schools_search, programs_search

Author: Mark Foster
Last Updated: October 2025
"""

from importlib import import_module  # Dynamically import modules by name
from pkgutil import iter_modules  # Iterate over modules in a package directory
from pathlib import Path  # Object-oriented filesystem path handling

# Locate this package directory
_pkg_dir = Path(__file__).parent

# You can exclude files here if needed
_EXCLUDE = {
    "__init__.py",
    "__pycache__",
    "scorecard_base.py",  # Utility module, not a tool
}

def _is_tool_module(name: str) -> bool:
    # Skip dunder and private file names; Keep anything else.
    return not (name.startswith("_") or name in _EXCLUDE)

def autodiscover_tools() -> None:
    """
    Import all modules in this package to trigger @tool registration.
    """
    for mod_info in iter_modules([str(_pkg_dir)]):
        mod_name = mod_info.name  # e.g., "schools_search"
        if _is_tool_module(mod_name):
            import_module(f"{__name__}.{mod_name}")

# Run discovery on package import
autodiscover_tools()
