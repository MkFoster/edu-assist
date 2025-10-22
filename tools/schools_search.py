"""
College and University Search Tool
=================================

Strands AI tool for searching colleges and universities using the official
U.S. Department of Education College Scorecard API. This tool provides
comprehensive search functionality with geographic, institutional, and
academic criteria filtering.

Search Capabilities:
- Geographic: Search by state, city/state, or latitude/longitude with radius
- Institutional: Filter by public/private, size, control type
- Academic: Sort by admission rates, costs, graduation rates
- Specialized: Online-only institutions, specific degree levels

Location Modes:
1. State Search: Find all schools in a specific state
2. City Search: Find schools in a specific city and state
3. Proximity Search: Find schools within radius of coordinates

Filters Available:
- School control (public, private non-profit, private for-profit)
- Institution size (minimum and maximum enrollment)
- Online-only institutions
- Sorting options (cost, admission rate, size, etc.)

Data Sources:
- U.S. Department of Education College Scorecard API
- IPEDS (Integrated Postsecondary Education Data System)
- Official institutional data reported to federal government

Usage:
This tool is automatically registered with the Strands agent and can be
called through natural language queries about finding colleges.

Author: Mark Foster
Last Updated: October 2025
"""

from pydantic import BaseModel, Field, conint, confloat, model_validator
from typing import Optional, Literal, List, Dict, Any

# Import shared helpers from the base module
from .scorecard_base import fetch_json, get_key

# Import the Strands @tool decorator
from strands import tool


# ---------------------------------------------------------------------------
# 1. Define groups of fields (profiles) the tool can include in its results
# ---------------------------------------------------------------------------
# The College Scorecard dataset is massive — so we define
# manageable “fieldsets” the agent can request by name.
FIELDSETS = {
    "basic": (
        "id,school.name,school.city,school.state,"
        "location.lat,location.lon,school.school_url"
    ),
    "admissions": (
        "latest.admissions.admission_rate.overall,"
        "latest.admissions.sat_scores.average.overall"
    ),
    "costs": (
        "latest.cost.tuition.in_state,latest.cost.tuition.out_of_state,"
        "latest.cost.net_price.public,latest.cost.net_price.private"
    ),
    "outcomes": (
        "latest.completion.rate_suppressed.overall,"
        "latest.earnings.10_yrs_after_entry.median"
    ),
}

# Default to “basic” fields (id, name, city, state, coords, url)
DEFAULT_FIELDS = FIELDSETS["basic"]


# ---------------------------------------------------------------------------
# 2. Define the Pydantic argument model for this tool
# ---------------------------------------------------------------------------
class SchoolsSearchArgs(BaseModel):
    """
    Defines what arguments this Strands tool accepts.

    Each property corresponds to a filter or option for the API query.
    """

    # --- LOCATION MODES ---
    state: Optional[str] = Field(None, description="Two-letter state code, e.g. 'NY'.")
    city: Optional[str] = Field(None, description="City name, e.g. 'Rochester'.")
    latitude: Optional[confloat(ge=-90, le=90)] = Field(None, description="Latitude coordinate.")
    longitude: Optional[confloat(ge=-180, le=180)] = Field(None, description="Longitude coordinate.")
    distance_mi: conint(ge=1, le=500) = Field(
        25, description="Search radius in miles (for lat/lon mode)."
    )

    # --- ADDITIONAL FILTERS ---
    control: Optional[Literal["public", "private", "for-profit"]] = Field(
        None, description="Type of institution."
    )
    min_size: Optional[int] = Field(None, description="Minimum student enrollment.")
    max_size: Optional[int] = Field(None, description="Maximum student enrollment.")
    online_only: Optional[bool] = Field(
        None, description="True = only show fully online institutions."
    )

    # --- SORTING / PAGINATION ---
    sort_by: Optional[
        Literal[
            "latest.admissions.admission_rate.overall",
            "latest.cost.net_price.public",
            "latest.cost.net_price.private",
            "latest.completion.rate_suppressed.overall",
        ]
    ] = Field(None, description="Field to sort by.")
    sort_order: Literal["asc", "desc"] = Field("asc", description="Sort order (ascending/descending).")
    page: conint(ge=0) = Field(0, description="Page number (0-indexed).")
    per_page: conint(ge=1, le=100) = Field(10, description="Max results to return per page.")

    # --- FIELD PROFILES ---
    profiles: List[Literal["basic", "admissions", "costs", "outcomes"]] = Field(
        ["basic"],
        description=(
            "List of field profiles to include in results. "
            "Combine multiple for richer data (e.g. ['basic','costs'])."
        ),
    )

    # --- VALIDATION: Must choose exactly ONE location mode ---
    @model_validator(mode='before')
    @classmethod
    def _validate_location_mode(cls, values):
        """
        Ensures the user provided exactly one location mode.
        """
        lat, lon, city, state = (
            values.get("latitude"),
            values.get("longitude"),
            values.get("city"),
            values.get("state"),
        )

        has_latlon = lat is not None or lon is not None
        has_citystate = bool(city and state)
        has_state_only = state is not None and city is None and not has_latlon

        modes = [has_latlon, has_citystate, has_state_only]
        if sum(modes) != 1:
            raise ValueError(
                "Specify exactly one location mode: "
                "(1) state, (2) city+state, or (3) lat+lon."
            )
        if has_latlon and (lat is None or lon is None):
            raise ValueError("Both latitude and longitude are required for lat/lon search.")
        return values


# ---------------------------------------------------------------------------
# 3. Define the actual Strands tool
# ---------------------------------------------------------------------------
@tool(
    name="scorecard.schl.search",
    description=(
        "Search for institutions using the U.S. College Scorecard API. "
        "Supports filters by state, city/state, or coordinates, with "
        "optional filters for control, size, and online-only."
    ),
)
async def schools_search(args: SchoolsSearchArgs) -> Dict[str, Any]:
    """
    Executes a search for colleges using the Scorecard API
    and returns a structured dictionary with summary cards.

    Returns:
        {
          "cards": [ {id, name, city, state, url}, ... ],
          "metadata": {...},   # pagination data
          "raw": {...}         # full API JSON (optional for advanced use)
        }
    """

    # -----------------------------------------------------------------------
    # STEP 1: Build query parameters for the API
    # -----------------------------------------------------------------------
    params: Dict[str, Any] = {
        "api_key": get_key(),
        "_per_page": args.per_page,
        "page": args.page,
        # Join all requested profiles into a single comma-separated field list
        "fields": ",".join(
            {f for p in args.profiles for f in FIELDSETS[p].split(",")}
        ),
    }

    # -----------------------------------------------------------------------
    # STEP 2: Location filters (mutually exclusive)
    # -----------------------------------------------------------------------
    if args.latitude is not None and args.longitude is not None:
        # Geographic search using coordinates and distance
        params["latitude"] = args.latitude
        params["longitude"] = args.longitude
        params["distance"] = f"{args.distance_mi}mi"
    elif args.city and args.state:
        # City + state exact match
        params["school.city"] = args.city
        params["school.state"] = args.state.upper()
    else:
        # State-only search
        params["school.state"] = args.state.upper()

    # -----------------------------------------------------------------------
    # STEP 3: Optional filters (control, size, online_only)
    # -----------------------------------------------------------------------
    if args.control:
        # Map human-friendly values to API numeric codes
        #   1 = Public, 2 = Private nonprofit, 3 = Private for-profit
        control_map = {"public": 1, "private": 2, "for-profit": 3}
        params["school.control"] = control_map[args.control]

    if args.min_size or args.max_size:
        # API supports a “range” syntax like 0..10000
        lo = args.min_size or 0
        hi = args.max_size or 999999
        params["latest.student.size__range"] = f"{lo}..{hi}"

    if args.online_only is not None:
        # True/False must be sent as integer 1/0
        params["school.online_only"] = int(args.online_only)

    # -----------------------------------------------------------------------
    # STEP 4: Sorting
    # -----------------------------------------------------------------------
    if args.sort_by:
        # Append “:desc” if needed; default is ascending.
        order = "" if args.sort_order == "asc" else "desc"
        params["sort"] = f"{args.sort_by}:{order}" if order else args.sort_by

    # -----------------------------------------------------------------------
    # STEP 5: Make the API request
    # -----------------------------------------------------------------------
    data = await fetch_json(params)

    # -----------------------------------------------------------------------
    # STEP 6: Transform the raw API results into lightweight “cards”
    # -----------------------------------------------------------------------
    results = data.get("results", [])
    
    if not results:
        return "No schools found matching your criteria. Try broadening your search parameters."
    
    # Create lightweight cards for display
    cards = []
    formatted_schools = []
    
    for r in results:
        # Create simplified card data
        card = {
            "id": r.get("id"),
            "name": r.get("school.name"),
            "city": r.get("school.city"),
            "state": r.get("school.state"),
            "url": r.get("school.school_url"),
        }
        cards.append(card)
        
        # Format for human reading
        school_info = []
        if card["name"]:
            school_info.append(f"**{card['name']}** (ID: {card['id']})")
        if card["city"] and card["state"]:
            school_info.append(f"📍 {card['city']}, {card['state']}")
        if card["url"]:
            school_info.append(f"🌐 {card['url']}")
        
        formatted_schools.append("\n".join(school_info))
    
    # Create summary text
    metadata = data.get("metadata", {})
    total_results = metadata.get("total", len(results))
    current_page = metadata.get("page", args.page)
    
    summary_lines = [
        f"Found {total_results} schools matching your criteria.",
        f"Showing page {current_page + 1}, {len(results)} results:",
        "",
        "\n\n".join(formatted_schools)
    ]
    
    if len(results) < total_results:
        summary_lines.append(f"\n💡 Use page={current_page + 1} to see more results.")
    
    return "\n".join(summary_lines)
