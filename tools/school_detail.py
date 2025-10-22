"""
tools/school_detail.py
----------------------

Strands tool: Fetch detailed college information by institution ID
from the U.S. College Scorecard API.

Purpose:
  After you use the schools or programs search tool to get a list of schools,
  you can call this one to pull richer data — such as admissions rates,
  tuition, completion rates, and earnings outcomes — for specific IDs.

Typical usage:
  - "Show admissions and cost details for University of Rochester."
  - "Get outcome stats for these 3 schools."
"""

from typing import List, Dict, Any

from pydantic import BaseModel, Field
from strands import tool

# Import common base helpers for key retrieval and API requests
from .scorecard_base import fetch_json, get_key


# ---------------------------------------------------------------------------
# 1. Define field "profiles" (fieldsets)
# ---------------------------------------------------------------------------
# These are predefined subsets of fields from the College Scorecard dataset.
# You can add or remove fields here depending on how much info you want to expose.
PROFILES = {
    # Basic identity and location
    "basic": (
        "id,school.name,school.city,school.state,school.school_url,"
        "location.lat,location.lon"
    ),

    # Admissions info: rates and SAT averages
    "admissions": (
        "latest.admissions.admission_rate.overall,"
        "latest.admissions.sat_scores.average.overall"
    ),

    # Tuition and net price information
    "costs": (
        "latest.cost.tuition.in_state,"
        "latest.cost.tuition.out_of_state,"
        "latest.cost.net_price.public,"
        "latest.cost.net_price.private"
    ),

    # Outcome metrics (graduation + median earnings)
    "outcomes": (
        "latest.completion.rate_suppressed.overall,"
        "latest.earnings.10_yrs_after_entry.median"
    ),
}


# ---------------------------------------------------------------------------
# 2. Define the Pydantic arguments model
# ---------------------------------------------------------------------------
class SchoolDetailArgs(BaseModel):
    """
    Arguments for requesting detailed information about one or more schools.

    Attributes:
        ids (List[int]): One or more institution IDs (from prior search results).
        profiles (List[str]): One or more field group names (basic, admissions, costs, outcomes).
    """
    ids: List[int] = Field(..., description="List of College Scorecard institution IDs.")
    profiles: List[str] = Field(
        ["basic"],
        description=f"List of data profiles to include. Options: {list(PROFILES.keys())}"
    )


# ---------------------------------------------------------------------------
# 3. Define the Strands tool
# ---------------------------------------------------------------------------
@tool(
    name="scorecard.schl.detail",
    description=(
        "Retrieve detailed information for one or more colleges "
        "identified by their Scorecard institution IDs. "
        "Profiles control which field groups are included: basic, admissions, costs, outcomes."
    ),
)
async def school_detail(args: SchoolDetailArgs) -> Dict[str, Any]:
    """
    Fetch details for one or more schools.

    Example input:
        {
          "ids": [194091, 194824],
          "profiles": ["basic", "costs", "outcomes"]
        }
    """

    # -----------------------------------------------------------------------
    # STEP 1: Build the list of fields based on requested profiles
    # -----------------------------------------------------------------------
    # Each profile string (like "basic", "costs") corresponds to a comma-separated list of fields.
    # We combine and deduplicate them so we can ask for multiple profiles at once.
    selected_fields = ",".join({
        f for p in args.profiles
        for f in PROFILES.get(p, "").split(",")
        if f  # ignore blanks
    })

    # -----------------------------------------------------------------------
    # STEP 2: Prepare the query parameters
    # -----------------------------------------------------------------------
    params = {
        "api_key": get_key(),
        "id__in": ",".join(map(str, args.ids)),  # comma-separated list of institution IDs
        "fields": selected_fields,
    }

    # -----------------------------------------------------------------------
    # STEP 3: Make the API request
    # -----------------------------------------------------------------------
    data = await fetch_json(params)

    # -----------------------------------------------------------------------
    # STEP 4: Return the results in a format optimized for agent consumption
    # -----------------------------------------------------------------------
    results = data.get("results", [])
    
    if not results:
        return f"No schools found for IDs: {args.ids}"
    
    # Format the results for better readability by the agent
    formatted_schools = []
    for school in results:
        school_info = []
        
        # Basic info
        if school.get("school.name"):
            school_info.append(f"**{school['school.name']}**")
        if school.get("school.city") and school.get("school.state"):
            school_info.append(f"Location: {school['school.city']}, {school['school.state']}")
        
        # Admissions info
        if school.get("latest.admissions.admission_rate.overall"):
            rate = school["latest.admissions.admission_rate.overall"]
            school_info.append(f"Admission Rate: {rate:.1%}")
        
        # Cost info
        if school.get("latest.cost.tuition.in_state"):
            tuition = school["latest.cost.tuition.in_state"]
            school_info.append(f"In-State Tuition: ${tuition:,}")
        if school.get("latest.cost.tuition.out_of_state"):
            tuition = school["latest.cost.tuition.out_of_state"]
            school_info.append(f"Out-of-State Tuition: ${tuition:,}")
        
        # Outcomes
        if school.get("latest.earnings.10_yrs_after_entry.median"):
            earnings = school["latest.earnings.10_yrs_after_entry.median"]
            school_info.append(f"Median Earnings (10 years): ${earnings:,}")
        
        formatted_schools.append("\n".join(school_info))
    
    return "\n\n".join(formatted_schools)
