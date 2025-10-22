"""
College Humor and Entertainment Tool
===================================

Strands AI tool providing lighthearted college-themed humor to enhance
the college search experience. This tool offers family-friendly jokes
and entertainment to help reduce stress and add levity to the college
exploration process.

Purpose:
- Provide comic relief during intensive college search sessions
- Break the ice in conversations about college planning
- Add personality and warmth to the AI assistant experience
- Help students and families maintain a positive attitude

Features:
- Curated collection of clean, college-themed jokes
- Random selection for variety in repeated interactions
- Educational humor that connects to college experiences
- Family-friendly content appropriate for all audiences

Content Categories:
- Academic life and studying humor
- Student lifestyle and campus experiences
- Educational wordplay and puns
- General college-related situations

Usage in Conversation:
- When users seem stressed about college decisions
- To lighten the mood during complex financial discussions
- As an ice-breaker for new conversations
- When explicitly requested by users

Integration:
This tool is automatically available to the Strands agent and can be
triggered through natural language requests for humor or entertainment.

Author: Mark Foster
Last Updated: October 2025
"""

import random
from typing import Dict, Any
from pydantic import BaseModel
from strands import tool


# ---------------------------------------------------------------------------
# Hard-coded collection of college jokes
# ---------------------------------------------------------------------------
COLLEGE_JOKES = [
    "Why did the student eat his homework? Because the teacher told him it was a piece of cake!",
    
    "What do you call a student who's afraid of Santa? Claustrophobic!",
    
    "Why don't college students ever get cold? Because they're always in their degrees!",
    
    "What's the difference between a college student and a large pizza? A large pizza can feed a family of four!",
    
    "Why did the math student break up with the English student? Because they had no common factors!",
    
    "What do you call a college student who works at a bank? A loan ranger!",
    
    "Why did the college student bring a ladder to class? Because they wanted to go to high school!",
    
    "What's a college student's favorite type of music? Wrap music... because they're always wrapping up assignments!",
    
    "Why don't college students trust stairs? Because they're always up to something!",
    
    "What did the college student say when they finally graduated? 'I'm degree-lighted!'"
]


# ---------------------------------------------------------------------------
# Input model (no parameters needed, but keeping consistent structure)
# ---------------------------------------------------------------------------
class CollegeJokesArgs(BaseModel):
    """Arguments for getting college jokes (currently no parameters needed)."""
    pass


# ---------------------------------------------------------------------------
# The actual Strands tool
# ---------------------------------------------------------------------------
@tool(
    name="college_jokes.random",
    description="Get a random college-themed joke to lighten the mood during your college search!",
)
async def get_college_joke(args: CollegeJokesArgs = None) -> Dict[str, Any]:
    """
    Returns a randomly selected college-themed joke.
    
    This tool provides family-friendly humor with college themes,
    perfect for adding some fun to college search conversations.
    """
    
    # Randomly select one joke from our collection
    joke = random.choice(COLLEGE_JOKES)
    
    # Format the response
    return f"Here's a college joke for you:\n\n😄 {joke}"