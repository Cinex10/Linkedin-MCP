FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONPATH=/app
ENV PRODUCTION_MODE=true
ENV MCP_TRANSPORT=sse
ENV MCP_SERVER_HOST=0.0.0.0
ENV MCP_SERVER_PORT=8000

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml uv.lock ./
COPY linkedin_mcp_server/ ./linkedin_mcp_server/
COPY start_production.py ./

# Install UV for dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install dependencies
RUN uv sync --frozen

# Expose the port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/sse || exit 1

# Run the server using the production startup script
CMD ["uv", "run", "python", "start_production.py"] 