"""Main entry point for LinkedIn MCP Server."""

import sys
import asyncio
import logging
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from linkedin_mcp_server.server import get_server
from linkedin_mcp_server.config import validate_config


def main() -> None:
    """Main function to run the LinkedIn MCP Server."""
    # Get configuration first
    from linkedin_mcp_server.config import get_config
    config = get_config()
    
    # Set up logging
    log_level = logging.DEBUG if config.production_mode else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    try:
        # Get the server instance (don't validate config upfront)
        # Configuration will be validated when OAuth operations are attempted
        server = get_server()
        
        # Log server configuration
        mode = "Production" if config.production_mode else "Development"
        logger.info(f"Starting LinkedIn MCP Server in {mode} mode...")
        logger.info(f"Transport: {config.transport_mode}")
        logger.info(f"Host: {config.server_host}")
        logger.info(f"Port: {config.server_port}")
        
        if config.transport_mode == "sse":
            logger.info("Server will be available at:")
            logger.info(f"  - SSE endpoint: http://{config.server_host}:{config.server_port}/sse")
            logger.info(f"  - Message endpoint: http://{config.server_host}:{config.server_port}/messages/")
        elif config.transport_mode == "streamable-http":
            logger.info("Server will be available at:")
            logger.info(f"  - HTTP endpoint: http://{config.server_host}:{config.server_port}/mcp")
        else:
            logger.info("Using stdio transport for local development")
        
        # Run the server with configured transport
        if config.transport_mode == "sse":
            logger.info("Starting server with SSE transport")
            logger.info(f"Server will be available at http://{config.server_host}:{config.server_port}/sse")
            
            # For SSE, we need to run the server manually with uvicorn
            import uvicorn
            sse_app = server.sse_app()
            uvicorn.run(
                sse_app,
                host=config.server_host,
                port=config.server_port,
                log_level="info" if config.production_mode else "debug"
            )
        elif config.transport_mode == "streamable-http":
            logger.info("Starting server with Streamable HTTP transport")
            logger.info(f"Server will be available at http://{config.server_host}:{config.server_port}/mcp")
            # Use async Streamable HTTP runner
            import asyncio
            asyncio.run(server.run_streamable_http_async())
        else:
            # Default to stdio for development
            logger.info("Starting server with STDIO transport")
            server.run()
        
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 