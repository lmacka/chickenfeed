#!/usr/bin/env python3
"""
Main entry point for the Chicky Control server
"""
import os
import logging
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.services.socket_service import create_socketio_app
from app.routers import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Get configuration from environment variables
PORT = int(os.getenv("PORT", "3000"))
AUTH_TOKEN = os.getenv("CHICKY_AUTH_TOKEN", "default-token-change-me")

def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application
    
    Returns:
        Configured FastAPI application
    """
    # Create FastAPI app
    app = FastAPI(title="Chicky Control")
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routes
    app.include_router(api_router.router)
    
    # Create Socket.IO app and attach it to FastAPI
    socketio_app = create_socketio_app(auth_token=AUTH_TOKEN)
    app.mount("/socket.io", socketio_app)
    
    return app

app = create_app()

if __name__ == "__main__":
    logger.info(f"Starting server on port {PORT}")
    logger.info(f"Auth token is {'configured' if AUTH_TOKEN != 'default-token-change-me' else 'not configured'}")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
    ) 