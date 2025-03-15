#!/usr/bin/env python3
"""
Script to run the Chicky Control server
"""
import os
import logging

import uvicorn

# Get port from environment variable
PORT = int(os.getenv("PORT", "3000"))

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Run the server
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=PORT,
        reload=True,
    ) 