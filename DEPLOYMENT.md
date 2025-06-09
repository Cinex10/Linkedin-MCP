# LinkedIn MCP Server - Production Deployment Guide

This guide covers deploying the LinkedIn MCP Server using Server-Sent Events (SSE) transport for production environments.

## 🚀 Quick Start

### 1. Environment Setup

Create a `.env` file with your LinkedIn API credentials:

```bash
# LinkedIn API Settings
CLIENT_ID=your_CLIENT_ID_here
CLIENT_SECRET=your_CLIENT_SECRET_here
REDIRECT_URI=https://your-domain.com/callback

# Production Settings
PRODUCTION_MODE=true
MCP_TRANSPORT=sse
MCP_SERVER_HOST=0.0.0.0
MCP_SERVER_PORT=8000
```

### 2. Docker Deployment

#### Option A: Docker Compose (Recommended)

```bash
# Build and start the server
docker-compose up -d

# Check logs
docker-compose logs -f linkedin-mcp

# Stop the server
docker-compose down
```

#### Option B: Docker Only

```bash
# Build the image
docker build -t linkedin-mcp .

# Run the container
docker run -d \
  --name linkedin-mcp \
  -p 8000:8000 \
  --env-file .env \
  linkedin-mcp
```

### 3. Direct Python Deployment

```bash
# Set environment variables
export PRODUCTION_MODE=true
export MCP_TRANSPORT=sse
export MCP_SERVER_HOST=0.0.0.0
export MCP_SERVER_PORT=8000

# Run the server
uv run python -m linkedin_mcp_server.main
```

## 🌐 Transport Modes

The server supports multiple transport modes via the `MCP_TRANSPORT` environment variable:

### SSE (Server-Sent Events) - Recommended for Production
```bash
export MCP_TRANSPORT=sse
```
- **Endpoints**: 
  - SSE: `http://localhost:8000/sse`
  - Messages: `http://localhost:8000/messages/`
- **Use Case**: Web-based deployments, real-time streaming
- **Benefits**: HTTP-based, firewall-friendly, supports multiple clients

### Streamable HTTP - Modern Alternative
```bash
export MCP_TRANSPORT=streamable-http
```
- **Endpoint**: `http://localhost:8000/mcp`
- **Use Case**: Modern web deployments
- **Benefits**: Efficient bidirectional communication

### STDIO - Development Only
```bash
export MCP_TRANSPORT=stdio
```
- **Use Case**: Local development and testing
- **Benefits**: Direct process communication

## 🔧 Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PRODUCTION_MODE` | `false` | Enable production optimizations |
| `MCP_TRANSPORT` | `sse` | Transport protocol (sse/streamable-http/stdio) |
| `MCP_SERVER_HOST` | `0.0.0.0` | Server bind address |
| `MCP_SERVER_PORT` | `8000` | Server port |
| `MCP_SERVER_NAME` | `LinkedIn MCP Server` | Server identification |
| `CLIENT_ID` | - | LinkedIn OAuth client ID |
| `CLIENT_SECRET` | - | LinkedIn OAuth client secret |
| `REDIRECT_URI` | - | OAuth callback URL |

## 🔒 Production Security

### HTTPS and SSL

For production deployments, always use HTTPS:

1. **With nginx reverse proxy** (recommended):
   ```bash
   docker-compose --profile proxy up -d
   ```

2. **Update nginx.conf**:
   - Replace `your-domain.com` with your actual domain
   - Add your SSL certificates to `./ssl/` directory

3. **SSL Certificate sources**:
   - Let's Encrypt (free): Use certbot
   - CloudFlare (free): Use their SSL certificates
   - Commercial: Purchase from CA

### Security Headers

The included nginx configuration adds security headers:
- HSTS (HTTP Strict Transport Security)
- X-Frame-Options
- X-Content-Type-Options
- X-XSS-Protection

### Rate Limiting

Built-in rate limiting:
- 10 requests per second per IP
- Burst capacity of 20 requests

## 🌍 Client Connection Examples

### JavaScript/Browser Client

```javascript
// Connect to SSE endpoint
const client = new MCPClient("https://your-domain.com/sse");

await client.connect();
const tools = await client.listTools();
console.log("Available tools:", tools);
```

### Python Client

```python
from fastmcp import Client

# Connect to SSE server
client = Client("https://your-domain.com/sse")

async with client:
    tools = await client.list_tools()
    print("Available tools:", tools)
```

### cURL Testing

```bash
# Test SSE endpoint
curl -N -H "Accept: text/event-stream" \
  https://your-domain.com/sse

# Test health check
curl https://your-domain.com/health
```

## 📊 Monitoring and Health Checks

### Health Check Endpoints

- **Application**: `http://localhost:8000/sse` (returns SSE stream)
- **Load Balancer**: `http://localhost/health` (nginx health check)

### Docker Health Checks

Health checks are automatically configured:
```bash
# Check container health
docker-compose ps
```

### Logging

Logs are output to stdout/stderr and can be collected by Docker:

```bash
# View logs
docker-compose logs -f linkedin-mcp

# Export logs
docker-compose logs linkedin-mcp > app.log
```

## 🔄 Deployment Strategies

### Blue-Green Deployment

1. Run new version on different port:
   ```bash
   export MCP_SERVER_PORT=8001
   docker-compose up -d
   ```

2. Update nginx upstream
3. Gracefully shutdown old version

### Rolling Updates

Use Docker Swarm or Kubernetes for zero-downtime deployments.

## ❗ Troubleshooting

### Common Issues

1. **Port already in use**:
   ```bash
   netstat -tlnp | grep :8000
   docker-compose down
   ```

2. **SSL certificate issues**:
   - Check certificate paths in nginx.conf
   - Verify certificate validity
   - Test with self-signed certs first

3. **CORS issues**:
   - Verify nginx CORS headers
   - Check client request headers
   - Test with curl first

4. **Connection refused**:
   - Check if container is running
   - Verify port mapping
   - Check firewall rules

### Debug Mode

Enable debug logging:
```bash
export PRODUCTION_MODE=false
docker-compose up
```

## 📈 Scaling

### Horizontal Scaling

1. **Load balancer**: Use nginx, HAProxy, or cloud load balancer
2. **Multiple instances**: Scale Docker containers
3. **Database**: Consider external token storage for session persistence

### Vertical Scaling

Adjust Docker resource limits in `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      memory: 1G
      cpus: '1.0'
```

## 🔗 Integration Examples

### Claude Desktop Integration

Add to your MCP configuration:
```json
{
  "mcpServers": {
    "linkedin": {
      "url": "https://your-domain.com/sse",
      "transport": "sse"
    }
  }
}
```

### API Gateway Integration

Use with Kong, Traefik, or AWS API Gateway for additional features:
- Authentication
- Rate limiting
- Analytics
- Request transformation

## 📚 Additional Resources

- [FastMCP Documentation](https://gofastmcp.com/)
- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [LinkedIn API Documentation](https://docs.microsoft.com/en-us/linkedin/)
- [Docker Compose Reference](https://docs.docker.com/compose/)

---

For support or questions, refer to the main README.md or create an issue in the repository. 