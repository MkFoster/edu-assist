"""
College Search Assistant - FastAPI Web Application
================================================

A production-ready web interface for the AI-powered college search assistant.
Built with FastAPI and deployed on AWS App Runner, this application provides:

Features:
- Real-time streaming chat interface with Server-Sent Events (SSE)
- Static file serving for frontend assets (HTML/CSS/JS)
- CORS support for cross-origin requests
- Secure credential management via AWS Secrets Manager
- Auto-scaling deployment on AWS App Runner

Architecture:
- FastAPI backend with async/await support
- Strands AI agent integration with Amazon Bedrock (Claude 4.5 Sonnet)
- Custom tools for U.S. Department of Education College Scorecard API
- Streaming responses for real-time user experience

Deployment:
- AWS App Runner for serverless container hosting
- GitHub integration for automatic deployments
- Environment variables managed via AWS Secrets Manager
- Horizontal auto-scaling based on traffic

Local Development:
    uvicorn web_app:app --reload --host 0.0.0.0 --port 8000

Production:
    Deployed automatically via AWS App Runner from GitHub repository

API Endpoints:
- GET /: Main chat interface (HTML)
- POST /chat: Submit chat messages
- GET /stream: Server-Sent Events for streaming responses
- Static files served from root directory

Author: Mark Foster
Last Updated: October 2025
"""

import asyncio
import json
import logging
import os
from typing import AsyncGenerator
from pathlib import Path

# Load environment variables from .env file for local development
# In production (AWS App Runner), these come from AWS Secrets Manager
from dotenv import load_dotenv
load_dotenv()

# FastAPI framework and supporting libraries
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import our custom college search agent
from agent import make_agent

# Configure application logging for debugging and monitoring
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log environment configuration status (without exposing sensitive data)
logger.info(f"AWS_REGION: {os.getenv('AWS_REGION', 'not-set')}")
logger.info(f"COLLEGE_SCORECARD_API_KEY: {'set' if os.getenv('COLLEGE_SCORECARD_API_KEY') else 'using-demo-key'}")

# Initialize FastAPI application with metadata
app = FastAPI(
    title="College Search Assistant",
    description="AI-powered college and academic program search using official U.S. Department of Education data",
    version="2.0.0",
    docs_url="/api/docs",  # Swagger UI documentation
    redoc_url="/api/redoc"  # ReDoc documentation
)

# Configure CORS for cross-origin requests (development and production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the agent
agent = make_agent()

# Request models
class ChatRequest(BaseModel):
    """Request model for chat messages."""
    message: str

class ChatResponse(BaseModel):
    """Response model for chat messages."""
    response: str
    success: bool
    error: str = None


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "college-scorecard-agent"}


# Non-streaming chat endpoint
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Simple chat endpoint that returns the complete response.
    """
    try:
        logger.info(f"Received chat request: {request.message}")
        
        # Invoke the agent
        result = await agent.invoke_async(request.message)
        print(f"Agent result: {result}")
        
        # Extract the response text
        response_text = getattr(result, "output", str(result))
        
        return ChatResponse(
            response=response_text,
            success=True
        )
        
    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        return ChatResponse(
            response="",
            success=False,
            error=str(e)
        )


# Streaming chat endpoint using Server-Sent Events
@app.post("/chat/stream", response_model=ChatResponse)
async def stream_chat(request: ChatRequest):
    """
    Streaming chat endpoint using Server-Sent Events (SSE).
    
    This provides real-time updates as the agent processes the request,
    including tool usage and incremental text generation.
    """

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate Server-Sent Events for the chat response."""
        try:
            logger.info(f"Starting streaming chat for: {request.message}")
            
            # Send initial status
            yield f"data: {json.dumps({'type': 'status', 'message': 'Processing your request...'})}\n\n"
            
            # Stream agent events
            async for event in agent.stream_async(request.message):

                # Track event loop lifecycle
                if event.get("init_event_loop", False):
                    print("🔄 Event loop initialized")
                elif event.get("start_event_loop", False):
                    print("▶️ Event loop cycle starting")
                elif "message" in event:
                    print(f"📬 New message created: {event['message']['role']}")
                elif event.get("complete", False):
                    print("✅ Cycle completed")
                elif event.get("force_stop", False):
                    print(f"🛑 Event loop force-stopped: {event.get('force_stop_reason', 'unknown reason')}")

                # Track tool usage
                if "current_tool_use" in event and event["current_tool_use"].get("name"):
                    tool_name = event["current_tool_use"]["name"]
                    print(f"🔧 Using tool: {tool_name}")

                # Show only a snippet of text to keep output clean
                #if "data" in event:
                #    print(f"📟 Text: {event["data"]}")

                # Handle text chunks
                if "data" in event and event["data"]:
                    yield f"data: {json.dumps({'type': 'text', 'content': event['data']})}\n\n"
                
                # Handle tool usage
                elif "current_tool_use" in event and event["current_tool_use"].get("name"):
                    tool_name = event["current_tool_use"]["name"]
                    yield f"data: {json.dumps({'type': '🔧tool', 'name': tool_name, 'status': 'using'})}\n\n"
                
                # Handle completion
                elif "result" in event:
                    yield f"data: {json.dumps({'type': 'complete', 'message': 'Response complete'})}\n\n"
                
                # Handle errors
                elif event.get("force_stop"):
                    reason = event.get("force_stop_reason", "Unknown error")
                    yield f"data: {json.dumps({'type': 'error', 'message': reason})}\n\n"
            
            # Send final completion signal
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            logger.error(f"Error in streaming chat: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# Serve the main HTML page
@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the main chat interface."""
    try:
        # Get the directory where this script is located
        current_dir = Path(__file__).parent
        html_file_path = current_dir / "index.html"
        
        # Read the HTML file
        with open(html_file_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
            
        return HTMLResponse(content=html_content)
    
    except FileNotFoundError:
        # Fallback error page if index.html is not found
        error_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Error</title></head>
        <body>
            <h1>Error</h1>
            <p>The index.html file was not found. Please ensure it exists in the same directory as web_app.py</p>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=500)


# Serve the privacy policy page
@app.get("/privacy-policy.html", response_class=HTMLResponse)
async def serve_privacy_policy():
    """Serve the privacy policy page."""
    try:
        # Get the directory where this script is located
        current_dir = Path(__file__).parent
        html_file_path = current_dir / "privacy-policy.html"
        
        # Read the HTML file
        with open(html_file_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
            
        return HTMLResponse(content=html_content)
    
    except FileNotFoundError:
        # Fallback error page if privacy-policy.html is not found
        error_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Error</title></head>
        <body>
            <h1>Privacy Policy Not Found</h1>
            <p>The privacy-policy.html file was not found.</p>
            <a href="/">← Back to EDU Assist</a>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=404)


# Serve the user agreement page
@app.get("/user-agreement.html", response_class=HTMLResponse)
async def serve_user_agreement():
    """Serve the user agreement page."""
    try:
        # Get the directory where this script is located
        current_dir = Path(__file__).parent
        html_file_path = current_dir / "user-agreement.html"
        
        # Read the HTML file
        with open(html_file_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
            
        return HTMLResponse(content=html_content)
    
    except FileNotFoundError:
        # Fallback error page if user-agreement.html is not found
        error_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Error</title></head>
        <body>
            <h1>User Agreement Not Found</h1>
            <p>The user-agreement.html file was not found.</p>
            <a href="/">← Back to EDU Assist</a>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=404)


# Serve the about page
@app.get("/about.html", response_class=HTMLResponse)
async def serve_about():
    """Serve the about page."""
    try:
        # Get the directory where this script is located
        current_dir = Path(__file__).parent
        html_file_path = current_dir / "about.html"
        
        # Read the HTML file
        with open(html_file_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
            
        return HTMLResponse(content=html_content)
    
    except FileNotFoundError:
        # Fallback error page if about.html is not found
        error_html = """
        <!DOCTYPE html>
        <html>
        <head><title>Error</title></head>
        <body>
            <h1>About Page Not Found</h1>
            <p>The about.html file was not found.</p>
            <a href="/">← Back to EDU Assist</a>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=404)


# API documentation endpoint
@app.get("/docs-info")
async def api_docs_info():
    """Information about available API endpoints."""
    return {
        "endpoints": {
            "/": "Main chat interface (HTML)",
            "/health": "Health check endpoint",
            "/chat": "Simple chat endpoint (JSON response)",
            "/chat/stream": "Streaming chat endpoint (Server-Sent Events)",
            "/docs": "Swagger UI documentation",
            "/redoc": "ReDoc API documentation"
        },
        "usage": {
            "streaming": "Use /chat/stream for real-time responses",
            "simple": "Use /chat for complete responses",
            "frontend": "Visit / for the web interface"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    print("🎓 Starting College Scorecard Web Assistant...")
    print("📖 Visit http://localhost:8000 for the web interface")
    print("🔗 Visit http://localhost:8000/docs for API documentation")
    
    uvicorn.run(
        "web_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )