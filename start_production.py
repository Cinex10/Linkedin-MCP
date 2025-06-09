#!/usr/bin/env python3
"""Production startup script for LinkedIn MCP Server with SSE transport."""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Start the LinkedIn MCP Server in production mode."""
    
    # Set production environment variables
    env = os.environ.copy()
    env.update({
        "PRODUCTION_MODE": "true",
        "MCP_TRANSPORT": "sse",
    })
    
    # Get configuration from environment or use defaults
    host = env.get("MCP_SERVER_HOST", "0.0.0.0")
    port = env.get("MCP_SERVER_PORT", "8000")
    
    # Set uvicorn environment variables for the MCP SDK v1.0
    env.update({
        "UVICORN_HOST": host,
        "UVICORN_PORT": port,
        "UVICORN_LOG_LEVEL": "info"
    })
    
    # Path to the server module
    script_dir = Path(__file__).parent
    server_script = script_dir / "linkedin_mcp_server" / "main.py"
    
    print(f"🚀 Starting LinkedIn MCP Server in Production Mode")
    print(f"   Transport: SSE")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Server Script: {server_script}")
    print()
    
    # Build the command to run the server
    cmd = [sys.executable, str(server_script)]
    
    print(f"Executing: {' '.join(cmd)}")
    print(f"Environment: UVICORN_HOST={host}, UVICORN_PORT={port}")
    print("=" * 60)
    
    try:
        # Run the server
        subprocess.run(cmd, env=env, check=True)
    except KeyboardInterrupt:
        print("\n⏹️  Server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Server failed with exit code {e.returncode}")
        sys.exit(e.returncode)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 