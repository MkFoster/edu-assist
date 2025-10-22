"""
College Search Agent - Strands AI Agent Implementation
====================================================

This module creates and configures a Strands AI agent powered by Amazon Bedrock 
(Claude 4.5 Sonnet) for helping users find colleges and academic programs using 
the U.S. Department of Education College Scorecard API.

Key Features:
- AWS Bedrock integration with Claude 4.5 Sonnet model
- Custom tools for college/program search and details
- Environment variable management for AWS credentials
- Production-ready configuration for AWS App Runner deployment

Architecture:
- Strands Agent framework for AI orchestration
- Custom tools registered via decorators
- Secure credential handling via environment variables
- Support for both local development and cloud deployment

Usage:
    # For local development
    python agent.py
    
    # For web deployment (called by web_app.py)
    from agent import make_agent
    agent = make_agent()

Environment Variables Required:
- AWS_ACCESS_KEY_ID: AWS access key for Bedrock access
- AWS_SECRET_ACCESS_KEY: AWS secret key for Bedrock access  
- AWS_REGION: AWS region (default: us-east-1)
- COLLEGE_SCORECARD_API_KEY: Department of Education API key
- STRANDS_MODEL_ID: Bedrock model ID (default: anthropic.claude-sonnet-4-5-20250929-v1:0)

Author: Mark Foster
Last Updated: October 2025
"""

import asyncio
import os

# Load environment variables from .env file for local development
# In production (App Runner), these come from AWS Secrets Manager
from dotenv import load_dotenv
load_dotenv()

# Import all tool modules to register the @tool-decorated functions with Strands
# This registration happens automatically on import
from tools import (
    college_jokes,      # Lighthearted college-related jokes
    meta,              # Metadata and mappings for college data
    programs_search,   # Search for academic programs by criteria
    schools_search,    # Search for schools/colleges by location, type, etc.
    school_detail      # Get detailed information about specific schools
)

# Strands AI framework and AWS SDK
from strands import Agent
import boto3

def make_agent():
    """
    Create and configure a Strands AI agent for college search assistance.
    
    This function:
    1. Loads AWS credentials from environment variables
    2. Clears any conflicting AWS profile settings
    3. Creates a Strands Agent with Bedrock (Claude 4.5 Sonnet)
    4. Registers all custom college search tools
    
    Returns:
        Agent: Configured Strands agent ready for college search queries
        
    Environment Variables:
        AWS_ACCESS_KEY_ID: Required for Bedrock access
        AWS_SECRET_ACCESS_KEY: Required for Bedrock access
        AWS_REGION: AWS region (default: us-east-1)
        STRANDS_MODEL_ID: Bedrock model identifier
    """
    # Load AWS credentials from environment (set by App Runner or .env file)
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    
    if aws_access_key and aws_secret_key:
        # Ensure environment variables are set for boto3/Strands
        os.environ['AWS_ACCESS_KEY_ID'] = aws_access_key
        os.environ['AWS_SECRET_ACCESS_KEY'] = aws_secret_key
        os.environ['AWS_REGION'] = aws_region
        
        # Clear any AWS profile environment variables that might conflict
        # This prevents profile-related errors in containerized environments
        if 'AWS_PROFILE' in os.environ:
            del os.environ['AWS_PROFILE']
        if 'AWS_DEFAULT_PROFILE' in os.environ:
            del os.environ['AWS_DEFAULT_PROFILE']
    
    # Create Strands agent with college search specialization
    # The agent uses Claude 3.5 Sonnet via Amazon Bedrock
    agent = Agent(
        name="college-helper",
        description="AI assistant specialized in college and academic program search using official U.S. Department of Education data.",
        system_prompt=(
            "You are an expert college search assistant powered by the U.S. Department of Education College Scorecard API. "
            "Help users find colleges, universities, and academic programs based on their criteria. "
            "Use the available tools to search for schools, programs, and detailed information. "
            "Prefer using 'tools.schools_search', 'tools.programs_search', and 'tools.school_detail' functions. "
            "Provide helpful, accurate information and mention which tools were used briefly. "
            "Focus on being conversational and helpful rather than technical."
        ),
        callback_handler=None  # No custom callbacks for this implementation
    )

    return agent

async def repl(agent: Agent):
    """
    Run an interactive command-line interface for the college search agent.
    
    This provides a simple REPL (Read-Eval-Print Loop) for testing the agent
    locally during development. In production, the agent is used via the web interface.
    
    Args:
        agent: Configured Strands agent instance
    """
    print("🎓 College Search Assistant ready!")
    print("Ask me about colleges, programs, admissions, or anything education-related.")
    print("Type 'exit' or 'quit' to end the session.\n")
    
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye! 👋")
            break
            
        if user_input.lower() in {"exit", "quit", "bye"}:
            print("Goodbye! Good luck with your college search! 🎓")
            break
            
        if not user_input:
            continue
            
        try:
            # Get response from the agent
            result = await agent.invoke_async(user_input)
            response = getattr(result, "output", str(result))
            print(f"\nAssistant: {response}\n")
        except Exception as e:
            print(f"\nSorry, I encountered an error: {e}\n")


if __name__ == "__main__":
    """
    Entry point for local development and testing.
    
    Run this script directly to interact with the agent via command line:
        python agent.py
    """
    try:
        agent = make_agent()
        asyncio.run(repl(agent))
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Failed to start agent: {e}")
