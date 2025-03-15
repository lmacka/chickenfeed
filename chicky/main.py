#!/usr/bin/env python3
"""
Main entry point for the Chickenfeed Pi component
This file is just a wrapper around the actual server implementation
"""

import logging
from src.server import run_server

if __name__ == "__main__":
    try:
        run_server()
    except Exception as e:
        logging.error(f"Failed to start server: {e}")
        exit(1) 