"""
FastAPI application for the Chickenfeed Pi component
"""
from typing import Dict, Any

from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.routes.api import router as api_router
from src.utils.logger import get_logger
from src.lifecycle import lifespan

logger = get_logger(__name__)

def create_app(config: Dict[str, Any]) -> FastAPI:
    """
    Create and configure the FastAPI application
    
    Args:
        config: Configuration dictionary
        
    Returns:
        FastAPI application
    """
    app = FastAPI(
        title="Chickenfeed Pi",
        description="Raspberry Pi component of the Chickenfeed project",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Store config in app.state for access in routes
    app.state.config = config
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Request logging middleware removed to reduce verbosity
    
    # Error handler middleware
    @app.middleware("http")
    async def error_handler(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            logger.error(f"Unhandled error: {e}")
            return Response(
                content={"error": "Internal server error", "message": str(e)},
                status_code=500
            )
    
    # Include API routes
    app.include_router(api_router)
    
    return app 