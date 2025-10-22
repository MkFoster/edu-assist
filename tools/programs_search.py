"""
tools/programs_search.py
------------------------

Strands tool to search for colleges **by degree program** using the U.S.
College Scorecard API (Field-of-Study data embedded under institutions).

Use cases:
  • "Find schools that offer Computer Science in NY."
  • "Show colleges with CIP 11.0101 (Computer Science), bachelor's level."
  • "List programs with 'nursing' in the name within 50 miles (combine with a schools search)."

This tool:
  - Lets you filter by CIP code prefix or program title keyword.
  - Lets you constrain to specific award levels (associate/bachelor/etc.).
  - Optionally filter by institution 'control' (public/private/for-profit) and state.
  - Returns each **institution** with an array of the **matching program entries**.
"""

from typing import Optional, List, Dict, Any, Literal

from pydantic import BaseModel, Field, conint, field_validator, model_validator
from strands import tool

# Shared base helpers (API key retrieval + async GET)
from .scorecard_base import fetch_json, get_key


# ---------------------------------------------------------------------------
# 1) Field selection
# ---------------------------------------------------------------------------
# The Scorecard API nests program (FOS) values under `latest.programs.cip_6_digit.*`.
# We keep the field list tight for performance; expand as needed.
FOS_FIELDS = ",".join([
    "id",
    "school.name",
    "school.city",
    "school.state",
    # Program (6-digit CIP granularity)
    "latest.programs.cip_6_digit.code",
    "latest.programs.cip_6_digit.title",
    "latest.programs.cip_6_digit.credential",            # award level
    "latest.programs.cip_6_digit.earnings.highest_quartile",
    "latest.programs.cip_6_digit.debt.median",
    # Add more fields here if you want (counts, enrollment, etc.)
])


# ---------------------------------------------------------------------------
# 2) Award level mapping helper (human-friendly → API integers)
# ---------------------------------------------------------------------------
# College Scorecard encodes credentials as integers. A common simplified mapping is:
#   1 = Certificate (< 1 year)
#   2 = Associate
#   3 = Bachelor's
#   4 = Post-bacc certificate
#   5 = Master's
#   6 = Doctoral
# (Some datasets include more granular cert levels; adjust as needed.)
AWARD_LEVELS_MAP = {
    "certificate": [1],   # you can widen to [1,4] if you want all certificates
    "associate": [2],
    "bachelor": [3],
    "masters": [5],
    "master": [5],
    "doctoral": [6],
    "doctorate": [6],
}

CONTROL_MAP = {"public": 1, "private": 2, "for-profit": 3}


# ---------------------------------------------------------------------------
# 3) Tool argument schema
# ---------------------------------------------------------------------------
class ProgramsSearchArgs(BaseModel):
    """
    Arguments accepted by the programs search tool.

    You must specify **at least one** of:
      • cip_prefix (2/4/6-digit CIP code like '11', '11.01', '11.0101')
      • program_text (keyword contained in program title)
    """
    # --- Primary program filters (choose one or both) ---
    cip_prefix: Optional[str] = Field(
        None, description="CIP code prefix at 2-, 4-, or 6-digit granularity (e.g. '11', '11.01', '11.0101')."
    )
    program_text: Optional[str] = Field(
        None, description="Case-insensitive substring match on program title (best-effort)."
    )

    # --- Institution constraints (optional) ---
    state: Optional[str] = Field(None, description="Two-letter state filter (e.g. 'NY').")
    control: Optional[Literal["public", "private", "for-profit"]] = Field(
        None, description="Institution control type."
    )

    # --- Award levels (optional) ---
    # You can pass either explicit numeric codes or friendly strings.
    award_levels: Optional[List[int]] = Field(
        None, description="List of numeric award level codes (e.g., [2,3] for associate + bachelor)."
    )
    award_levels_named: Optional[List[str]] = Field(
        None, description="List of names (e.g., ['associate','bachelor']). Mapped to numeric codes."
    )

    # --- Paging ---
    page: conint(ge=0) = Field(0, description="Page number (0-indexed).")
    per_page: conint(ge=1, le=100) = Field(10, description="Max results per page (institutions).")

    # --- Program nesting behavior ---
    all_programs_nested: bool = Field(
        False,
        description=(
            "If False (default), Scorecard tries to return only matching program entries "
            "in the nested list. If True, return *all* program entries per institution, "
            "even if you filtered by a specific program."
        ),
    )

    @field_validator("state")
    @classmethod
    def _norm_state(cls, v):
        return v.upper() if v else v

    @field_validator("program_text")
    @classmethod
    def _strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("award_levels", mode="before")
    @classmethod
    def _merge_award_levels(cls, raw_levels, info):
        """
        Merge numeric award_levels with named award_levels into a final numeric list.
        Deduplicate and preserve small size.
        """
        # In Pydantic v2, we need to access other field values through info.data
        values = info.data if info else {}
        named = values.get("award_levels_named")
        merged: List[int] = list(raw_levels or [])
        if named:
            for name in named:
                codes = AWARD_LEVELS_MAP.get(name.lower())
                if codes:
                    merged.extend(codes)
        # Deduplicate while preserving order
        seen = set()
        deduped = []
        for x in merged:
            if x not in seen:
                seen.add(x)
                deduped.append(x)
        return deduped or None

    @model_validator(mode='before')
    @classmethod
    def _at_least_one_filter(cls, values):
        """
        Ensure the user supplied at least one of cip_prefix or program_text.
        """
        if not (values.get("cip_prefix") or values.get("program_text")):
            raise ValueError("Provide at least one filter: cip_prefix or program_text.")
        return values


# ---------------------------------------------------------------------------
# 4) The Strands tool function
# ---------------------------------------------------------------------------
@tool(
    name="scorecard.prog.search",
    description=(
        "Search institutions by program (Field-of-Study) using CIP code or program title keywords. "
        "Optionally filter by award level(s), state, and control (public/private/for-profit). "
        "Returns institutions with an array of matched program rows."
    ),
)
async def programs_search(args: ProgramsSearchArgs) -> Dict[str, Any]:
    """
    Perform a programs (field-of-study) search.

    Returns a dict:
    {
      'cards': [
        {
          'id': 123456,
          'name': 'Example University',
          'city': 'Rochester',
          'state': 'NY',
          'programs': [
              {
                'cip': '11.0101',
                'title': 'Computer Science',
                'credential': 3,
                'earnings_high_q': 98765,
                'debt_median': 15000
              },
              ...
          ]
        },
        ...
      ],
      'metadata': {...},   # pagination info
      'raw': {...}         # the full API response (optional debugging/enrichment)
    }
    """
    # -----------------------------------------------------------------------
    # STEP 1: Base params
    # -----------------------------------------------------------------------
    params: Dict[str, Any] = {
        "api_key": get_key(),
        "fields": FOS_FIELDS,
        "_per_page": args.per_page,
        "page": args.page,
    }

    # Include all nested programs or only the matching ones
    if args.all_programs_nested:
        params["all_programs_nested"] = "true"

    # -----------------------------------------------------------------------
    # STEP 2: Program filters
    # -----------------------------------------------------------------------
    # CIP prefix: the API accepts exact CIP values; prefix support can vary.
    # Common pattern is to pass a CIP "prefix" and let their backend match.
    # If strict exact-match is enforced in your testing, you can loop prefixes client-side.
    if args.cip_prefix:
        params["latest.programs.cip_6_digit.code"] = args.cip_prefix

    # Program title keyword (best-effort; if not supported by API for your field,
    # you can fetch and filter client-side by title lower().find(keyword) >= 0)
    if args.program_text:
        params["latest.programs.cip_6_digit.title__contains"] = args.program_text

    # -----------------------------------------------------------------------
    # STEP 3: Institution filters
    # -----------------------------------------------------------------------
    if args.state:
        params["school.state"] = args.state
    if args.control:
        params["school.control"] = CONTROL_MAP[args.control]

    # -----------------------------------------------------------------------
    # STEP 4: Award level(s)
    # -----------------------------------------------------------------------
    # If present, serialize as comma-separated list for __in filter semantics.
    if args.award_levels:
        params["latest.programs.cip_6_digit.credential__in"] = ",".join(map(str, args.award_levels))

    # -----------------------------------------------------------------------
    # STEP 5: Call the API
    # -----------------------------------------------------------------------
    data = await fetch_json(params)

    # -----------------------------------------------------------------------
    # STEP 6: Normalize into institution "cards" with matched programs
    # -----------------------------------------------------------------------
    cards: List[Dict[str, Any]] = []

    # The API returns a flat list of results where the nested FOS fields correspond
    # to (one of) the program rows. Given our restricted fields list, each result row
    # represents an institution + a single program match. We group by institution id.
    by_id: Dict[int, Dict[str, Any]] = {}

    for row in data.get("results", []):
        inst_id = row.get("id")
        if inst_id is None:
            # Skip rows without an id (unlikely, but defensive)
            continue

        # Build or reuse the institution card
        card = by_id.get(inst_id)
        if not card:
            card = {
                "id": inst_id,
                "name": row.get("school.name"),
                "city": row.get("school.city"),
                "state": row.get("school.state"),
                "programs": [],  # we'll append program matches below
            }
            by_id[inst_id] = card

        # Extract the (one) program payload present on this row
        prog = {
            "cip": row.get("latest.programs.cip_6_digit.code"),
            "title": row.get("latest.programs.cip_6_digit.title"),
            "credential": row.get("latest.programs.cip_6_digit.credential"),
            "earnings_high_q": row.get("latest.programs.cip_6_digit.earnings.highest_quartile"),
            "debt_median": row.get("latest.programs.cip_6_digit.debt.median"),
        }

        # Only add if we actually have a CIP code/title (some rows may be sparse/suppressed)
        if prog["cip"] or prog["title"]:
            card["programs"].append(prog)

    # Convert the grouped map into a list for output
    cards = list(by_id.values())

    # -----------------------------------------------------------------------
    # STEP 7: Format response with enhanced ToolResult format
    # -----------------------------------------------------------------------
    if not cards:
        return "No programs found matching your criteria. Try broadening your search parameters."

    # Create formatted text for human reading
    summary_lines = []
    metadata = data.get("metadata", {})
    total_results = metadata.get("total", len(cards))
    current_page = metadata.get("page", args.page)
    
    summary_lines.append(f"Found {total_results} institutions with matching programs.")
    summary_lines.append(f"Showing page {current_page + 1}, {len(cards)} results:")
    summary_lines.append("")
    
    for card in cards:
        # Format institution header
        inst_info = f"**{card['name']}** (ID: {card['id']})"
        if card['city'] and card['state']:
            inst_info += f" - {card['city']}, {card['state']}"
        summary_lines.append(inst_info)
        
        # Format programs for this institution
        for prog in card['programs']:
            prog_line = f"  • {prog['title']} (CIP: {prog['cip']})"
            if prog['credential']:
                cred_map = {1: "Certificate", 2: "Associate", 3: "Bachelor's", 4: "Post-bacc Cert", 5: "Master's", 6: "Doctoral"}
                prog_line += f" - {cred_map.get(prog['credential'], f"Level {prog['credential']}")}"
            if prog['earnings_high_q']:
                prog_line += f" - Top 25% Earnings: ${prog['earnings_high_q']:,}"
            summary_lines.append(prog_line)
        summary_lines.append("")
    
    if len(cards) < total_results:
        summary_lines.append(f"💡 Use page={current_page + 1} to see more results.")

    return "\n".join(summary_lines)
