# LinkedIn MCP Server

A Model Context Protocol (MCP) server that provides secure access to LinkedIn API with OAuth 2.0 authentication. This server allows AI assistants to interact with LinkedIn profiles, connections, and other professional data in a controlled and authenticated manner.

## Features

- 🔐 **OAuth 2.0 Authentication** - Secure LinkedIn API access with PKCE
- 👤 **Profile Management** - Access and manage LinkedIn profiles
- 🌐 **Network Analysis** - Retrieve and analyze connections
- 🔍 **People Search** - Search for professionals on LinkedIn
- 📝 **Content Sharing** - Post content to LinkedIn
- 📊 **Activity Summaries** - Get comprehensive LinkedIn activity reports
- 🛠️ **MCP Resources** - Expose LinkedIn data as MCP resources
- 💬 **Smart Prompts** - Pre-built prompts for LinkedIn analysis

## Prerequisites

- Python 3.10 or higher
- LinkedIn Developer Application
- `uv` package manager (recommended) or `pip`

## LinkedIn Developer Setup

1. Go to [LinkedIn Developer Portal](https://developer.linkedin.com/)
2. Create a new application or use an existing one
3. Configure OAuth 2.0 settings:
   - Add redirect URL: `http://localhost:8080/callback`
   - Request the necessary scopes:
     - `profile`
     - `email`
     - `openid` 
     - `w_member_social` 
4. Note your **Client ID** and **Client Secret**

## Installation

### Using uv (recommended)

```bash
# Clone the repository
git clone <repository-url>
cd linkedin-mcp

# Install with uv
uv sync

# Activate the virtual environment
source .venv/bin/activate  # On Unix/macOS
# or
.venv\Scripts\activate     # On Windows
```

### Using pip

```bash
# Clone the repository
git clone <repository-url>
cd linkedin-mcp

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Unix/macOS
# or
venv\Scripts\activate     # On Windows

# Install dependencies
pip install -e .
```

## Configuration

1. Copy the example environment file:
   ```bash
   cp example.env .env
   ```

2. Edit `.env` with your LinkedIn API credentials:
   ```bash
   LINKEDIN_CLIENT_ID=your_linkedin_client_id_here
   LINKEDIN_CLIENT_SECRET=your_linkedin_client_secret_here
   LINKEDIN_REDIRECT_URI=http://localhost:8080/callback
   ```

## Redirect URI Setup

The redirect URI is where LinkedIn sends users after they authorize your application. You have several options:

### Option 1: Built-in Callback Server (Recommended for Development)

The easiest way is to use the built-in callback server:

```python
# 1. Start the callback server
server_status = start_callback_server()  # Defaults to port 8080
print(server_status["callback_url"])  # http://localhost:8080/callback

# 2. Authenticate (server will automatically handle the callback)
auth_result = authenticate_linkedin()
# Visit the auth_url in your browser

# 3. After authorization, the callback server will display the full callback URL
# Copy it and use it to complete authentication
complete_result = complete_linkedin_auth(
    session_id=auth_result["session_id"],
    authorization_response="http://localhost:8080/callback?code=..."
)

# 4. Stop the server when done
stop_callback_server()
```

### Option 2: Manual Callback Handling

If you prefer to handle callbacks manually:

```bash
# Run the standalone callback server
python -m linkedin_mcp_server.callback_server
```

This will start a server on `http://localhost:8080` that:
- Shows a success page after authorization
- Displays the full callback URL to copy
- Handles errors gracefully

### Option 3: Custom Redirect URI

You can use any redirect URI by:

1. **Update your `.env` file:**
   ```bash
   LINKEDIN_REDIRECT_URI=https://your-domain.com/callback
   ```

2. **Configure the same URI in LinkedIn Developer Console:**
   - Go to https://developer.linkedin.com/
   - Select your app
   - Add the redirect URI to "Authorized redirect URLs"

3. **Handle the callback yourself** at that URL

### LinkedIn Developer Console Setup

**Important:** Your redirect URI must be registered in LinkedIn Developer Console:

1. Go to https://developer.linkedin.com/
2. Select your LinkedIn app
3. Go to "Auth" tab
4. Add your redirect URI to "Authorized redirect URLs for your app"
5. Save changes

**Common redirect URIs:**
- Development: `http://localhost:8080/callback`
- Production: `https://yourdomain.com/auth/linkedin/callback`
- Mobile: `your-app://auth/callback`

### Troubleshooting Redirect URI Issues

**Error: "redirect_uri_mismatch"**
- The redirect URI in your request doesn't match what's registered in LinkedIn Developer Console
- Check that the URI matches exactly (including protocol, port, and path)

**Error: "invalid_redirect_uri"**
- The redirect URI format is invalid
- Must be a valid HTTP/HTTPS URL
- Cannot contain fragments (#) or certain special characters

**Port already in use:**
```python
# Use a different port
start_callback_server(port=8081)
```

### Current Configuration

Your current redirect URI is set to: `http://localhost:8080/callback`

To change it, update the `LINKEDIN_REDIRECT_URI` in your `.env` file.

## Supported LinkedIn Scopes

**✅ SUPPORTED SCOPES:**
- `profile` - Basic profile information (name, headline, etc.)
- `email` - Email address access
- `openid` - Required for OpenID Connect flow (provides user ID)
- `w_member_social` - scope for posting

The LinkedIn MCP automatically validates scopes and will reject unsupported ones with helpful error messages.

## Single-Tool Authentication

```python
# The MCP server automatically starts a singleton callback server during startup
# Simply use authenticate_linkedin_oauth() - no server management needed!

# Complete OAuth flow in one step with automatic browser opening
result = authenticate_linkedin_oauth()
# This will:
# 1. Use the automatically started singleton callback server
# 2. Generate the authorization URL
# 3. Automatically open the URL in your default browser
# 4. Wait for user to authorize in the opened browser tab
# 5. Capture callback and exchange for token
# 6. Return authenticated user information

# Returns: {
#   "success": True,
#   "linkedin_user_id": "dXJuOmxpOnBlcnNvbjpBQkNERUY...",
#   "user_name": "John Doe",
#   "session_id": "abc123...",
#   "auto_browser_opened": True,
#   "callback_server_port": 8080,
#   "message": "🎉 Successfully authenticated...",
#   "user_info": {...}
# }
```

**Parameters:**
- `scopes` (optional): List of OAuth scopes to request
- `timeout` (optional): Max wait time in seconds (default: 300)
- `port` (optional): Port preference (will use actual server port)
- `auto_open_browser` (optional): Auto-open browser (default: True)

**Automatic Server Management:** The MCP server automatically starts a singleton callback server during startup and stops it during shutdown. The callback server uses a singleton pattern for efficient lifecycle management.

**Manual Server Management (Optional):**

```python
# Check server status
status = get_callback_server_status()

# Start server on different port (if needed)
start_callback_server(port=8081)

# Stop server manually (will restart automatically with MCP server)
stop_callback_server()
```

**Browser Opening Options:**

```python
# Auto-open browser (default - recommended)
result = authenticate_linkedin_oauth()

# Manual browser opening (display URL only)
result = authenticate_linkedin_oauth(auto_open_browser=False)

# Custom configuration
result = authenticate_linkedin_oauth(
    scopes=['profile', 'email', 'openid', 'w_member_social'],  # Only use supported scopes
    timeout=180,  # 3 minutes
    auto_open_browser=True
)
```

### Helper Tools

```python
# Get your LinkedIn user ID from a session
user_info = get_my_linkedin_user_id(session_id="abc123...")

# List all authenticated users
users = list_authenticated_users()
```

### Posting Content to LinkedIn

**⚠️ Important Note**: LinkedIn's current API has limited posting capabilities. The posting tools are included for completeness but may not work due to these API restrictions.

**Simple Posting (Recommended):**

```python
# Post content using the most recently authenticated user
result = post_to_linkedin("Hello LinkedIn! This is a test post.")

# Post with specific visibility
result = post_to_linkedin(
    text="This post is only visible to my connections",
    visibility="CONNECTIONS"  # or "PUBLIC"
)
```

**Advanced Posting (Requires User ID):**

```python
# Get user ID first
users = list_authenticated_users()
user_id = users["authenticated_users"][0]["linkedin_user_id"]

# Post content
result = share_linkedin_content(
    user_id=user_id,
    text="Hello LinkedIn!",
    visibility="PUBLIC"
)
```

**Expected Limitations:**

Due to LinkedIn's API restrictions, you may encounter:
- `403 Forbidden` errors for posting operations
- Messages about API limitations
- Suggestions to use LinkedIn's web interface instead

**Alternative Solutions:**
- Use LinkedIn's web interface for posting
- Apply for LinkedIn's Partner Program for special API access
- Use LinkedIn's Campaign Manager for business content

### Running the Server

```bash
# Using the installed script
linkedin-mcp-server

# Or directly with Python
python -m linkedin_mcp_server.main

# Or using uv
uv run linkedin-mcp-server
```

### Testing with MCP Inspector

```bash
# Install MCP Inspector (if not already installed)
npm install -g @modelcontextprotocol/inspector

# Test the server
mcp dev linkedin_mcp_server/main.py
```

### Available Tools

The server provides the following MCP tools:

1. **`authenticate_linkedin_oauth`** - Complete OAuth authentication in one step with auto-browser opening
2. **`get_my_linkedin_user_id`** - Get LinkedIn user ID from session
3. **`get_linkedin_profile`** - Retrieve user profile information
4. **`get_linkedin_connections`** - Get user's LinkedIn connections
5. **`search_linkedin_people`** - Search for people on LinkedIn
6. **`share_linkedin_content`** - Post content to LinkedIn (requires user_id)
7. **`post_to_linkedin`** - Simplified posting tool (uses most recent authenticated user)
8. **`get_linkedin_activity_summary`** - Get comprehensive activity summary
9. **`revoke_linkedin_auth`** - Revoke authentication tokens
10. **`list_authenticated_users`** - List all currently authenticated users
11. **`start_callback_server`** - Start OAuth callback server (used internally)
12. **`stop_callback_server`** - Stop OAuth callback server
13. **`get_callback_server_status`** - Check callback server status

### Available Resources

The server exposes LinkedIn data as MCP resources:

- **`linkedin://profile/{user_id}`** - User profile data
- **`linkedin://connections/{user_id}`** - User connections data

### Available Prompts

Pre-built prompts for common LinkedIn analysis tasks:

- **`linkedin_profile_summary`** - Analyze LinkedIn profile effectiveness
- **`linkedin_networking_strategy`** - Develop networking strategies

## Security Features

- **PKCE (Proof Key for Code Exchange)** - Enhanced OAuth security
- **Token Management** - Secure token storage and validation
- **Scope-based Permissions** - Request only necessary permissions
- **Request Timeout** - Prevent hanging requests
- **Error Handling** - Comprehensive error handling and logging

## API Rate Limits

LinkedIn API has rate limits. The server handles:
- Automatic error detection for rate limit exceeded (429 status)
- Proper error messages for quota issues
- Connection limits (max 500 connections per request)

## Development

### Running Tests

```bash
# With uv
uv run pytest

# With pip
pytest
```

### Code Formatting

```bash
# Format code
uv run black linkedin_mcp_server/
uv run ruff check linkedin_mcp_server/

# Type checking
uv run mypy linkedin_mcp_server/
```

## Troubleshooting

### Common Issues

1. **"Configuration validation failed"**
   - Check that `LINKEDIN_CLIENT_ID` and `LINKEDIN_CLIENT_SECRET` are set
   - Verify the values are correct from LinkedIn Developer Portal

2. **"Error during authentication process"**
   - Check that the MCP server started successfully and the callback server is running
   - Verify the MCP server startup logs for any callback server errors
   - Try restarting the MCP server if the callback server failed to start

3. **"Authentication timeout"**
   - Increase the timeout parameter in `authenticate_linkedin_oauth()`
   - Check your internet connection
   - Ensure you complete the authorization in the browser within the timeout period

4. **"Unauthorized - access token may be expired"**
   - Re-authenticate the user using the authentication flow
   - Check if the LinkedIn app has the required permissions

5. **"Rate limit exceeded"**
   - Wait before making more requests
   - Consider implementing exponential backoff

6. **"LinkedIn API access forbidden" (Posting Issues)**
   - LinkedIn has restricted posting capabilities through their API
   - This is a known limitation of LinkedIn's current API
   - Use LinkedIn's web interface for posting content
   - Consider applying for LinkedIn's Partner Program for special API access

7. **"Could not open browser automatically"**
   - The system couldn't open the default browser
   - Use `auto_open_browser=False` and manually open the displayed URL
   - Check if you have a default browser configured

8. **Browser opens but shows "This site can't be reached"**
   - Check if the callback server is running with `get_callback_server_status()`
   - Verify the MCP server started successfully
   - Check MCP server logs for callback server startup issues
   - Try manually starting a callback server: `start_callback_server(port=8081)`

### Debug Logging

Enable debug logging by setting the log level:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For issues and questions:
1. Check the [troubleshooting section](#troubleshooting)
2. Open an issue on GitHub
3. Consult the [LinkedIn API documentation](https://docs.microsoft.com/en-us/linkedin/)

## Disclaimer

This is an unofficial LinkedIn API client. Make sure to comply with LinkedIn's API Terms of Service and usage policies. 