"""CLI entry point for LinkedIn MCP Server utilities."""

import sys
import argparse
from .callback_server import run_callback_server


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="LinkedIn MCP Server utilities",
        prog="python -m linkedin_mcp_server"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Callback server command
    callback_parser = subparsers.add_parser(
        "callback-server",
        help="Run OAuth callback server"
    )
    callback_parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="Port to run the server on (default: 8080)"
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    if args.command == "callback-server":
        print(f"Starting LinkedIn OAuth callback server on port {args.port}...")
        run_callback_server(args.port)
    else:
        parser.print_help()


if __name__ == "__main__":
    main() 