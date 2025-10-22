"""
FastAPI Web Application for College Scorecard Agent
==================================================

A web interface for the Strands College Scorecard agent that provides:
- Real-time streaming chat interface
- Server-Sent Events (SSE) for live responses
- Static file serving for frontend assets
- CORS support for development

Usage:
    uvicorn web_app:app --reload --host 0.0.0.0 --port 8000
"""

import asyncio
import json
import logging
import os
from typing import AsyncGenerator
from pathlib import Path

# Load environment variables from .env file (like JavaScript dotenv)
from dotenv import load_dotenv
load_dotenv()  # This loads .env file variables into os.environ

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import our Strands agent
from agent import make_agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log environment configuration (without exposing secrets)
logger.info(f"AWS_REGION: {os.getenv('AWS_REGION', 'not-set')}")
logger.info(f"COLLEGE_SCORECARD_API_KEY: {'set' if os.getenv('COLLEGE_SCORECARD_API_KEY') else 'using-demo-key'}")

# Initialize FastAPI app
app = FastAPI(
    title="College Scorecard Assistant",
    description="AI-powered college search using the U.S. College Scorecard API",
    version="1.0.0"
)

# Add CORS middleware for frontend development
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
@app.post("/chat/stream")
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
                if "data" in event:
                    print(f"📟 Text: {event["data"]}")

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