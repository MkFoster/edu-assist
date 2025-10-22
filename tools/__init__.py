"""
tools/__init__.py
Auto-discovers and imports every tool module in this package.

Why? Strands tools register themselves via the @tool decorator at import time.
So importing all modules here ensures everything is registered without manually
listing them in app.py.
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
