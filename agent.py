# app.py
import asyncio
import os

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# --- Import tools from subpackage ---
# The act of importing registers the @tool-decorated functions with Strands
# The tools/__init__.py auto-discovers and imports all tool modules
import tools  # noqa: F401

# --- Strands setup ---
from strands import Agent

def make_agent():
    # Set AWS environment variables if they're in the .env file
    # Strands will automatically pick these up
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    
    if aws_access_key and aws_secret_key:
        os.environ['AWS_ACCESS_KEY_ID'] = aws_access_key
        os.environ['AWS_SECRET_ACCESS_KEY'] = aws_secret_key
        os.environ['AWS_REGION'] = aws_region
    
    # Create agent with basic configuration
    # Strands will use AWS credentials from environment automatically
    agent = Agent(
        name="college-helper",
        description="Helps users find colleges and programs using the U.S. College Scorecard API.",
        system_prompt=(
            "You are a helpful college search assistant. "
            "Use the scorecard tools to find schools, programs, and details. "
            "Prefer the 'tools.schools_search', 'tools.programs_search', and 'tools.school_detail' functions."
        ),
        callback_handler=None
    )

    return agent

async def repl(agent: Agent):
    print("🎓 College helper agent ready. Type 'exit' to quit.")
    while True:
        try:
            user = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if user.lower() in {"exit", "quit"}:
            break

        result = await agent.invoke_async(user)
        print("\nAssistant:", getattr(result, "output", result))


if __name__ == "__main__":
    agent = make_agent()
    asyncio.run(repl(agent))
