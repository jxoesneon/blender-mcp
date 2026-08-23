#!/usr/bin/env python3
"""
CLI entry point for running the Blender MCP server.
"""

import sys
import os

# Add src to pythonpath
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from blender_mcp.server import main

if __name__ == "__main__":
    main()
