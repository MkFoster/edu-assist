"""
College Scorecard API Base Utilities
===================================

Shared utilities and base functionality for all College Scorecard tools.
This module provides a centralized interface to the U.S. Department of Education
College Scorecard API with consistent error handling and configuration.

Features:
- Centralized API endpoint configuration
- Environment-based API key management
- Async HTTP client using aiohttp for non-blocking requests
- Synchronous HTTP client using requests for simple operations
- Standardized error handling and response parsing
- Support for demo mode with DEMO_KEY fallback

API Information:
- Base URL: https://api.data.gov/ed/collegescorecard/v1/schools.json
- Documentation: https://collegescorecard.ed.gov/data/documentation/
- Rate Limits: 1,000 requests per hour with API key
- Demo Key: Limited functionality for testing

Usage:
    from tools.scorecard_base import fetch_json, get_key
    
    # Get API key
    api_key = get_key()
    
    # Make async API request
    params = {"api_key": api_key, "fields": "school.name,id"}
    data = await fetch_json(params)

Environment Variables:
- COLLEGE_SCORECARD_API_KEY: Your API key from api.data.gov

Author: Mark Foster
Last Updated: October 2025
"""

import os
import requests
import aiohttp
from typing import Dict, Any

# Base URL for the U.S. Department of Education's College Scorecard API.
# This endpoint returns institution and program data in JSON format.
API_BASE = "https://api.data.gov/ed/collegescorecard/v1/schools.json"


# ---------------------------------------------------------------------------
# 1. Get the API key from environment variables
# ---------------------------------------------------------------------------
def get_key() -> str:
    """
    Returns the College Scorecard API key from the environment.

    For demo purposes, returns "DEMO_KEY" if no key is set.
    In production, you should get a real API key from https://api.data.gov/signup/
    """
    key = os.getenv("COLLEGE_SCORECARD_API_KEY")
    if not key:
        # Return demo key for testing - in production this should raise an error
        return "DEMO_KEY"
    return key


# ---------------------------------------------------------------------------
# 2. Fetch JSON data from the College Scorecard API (Async version)
# ---------------------------------------------------------------------------
async def fetch_json(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Makes an asynchronous HTTP GET request to the College Scorecard API.

    Args:
        params (dict): Query parameters for the API request.
                       These include your 'api_key', 'fields', filters, etc.

    Returns:
        dict: Parsed JSON response from the API.

    Raises:
        RuntimeError: if the API returns a non-200 status code or invalid JSON.
    """

    # aiohttp allows us to make non-blocking (async) HTTP calls.
    # This lets multiple tools run in parallel when the agent is handling many requests.
    async with aiohttp.ClientSession() as session:
        # The API expects parameters like api_key, school.city, fields, etc.
        async with session.get(API_BASE, params=params, timeout=25) as response:
            # If the API returns an error (like 400, 403, or 500),
            # we raise an exception with the text for debugging.
            if response.status != 200:
                text = await response.text()
                raise RuntimeError(
                    f"College Scorecard API error {response.status}: {text}"
                )

            # Parse the API’s JSON response body into a Python dictionary.
            # If the API responds with invalid JSON, aiohttp raises a ContentTypeError.
            data = await response.json()

    # At this point, data typically looks like:
    # {
    #   "metadata": { "total": 1234, "page": 0, "per_page": 10 },
    #   "results": [ { "id": 123456, "school.name": "Example University", ... }, ... ]
    # }

    return data


# ---------------------------------------------------------------------------
# 3. Synchronous version for simple tools
# ---------------------------------------------------------------------------
def fetch_json_sync(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Makes a synchronous HTTP GET request to the College Scorecard API.

    Args:
        params (dict): Query parameters for the API request.

    Returns:
        dict: Parsed JSON response from the API.

    Raises:
        RuntimeError: if the API returns a non-200 status code or invalid JSON.
    """
    response = requests.get(API_BASE, params=params, timeout=25)
    
    if response.status_code != 200:
        raise RuntimeError(
            f"College Scorecard API error {response.status_code}: {response.text}"
        )
    
    return response.json()


# Remove the conflicting alias - use the async version directly
