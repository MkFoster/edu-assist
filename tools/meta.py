"""
Metadata and Reference Information Tool
======================================

Strands AI tool providing metadata, mappings, and reference information
for the College Scorecard API and educational data systems. This tool
helps the AI agent understand data structures and provide better assistance.

Purpose:
- Expose available data field profiles and query options
- Provide CIP (Classification of Instructional Programs) code lookups
- Share enumeration mappings for institution types and award levels
- Help the agent construct more accurate and comprehensive queries
- Serve as a reference guide for educational data structures

Metadata Categories:

1. Field Profiles:
   - Basic institutional information
   - Admissions and enrollment data
   - Cost and financial aid information
   - Academic outcomes and employment data

2. CIP Code Classifications:
   - Standard educational program classifications
   - Hierarchical program groupings
   - Common program name mappings

3. Institution Classifications:
   - Public, private non-profit, private for-profit
   - Control type mappings and descriptions
   - Institutional size categories

4. Award Level Mappings:
   - Certificate through doctoral degree levels
   - Numeric codes to descriptive names
   - Educational attainment hierarchies

Usage:
This tool provides reference information that helps the agent:
- Construct better search queries
- Understand data field meanings
- Provide accurate explanations to users
- Validate input parameters

Integration:
Automatically available to the Strands agent for internal reference
and can be called when users ask about data definitions or categories.

Author: Mark Foster
Last Updated: October 2025
"""

import json
from typing import Dict, Any, List
from pydantic import BaseModel, Field
from strands import tool

# We'll re-import the PROFILES dictionary and AWARD_LEVELS_MAP from the other tool files.
# Since we're all in the same tools package, we use relative imports
from .school_detail import PROFILES              # field profiles
from .programs_search import AWARD_LEVELS_MAP, CONTROL_MAP  # mappings for awards and institution types


# ---------------------------------------------------------------------------
# 1. Optional: simple CIP code list for autocomplete
# ---------------------------------------------------------------------------
# You can expand this with a proper taxonomy, or load from a JSON file.
# For demonstration, we include a few common examples.

CIP_EXAMPLES = [
    {"cip": "11.0101", "title": "Computer Science"},
    {"cip": "14.0101", "title": "Engineering, General"},
    {"cip": "52.0201", "title": "Business Administration and Management, General"},
    {"cip": "51.3801", "title": "Registered Nursing/Registered Nurse"},
    {"cip": "26.0101", "title": "Biology/Biological Sciences, General"},
    {"cip": "40.0501", "title": "Chemistry, General"},
    {"cip": "23.0101", "title": "English Language and Literature, General"},
    {"cip": "24.0102", "title": "General Studies"},
]


# ---------------------------------------------------------------------------
# Input models for tools
# ---------------------------------------------------------------------------
class CIPAutocompleteArgs(BaseModel):
    """Arguments for CIP code autocomplete."""
    query: str = Field(..., description="Keyword to search for in program titles")


# ---------------------------------------------------------------------------
# 2. Tool 1: Return field profiles
# ---------------------------------------------------------------------------
@tool(
    name="scorecard.meta.fields",
    description="List available field profiles (basic, admissions, costs, outcomes) and the fields they include.",
)
async def meta_fields() -> Dict[str, Any]:
    """
    Returns the field profiles (used by the other tools) so that
    your agent or UI can dynamically see what's available.

    Example:
        await meta_fields({})
    Output:
        {
          "profiles": {
             "basic": ["id","school.name","school.city",...],
             "admissions": [...],
             ...
          }
        }
    """
    # Split each comma-separated string into a Python list
    profile_dict = {
        name: fields.split(",")
        for name, fields in PROFILES.items()
    }

    # Format for human display
    formatted_profiles = []
    for name, fields in profile_dict.items():
        formatted_profiles.append(f"**{name}**: {len(fields)} fields")
        formatted_profiles.append(f"  Fields: {', '.join(fields[:5])}{'...' if len(fields) > 5 else ''}")
        formatted_profiles.append("")

    return f"Available field profiles:\n\n" + "\n".join(formatted_profiles)


# ---------------------------------------------------------------------------
# 3. Tool 2: CIP code autocomplete
# ---------------------------------------------------------------------------
@tool(
    name="scorecard.meta.cip_autocomplete",
    description=(
        "Suggest CIP (Classification of Instructional Programs) codes "
        "based on a keyword search in the program title."
    ),
)
async def cip_autocomplete(args: CIPAutocompleteArgs) -> Dict[str, Any]:
    """
    Simple keyword-based CIP search.

    Args:
        args: CIPAutocompleteArgs with query field

    Returns:
        {
          "matches": [
            {"cip": "11.0101", "title": "Computer Science"},
            {"cip": "11.0802", "title": "Data Modeling/Warehousing and Database Administration"},
            ...
          ]
        }

    In production, you can replace CIP_EXAMPLES with a full JSON dataset
    from the NCES CIP taxonomy (public domain).
    """

    query = args.query.strip().lower()
    if not query:
        return "Please provide a search term to look up CIP codes."

    # Simple substring match
    matches = [
        cip for cip in CIP_EXAMPLES
        if query in cip["title"].lower()
    ]

    if not matches:
        return f"No CIP codes found matching '{query}'. Try a broader search term."

    # Format matches for display
    formatted_matches = []
    formatted_matches.append(f"Found {len(matches)} CIP code(s) matching '{query}':")
    formatted_matches.append("")
    
    for match in matches:
        formatted_matches.append(f"• **{match['cip']}**: {match['title']}")

    return "\n".join(formatted_matches)


# ---------------------------------------------------------------------------
# 4. Tool 3: Enumerations (control types, award levels, etc.)
# ---------------------------------------------------------------------------
@tool(
    name="scorecard.meta.enums",
    description="List known enumerations for school control types and award levels.",
)
async def meta_enums() -> Dict[str, Any]:
    """
    Returns useful enumerations that the agent can reference
    when constructing or validating user requests.
    """
    # Reverse-map award levels for readability
    awards_readable: Dict[str, List[int]] = {
        k: v for k, v in AWARD_LEVELS_MAP.items()
    }

    controls_readable: Dict[str, int] = {
        k: v for k, v in CONTROL_MAP.items()
    }

    # Format for human display
    formatted_text = []
    formatted_text.append("**Institution Control Types:**")
    for name, code in controls_readable.items():
        formatted_text.append(f"• {name}: {code}")
    
    formatted_text.append("\n**Award Levels:**")
    for name, codes in awards_readable.items():
        formatted_text.append(f"• {name}: {codes}")

    return "\n".join(formatted_text)
