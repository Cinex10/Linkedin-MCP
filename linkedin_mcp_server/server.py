"""LinkedIn MCP Server implementation."""

import json
import logging
import signal
import sys
from typing import Dict, Any, Optional, List
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import webbrowser
import socket

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.prompts import base

from .config import get_config, validate_config
from .oauth import LinkedInOAuth, TokenManager
from .client import LinkedInAPIClient, LinkedInAPIError
from .callback_server import CallbackServerManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Global instances
oauth_handler = LinkedInOAuth()
token_manager = TokenManager()

# Note: CallbackServerManager is now a singleton, no global instance needed


def signal_handler(signum, frame):
    """Handle termination signals to ensure graceful shutdown."""
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    
    # Stop callback server if it's running
    if CallbackServerManager.is_running():
        try:
            logger.info("Stopping callback server due to signal...")
            CallbackServerManager.stop_server()
            logger.info("Callback server stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping callback server: {e}")
    
    sys.exit(0)


# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Termination signal


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """Manage server startup and shutdown lifecycle."""
    logger.info("Starting LinkedIn MCP Server...")
    
    # Get configuration (don't validate upfront - will validate when needed)
    config = get_config()
    logger.info(f"Server initialized: {config.server_name} v{config.server_version}")
    
    # Start callback server automatically
    try:
        logger.info("Starting callback server as part of MCP lifecycle...")
        CallbackServerManager.start_server(port=8080)
        logger.info(f"✅ Callback server started successfully on port 8080")
    except OSError as e:
        if e.errno == 48:  # Address already in use
            logger.warning(f"⚠️  Port 8080 is already in use. Callback server not started automatically.")
            logger.info("You can manually start the callback server on a different port if needed.")
        else:
            logger.error(f"❌ Failed to start callback server: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error starting callback server: {e}")
    
    try:
        yield {
            "oauth_handler": oauth_handler,
            "token_manager": token_manager,
            "config": config
        }
    finally:
        logger.info("Shutting down LinkedIn MCP Server...")
        
        # Stop callback server if it's running
        if CallbackServerManager.is_running():
            try:
                logger.info("Stopping callback server...")
                CallbackServerManager.stop_server()
                logger.info("✅ Callback server stopped successfully")
            except Exception as e:
                logger.error(f"❌ Error stopping callback server: {e}")
        
        logger.info("LinkedIn MCP Server shutdown complete")


# Initialize FastMCP server
config = get_config()
mcp = FastMCP(
    name=config.server_name,
    lifespan=server_lifespan
)

# Configure server settings for production
if config.production_mode:
    mcp.settings.host = config.server_host
    mcp.settings.port = config.server_port


@mcp.resource("linkedin://profile/{user_id}")
def get_profile_resource(user_id: str) -> str:
    """Get LinkedIn profile data as a resource."""
    try:
        access_token = token_manager.get_access_token(user_id)
        if not access_token:
            return f"No access token found for user {user_id}. Please authenticate first."
        
        client = LinkedInAPIClient(access_token)
        profile = client.get_profile()
        
        return json.dumps(profile, indent=2)
    except LinkedInAPIError as e:
        logger.error(f"LinkedIn API error: {e}")
        return f"Error fetching profile: {e}"
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return f"Unexpected error: {e}"


@mcp.resource("linkedin://connections/{user_id}")
def get_connections_resource(user_id: str) -> str:
    """Get LinkedIn connections data as a resource."""
    try:
        access_token = token_manager.get_access_token(user_id)
        if not access_token:
            return f"No access token found for user {user_id}. Please authenticate first."
        
        client = LinkedInAPIClient(access_token)
        connections = client.get_connections()
        
        return json.dumps(connections, indent=2)
    except LinkedInAPIError as e:
        logger.error(f"LinkedIn API error: {e}")
        return f"Error fetching connections: {e}"
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return f"Unexpected error: {e}"


@mcp.tool()
def authenticate_linkedin_oauth(scopes: Optional[List[str]] = None, timeout: int = 300, port: int = 8080, auto_open_browser: bool = True) -> Dict[str, Any]:
    """
    Complete LinkedIn OAuth 2.0 authentication flow in a single step.
    
    This tool handles the entire OAuth flow automatically:
    1. Uses the lifecycle-managed callback server
    2. Generates the authorization URL
    3. Optionally opens the URL in the default browser
    4. Waits for user to authorize in browser
    5. Captures the callback and exchanges code for token
    6. Returns the authenticated user information
    
    Note: Assumes the callback server is already running (started automatically by MCP lifecycle).
    
    Args:
        scopes: Optional list of OAuth scopes to request
        timeout: Maximum time to wait for user authorization (default: 5 minutes)
        port: Port preference (will use lifecycle-managed server port if different)
        auto_open_browser: Whether to automatically open the auth URL in browser (default: True)
        
    Returns:
        Dictionary with LinkedIn user information and authentication status
    """
    try:
        # Validate configuration
        if not validate_config():
            return {"error": "LinkedIn credentials not configured. Please set LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET, and LINKEDIN_REDIRECT_URI environment variables."}
        
        actual_port = port
        
        try:
            # Create a new session
            session_id = token_manager.create_session()
            
            # Generate auth URL with session_id as state
            auth_url = oauth_handler.get_authorization_url(scopes=scopes, state=session_id)
            
            print(f"\n{'='*60}")
            print("LinkedIn OAuth Authentication")
            print(f"{'='*60}")
            print(f"🔗 Authorization URL: {auth_url}")
            print(f"📡 Using callback server on port: {port}")
            
            # Automatically open browser if requested
            if auto_open_browser:
                try:
                    print(f"🌐 Opening authorization URL in your default browser...")
                    webbrowser.open(auth_url)
                    print(f"✅ Browser opened successfully!")
                except Exception as browser_error:
                    print(f"⚠️  Could not open browser automatically: {browser_error}")
                    print(f"📋 Please manually visit: {auth_url}")
            else:
                print(f"📋 Please visit this URL to authenticate with LinkedIn:")
                print(f"   {auth_url}")
            
            print(f"\n⏳ Waiting for authorization (timeout: {timeout} seconds)...")
            print(f"   Callback server running on: http://localhost:{port}")
            print(f"{'='*60}\n")
            
            # Wait for callback
            callback_url = CallbackServerManager.wait_for_callback(timeout)
            
            if not callback_url:
                return {
                    "error": "Authentication timeout. Please try again.",
                    "auth_url": auth_url,
                    "session_id": session_id,
                    "message": "Make sure you complete the authorization in your browser within the timeout period."
                }
            
            # Exchange authorization code for token
            token_data = oauth_handler.exchange_code_for_token(callback_url)
            
            # Get user info to obtain LinkedIn user ID
            access_token = token_data.get("access_token")
            if not access_token:
                return {"error": "Authentication completed but no access token received."}
            
            # Get LinkedIn user profile to extract user ID
            client = LinkedInAPIClient(access_token)
            user_info = client.get_user_info()
            
            # Extract LinkedIn user ID from OpenID Connect response
            linkedin_user_id = user_info.get("sub")  # OpenID Connect uses 'sub' for user ID
            if not linkedin_user_id:
                return {"error": "Could not retrieve LinkedIn user ID from profile."}
            
            # Store token with session mapping
            token_manager.store_token_with_session(session_id, token_data, linkedin_user_id)
            
            # Extract user name from OpenID Connect response
            name = user_info.get("name", "Unknown")
            if not name or name == "Unknown":
                # Try to construct from given_name and family_name
                given_name = user_info.get("given_name", "")
                family_name = user_info.get("family_name", "")
                if given_name or family_name:
                    name = f"{given_name} {family_name}".strip()
            
            print(f"✅ Successfully authenticated LinkedIn account for {name}!")
            
            return {
                "success": True,
                "linkedin_user_id": linkedin_user_id,
                "user_name": name,
                "session_id": session_id,
                "scopes_granted": scopes or oauth_handler.config.default_scopes,
                "auto_browser_opened": auto_open_browser,
                "callback_server_port": port,
                "message": f"🎉 Successfully authenticated LinkedIn account for {name}! Your LinkedIn User ID is: {linkedin_user_id}",
                "user_info": user_info
            }
            
        except ValueError as scope_error:
            # Handle scope validation errors specifically
            return {
                "error": "Invalid LinkedIn scopes provided",
                "details": str(scope_error),
                "supported_scopes": oauth_handler.config.supported_scopes,
                "default_scopes": oauth_handler.config.default_scopes,
                "suggestion": "Use only supported scopes: profile, email, openid, w_member_social"
            }
        except Exception as auth_error:
            return {"error": f"Error during authentication process: {auth_error}"}
            
    except Exception as e:
        logger.error(f"Error in OAuth flow: {e}")
        return {"error": f"Error during OAuth authentication: {e}"}


@mcp.tool()
def get_my_linkedin_user_id(session_id: str) -> Dict[str, Any]:
    """
    Get the LinkedIn user ID for a completed authentication session.
    
    Args:
        session_id: Session identifier from authenticate_linkedin_oauth
        
    Returns:
        Dictionary with LinkedIn user ID or error
    """
    try:
        linkedin_user_id = token_manager.get_user_id_from_session(session_id)
        if not linkedin_user_id:
            return {"error": f"No authenticated user found for session {session_id}. Please complete authentication first."}
        
        return {
            "linkedin_user_id": linkedin_user_id,
            "session_id": session_id
        }
    except Exception as e:
        logger.error(f"Error getting user ID: {e}")
        return {"error": f"Error getting user ID: {e}"}


@mcp.tool()
def get_linkedin_profile(user_id: str, fields: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Get LinkedIn profile information for the authenticated user.
    
    Args:
        user_id: Unique identifier for the user
        fields: Optional list of profile fields to retrieve
        
    Returns:
        Profile data dictionary
    """
    try:
        access_token = token_manager.get_access_token(user_id)
        if not access_token:
            return {"error": f"No access token found for user {user_id}. Please authenticate first."}
        
        client = LinkedInAPIClient(access_token)
        profile = client.get_profile(fields=fields)
        
        return profile
    except LinkedInAPIError as e:
        logger.error(f"LinkedIn API error: {e}")
        return {"error": f"LinkedIn API error: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": f"Unexpected error: {e}"}


@mcp.tool()
def get_linkedin_connections(user_id: str, start: int = 0, count: int = 50) -> Dict[str, Any]:
    """
    Get LinkedIn connections for the authenticated user.
    
    Args:
        user_id: Unique identifier for the user
        start: Start index for pagination
        count: Number of connections to retrieve (max 500)
        
    Returns:
        Connections data dictionary
    """
    try:
        access_token = token_manager.get_access_token(user_id)
        if not access_token:
            return {"error": f"No access token found for user {user_id}. Please authenticate first."}
        
        client = LinkedInAPIClient(access_token)
        connections = client.get_connections(start=start, count=count)
        
        return connections
    except LinkedInAPIError as e:
        logger.error(f"LinkedIn API error: {e}")
        return {"error": f"LinkedIn API error: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": f"Unexpected error: {e}"}


@mcp.tool()
def search_linkedin_people(user_id: str, keywords: str, start: int = 0, count: int = 10) -> Dict[str, Any]:
    """
    Search for people on LinkedIn.
    
    Args:
        user_id: Unique identifier for the user
        keywords: Search keywords
        start: Start index for pagination
        count: Number of results to retrieve
        
    Returns:
        Search results dictionary
    """
    try:
        access_token = token_manager.get_access_token(user_id)
        if not access_token:
            return {"error": f"No access token found for user {user_id}. Please authenticate first."}
        
        client = LinkedInAPIClient(access_token)
        results = client.search_people(keywords=keywords, start=start, count=count)
        
        return results
    except LinkedInAPIError as e:
        logger.error(f"LinkedIn API error: {e}")
        return {"error": f"LinkedIn API error: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": f"Unexpected error: {e}"}


@mcp.tool()
def share_linkedin_content(user_id: str, text: str, visibility: str = "PUBLIC") -> Dict[str, Any]:
    """
    Share content on LinkedIn.
    
    Args:
        user_id: Unique identifier for the user
        text: Content text to share
        visibility: Visibility setting (PUBLIC, CONNECTIONS)
        
    Returns:
        Share response data
    """
    try:
        access_token = token_manager.get_access_token(user_id)
        if not access_token:
            return {"error": f"No access token found for user {user_id}. Please authenticate first."}
        
        client = LinkedInAPIClient(access_token)
        result = client.share_content(text=text, visibility=visibility)
        
        return {"success": True, "message": "Content shared successfully", "data": result}
    except LinkedInAPIError as e:
        logger.error(f"LinkedIn API error: {e}")
        return {"error": f"LinkedIn API error: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": f"Unexpected error: {e}"}


@mcp.tool()
def post_to_linkedin(text: str, visibility: str = "PUBLIC") -> Dict[str, Any]:
    """
    Post content to LinkedIn using the most recently authenticated user.
    
    Note: LinkedIn's current API has limited posting capabilities.
    This tool may not work due to API restrictions. For posting content,
    you may need to use LinkedIn's web interface or apply for special API access.
    
    Args:
        text: Content text to share (required)
        visibility: Visibility setting - "PUBLIC" or "CONNECTIONS" (default: "PUBLIC")
        
    Returns:
        Dict containing success status and response data or error message
    """
    try:
        # Get all authenticated users and use the most recent one
        users_response = list_authenticated_users()
        
        if "error" in users_response:
            return {
                "error": "No authenticated users found. Please authenticate with LinkedIn first using authenticate_linkedin_oauth.",
                "suggestion": "Run authenticate_linkedin_oauth() to connect your LinkedIn account"
            }
        
        authenticated_users = users_response.get("authenticated_users", [])
        if not authenticated_users:
            return {
                "error": "No authenticated users found. Please authenticate with LinkedIn first.",
                "suggestion": "Run authenticate_linkedin_oauth() to connect your LinkedIn account"
            }
        
        # Use the first authenticated user (most recent)
        user = authenticated_users[0]
        user_id = user.get("linkedin_user_id")
        
        if not user_id:
            return {"error": "Could not determine user ID from authenticated users"}
        
        # Validate input
        if not text or not text.strip():
            return {"error": "Text content is required and cannot be empty"}
        
        if visibility not in ["PUBLIC", "CONNECTIONS"]:
            return {"error": "Visibility must be either 'PUBLIC' or 'CONNECTIONS'"}
        
        # Attempt to post content
        access_token = token_manager.get_access_token(user_id)
        if not access_token:
            return {"error": f"No access token found for user {user_id}. Please re-authenticate."}
        
        client = LinkedInAPIClient(access_token)
        result = client.share_content(text=text, visibility=visibility)
        
        return {
            "success": True, 
            "message": f"Content posted successfully to LinkedIn as {user.get('name', 'Unknown User')}", 
            "data": result,
            "user": {
                "name": user.get('name'),
                "email": user.get('email')
            }
        }
        
    except LinkedInAPIError as e:
        error_msg = str(e)
        
        # Check for common API limitation errors
        if "403" in error_msg or "Forbidden" in error_msg:
            return {
                "error": "LinkedIn API access forbidden. LinkedIn has restricted posting capabilities through their API.",
                "details": error_msg,
                "suggestion": "LinkedIn has restricted posting capabilities through their API. You may need to post content directly through LinkedIn's web interface or apply for special API access through LinkedIn's Partner Program."
            }
        elif "401" in error_msg or "Unauthorized" in error_msg:
            return {
                "error": "Authentication failed. Your LinkedIn access token may have expired.",
                "details": error_msg,
                "suggestion": "Please re-authenticate using authenticate_linkedin_oauth()"
            }
        else:
            return {
                "error": f"LinkedIn API error: {error_msg}",
                "suggestion": "Check the LinkedIn API documentation for current posting capabilities and requirements."
            }
            
    except Exception as e:
        logger.error(f"Unexpected error in post_to_linkedin: {e}")
        return {"error": f"Unexpected error: {e}"}


@mcp.tool()
def get_linkedin_activity_summary(user_id: str) -> Dict[str, Any]:
    """
    Get a comprehensive summary of LinkedIn activity and profile.
    
    Args:
        user_id: Unique identifier for the user
        
    Returns:
        Activity summary data
    """
    try:
        access_token = token_manager.get_access_token(user_id)
        if not access_token:
            return {"error": f"No access token found for user {user_id}. Please authenticate first."}
        
        client = LinkedInAPIClient(access_token)
        summary = client.get_activity_summary()
        
        return summary
    except LinkedInAPIError as e:
        logger.error(f"LinkedIn API error: {e}")
        return {"error": f"LinkedIn API error: {e}"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"error": f"Unexpected error: {e}"}


@mcp.tool()
def revoke_linkedin_auth(user_id: str) -> str:
    """
    Revoke LinkedIn authentication for a user.
    
    Args:
        user_id: Unique identifier for the user
        
    Returns:
        Success message
    """
    try:
        access_token = token_manager.get_access_token(user_id)
        if access_token:
            # Revoke the token (LinkedIn doesn't have a standard revoke endpoint)
            oauth_handler.revoke_token(access_token)
        
        # Remove token from storage
        token_manager.remove_token(user_id)
        
        return f"LinkedIn authentication revoked for user {user_id}"
    except Exception as e:
        logger.error(f"Error revoking authentication: {e}")
        return f"Error revoking authentication: {e}"

@mcp.tool()
def list_authenticated_users() -> Dict[str, Any]:
    """
    List all authenticated LinkedIn users.
    
    Returns:
        Dictionary with list of authenticated users and their basic info
    """
    try:
        authenticated_users = []
        
        # Get all stored tokens
        for linkedin_user_id in token_manager._tokens.keys():
            access_token = token_manager.get_access_token(linkedin_user_id)
            if access_token:
                try:
                    client = LinkedInAPIClient(access_token)
                    user_info = client.get_user_info()
                    
                    # Extract user name from OpenID Connect response
                    name = user_info.get("name", "Unknown")
                    if not name or name == "Unknown":
                        # Try to construct from given_name and family_name
                        given_name = user_info.get("given_name", "")
                        family_name = user_info.get("family_name", "")
                        if given_name or family_name:
                            name = f"{given_name} {family_name}".strip()
                    
                    authenticated_users.append({
                        "linkedin_user_id": linkedin_user_id,
                        "name": name,
                        "email": user_info.get("email", ""),
                        "picture": user_info.get("picture", "")
                    })
                except Exception as e:
                    # Token might be expired or invalid
                    authenticated_users.append({
                        "linkedin_user_id": linkedin_user_id,
                        "name": "Unknown (token may be expired)",
                        "error": str(e)
                    })
        
        return {
            "authenticated_users": authenticated_users,
            "count": len(authenticated_users)
        }
    except Exception as e:
        logger.error(f"Error listing authenticated users: {e}")
        return {"error": f"Error listing authenticated users: {e}"}


@mcp.prompt()
def linkedin_profile_summary(user_id: str) -> List[base.Message]:
    """Generate a prompt for LinkedIn profile analysis."""
    return [
        base.UserMessage("Please analyze my LinkedIn profile and provide insights on:"),
        base.UserMessage("1. Professional headline and summary effectiveness"),
        base.UserMessage("2. Skills and experience alignment"),
        base.UserMessage("3. Network connections and industry presence"),
        base.UserMessage("4. Suggestions for profile optimization"),
        base.AssistantMessage(f"I'll analyze the LinkedIn profile data for user {user_id}. Please use the get_linkedin_activity_summary tool to retrieve the profile information first."),
    ]


@mcp.prompt()
def linkedin_networking_strategy() -> List[base.Message]:
    """Generate a prompt for LinkedIn networking strategy."""
    return [
        base.UserMessage("Help me develop a LinkedIn networking strategy based on my current connections and industry."),
        base.UserMessage("Please provide:"),
        base.UserMessage("1. Analysis of my current network composition"),
        base.UserMessage("2. Identification of networking gaps"),
        base.UserMessage("3. Specific action items for network expansion"),
        base.UserMessage("4. Content sharing recommendations"),
        base.AssistantMessage("I'll help you develop a comprehensive LinkedIn networking strategy. First, let me gather information about your current profile and connections using the available LinkedIn tools."),
    ]


@mcp.prompt()
def linkedin_content_creation(content_topic: str = "professional insights") -> List[base.Message]:
    """Generate a prompt for creating engaging LinkedIn content."""
    return [
        base.UserMessage(f"Help me create engaging LinkedIn content about: {content_topic}"),
        base.UserMessage("Please help me develop:"),
        base.UserMessage("1. A compelling hook to grab attention"),
        base.UserMessage("2. Main content with valuable insights or story"),
        base.UserMessage("3. Call-to-action to encourage engagement"),
        base.UserMessage("4. Relevant hashtags for reach"),
        base.UserMessage("5. Optimal posting timing recommendations"),
        base.AssistantMessage("I'll help you create engaging LinkedIn content that resonates with your professional audience. Based on your profile and network, I'll suggest content that aligns with your industry and expertise."),
    ]


@mcp.prompt()
def linkedin_job_search_strategy(target_role: str = "your desired position") -> List[base.Message]:
    """Generate a prompt for LinkedIn job search strategy."""
    return [
        base.UserMessage(f"Help me develop a job search strategy on LinkedIn for: {target_role}"),
        base.UserMessage("Please provide guidance on:"),
        base.UserMessage("1. Optimizing my profile for recruiters"),
        base.UserMessage("2. Using LinkedIn's job search features effectively"),
        base.UserMessage("3. Networking with people in target companies"),
        base.UserMessage("4. Following up on applications"),
        base.UserMessage("5. Building relationships with recruiters"),
        base.AssistantMessage("I'll help you create a comprehensive LinkedIn job search strategy. Let me first analyze your current profile and suggest optimizations, then provide a step-by-step action plan."),
    ]


@mcp.prompt()
def linkedin_connection_outreach(target_person: str = "industry professional") -> List[base.Message]:
    """Generate a prompt for crafting LinkedIn connection messages."""
    return [
        base.UserMessage(f"Help me craft a compelling LinkedIn connection request message to: {target_person}"),
        base.UserMessage("Please help me create:"),
        base.UserMessage("1. A personalized opening that shows genuine interest"),
        base.UserMessage("2. Clear value proposition for connecting"),
        base.UserMessage("3. Professional but warm tone"),
        base.UserMessage("4. Specific call-to-action or follow-up plan"),
        base.UserMessage("5. Alternative approaches if they don't respond"),
        base.AssistantMessage("I'll help you craft effective LinkedIn outreach messages that build meaningful professional relationships. The key is personalization and providing clear value."),
    ]


@mcp.prompt()
def linkedin_professional_brand_audit() -> List[base.Message]:
    """Generate a prompt for comprehensive LinkedIn brand review."""
    return [
        base.UserMessage("Conduct a comprehensive audit of my LinkedIn professional brand and presence."),
        base.UserMessage("Please analyze and provide feedback on:"),
        base.UserMessage("1. Profile completeness and optimization"),
        base.UserMessage("2. Professional headline and summary effectiveness"),
        base.UserMessage("3. Experience descriptions and skill endorsements"),
        base.UserMessage("4. Network quality and industry relevance"),
        base.UserMessage("5. Content sharing and engagement patterns"),
        base.UserMessage("6. Overall brand consistency and messaging"),
        base.AssistantMessage("I'll conduct a thorough audit of your LinkedIn presence using the available tools to analyze your profile, connections, and activity. This will help identify areas for improvement and optimization."),
    ]


@mcp.prompt()
def linkedin_setup_guide() -> List[base.Message]:
    """Generate a prompt for LinkedIn MCP setup and getting started."""
    return [
        base.UserMessage("Guide me through setting up and using the LinkedIn MCP integration effectively."),
        base.UserMessage("Please help me understand:"),
        base.UserMessage("1. How to authenticate with LinkedIn using the single-tool authentication"),
        base.UserMessage("2. What data I can access and manage"),
        base.UserMessage("3. Best practices for using the available tools"),
        base.UserMessage("4. Privacy and security considerations"),
        base.UserMessage("5. Common use cases and workflows"),
        base.UserMessage(""),
        base.UserMessage("Authentication method:"),
        base.UserMessage("- authenticate_linkedin_oauth() - Single-step automatic authentication with browser opening"),
        base.AssistantMessage("I'll guide you through the LinkedIn MCP setup process step by step. First, let me check if you're already authenticated, then provide a complete walkthrough of the available features and how to use them effectively. The new single-tool authentication makes the process much simpler!"),
    ]


@mcp.prompt()
def linkedin_post_copywriter(
    topic: str = "your business topic", 
    personal_views: str = "your unique perspective and expertise on this topic",
    target_audience: str = "business owners, entrepreneurs, individuals who want to start their business"
) -> List[base.Message]:
    """Generate a professional LinkedIn copywriting prompt for creating engaging posts."""
    return [
        base.UserMessage("CONTEXT: You are a copywriter with strong LinkedIn copywriter skills and specialized in captivating people's attention with your skills."),
        base.UserMessage(""),
        base.UserMessage(f"ACTION: Create 2 iterations of LinkedIn post copy on the given topic that resonates with the target audience. Also give me Image idea. The intro should hook readers attention and encourage them to read the entire post by pushing their emotional buttons. Capture the reader's interest from different angles using unique approaches."),
        base.UserMessage(""),
        base.UserMessage(f"Topic: [{topic}]"),
        base.UserMessage(""),
        base.UserMessage(f"My Views on topic: [{personal_views}]"),
        base.UserMessage(""),
        base.UserMessage(f"Target audience: {target_audience}"),
        base.UserMessage(""),
        base.UserMessage("SPECIFICATIONS:"),
        base.UserMessage("— The copy should be extremely confident and creative."),
        base.UserMessage("— Use sentence fragments."),
        base.UserMessage("— Each copy should be less than 175 words in length."),
        base.UserMessage(""),
        base.UserMessage("EXAMPLES:"),
        base.UserMessage(""),
        base.UserMessage("Example 1:"),
        base.UserMessage("You only need 1 hour."),
        base.UserMessage("Build the business."),
        base.UserMessage("Study the skill."),
        base.UserMessage("Get in the gym."),
        base.UserMessage("Whatever your goals are, it should be obvious that one hour is more than enough time to achieve your goals."),
        base.UserMessage("People are busy."),
        base.UserMessage("Do you think every successful business just quit their job and made it work their first time around?"),
        base.UserMessage("Or were they just like you? Like most people are? Busy with jobs and responsibilities?"),
        base.UserMessage("99% of successful people start with one hour a day."),
        base.UserMessage("Not 12 hours like the business guru screams at you."),
        base.UserMessage("Realize this:"),
        base.UserMessage("365 hours is more than anyone has dedicated to most things in their life."),
        base.UserMessage("That's a lot of time."),
        base.UserMessage("1 hour a day for 365 days."),
        base.UserMessage("That's it."),
        base.UserMessage("Wake up an hour earlier or go to bed an hour later."),
        base.UserMessage("Set boundaries with loved ones so they know that you're spending time on a better future for yourself and them."),
        base.UserMessage("Commit."),
        base.UserMessage("Most people don't start businesses."),
        base.UserMessage("They start distractions."),
        base.UserMessage("They focus on everything except for building a product or service and getting customers."),
        base.UserMessage("If I were starting from scratch, here's exactly what I would do to avoid all the nonsense."),
        base.UserMessage("Read today's Koe Letter here:"),
        base.UserMessage("Graphic: A black background and \"Normalize disappearing for 1 hour a day to build a better future for yourself.\" Is written on the background with display serif font."),
        base.UserMessage(""),
        base.UserMessage("Example 2:"),
        base.UserMessage("From Overthinking to Overcoming"),
        base.UserMessage("I used to believe that only top-notch editing could make my videos successful."),
        base.UserMessage("This mindset almost stopped me from starting my YouTube channel."),
        base.UserMessage("But when I finally began creating raw and unedited content, I found that viewers value Authenticity and True Value over Perfection."),
        base.UserMessage("Today, I am so grateful for my audience who enjoys and supports my genuine content."),
        base.UserMessage("If I had waited for everything to be perfect, I might still be stuck in the planning phase."),
        base.UserMessage("Lesson learned: Start where you are, with what you have. Authenticity wins 💯"),
        base.UserMessage(""),
        base.UserMessage("CUSTOMIZATION GUIDE:"),
        base.UserMessage("Step 1: Replace 'Topic' with what you want to write about."),
        base.UserMessage("Step 2: Fill in 'My views on topic' with your expertise and insights—this ensures your LinkedIn posts reflect your unique perspective."),
        base.UserMessage("Step 3: For best results, include an example of your ideal post style."),
        base.AssistantMessage(f"I'll create 2 compelling LinkedIn post variations on '{topic}' using professional copywriting techniques. Each post will be under 175 words, use confident language with sentence fragments, and include hooks that grab attention from the first line. I'll also suggest visual ideas to complement each post."),
    ]


@mcp.tool()
def start_callback_server(port: int = 8080) -> Dict[str, Any]:
    """
    Start the OAuth callback server on the specified port.
    
    Note: The MCP server automatically starts a callback server on port 8080 during startup.
    This tool is mainly useful for starting a server on a different port or restarting if stopped.
    
    Args:
        port: Port number to run the callback server on (default: 8080)
        
    Returns:
        Dictionary with server status and details
    """
    try:
        # Check if already running
        if CallbackServerManager.is_running():
            current_port = CallbackServerManager.get_port()
            if current_port == port:
                return {
                    "success": True,
                    "message": f"✅ Callback server is already running on port {port}",
                    "port": port,
                    "status": "already_running",
                    "url": f"http://localhost:{port}"
                }
            else:
                return {
                    "error": f"Callback server is already running on port {current_port}, but you requested port {port}",
                    "current_port": current_port,
                    "requested_port": port,
                    "suggestion": f"Stop the current server first or use port {current_port}"
                }
        
        # Start new callback server
        CallbackServerManager.start_server(port)
        
        return {
            "success": True,
            "message": f"✅ Callback server started successfully on port {port}",
            "port": port,
            "status": "started",
            "url": f"http://localhost:{port}",
            "instructions": [
                f"The server is now listening for OAuth callbacks on http://localhost:{port}",
                "You can now use authenticate_linkedin_oauth() to complete the authentication flow"
            ]
        }
        
    except OSError as e:
        if e.errno == 48:  # Address already in use
            return {
                "error": f"Port {port} is already in use by another application",
                "suggestion": "Try a different port or stop the application using this port",
                "errno": e.errno
            }
        else:
            return {
                "error": f"Failed to start callback server: {e}",
                "errno": getattr(e, 'errno', None)
            }
    except Exception as e:
        logger.error(f"Error starting callback server: {e}")
        return {"error": f"Unexpected error starting callback server: {e}"}


@mcp.tool()
def stop_callback_server() -> Dict[str, Any]:
    """
    Stop the OAuth callback server.
    
    Note: The callback server will restart automatically when the MCP server restarts.
    
    Returns:
        Dictionary with stop status and details
    """
    if not CallbackServerManager.is_running():
        return {
            "message": "No callback server is currently running",
            "status": "not_running"
        }
    
    try:
        port = CallbackServerManager.get_port()
        CallbackServerManager.stop_server()
        
        return {
            "success": True,
            "message": f"✅ Callback server stopped successfully (was running on port {port})",
            "port": port,
            "status": "stopped",
            "note": "The server will restart automatically when the MCP server restarts."
        }
        
    except Exception as e:
        logger.error(f"Error stopping callback server: {e}")
        return {"error": f"Error stopping callback server: {e}"}


@mcp.tool()
def get_callback_server_status() -> Dict[str, Any]:
    """
    Get the status of the OAuth callback server.
    
    Returns:
        Dictionary with detailed server status and management information
    """
    try:
        is_running = CallbackServerManager.is_running()
        
        if not is_running:
            return {
                "status": "not_running",
                "message": "Callback server is not currently running",
                "note": "The MCP server automatically starts a callback server on port 8080 during startup"
            }
        
        port = CallbackServerManager.get_port()
        
        return {
            "status": "running",
            "port": port,
            "url": f"http://localhost:{port}",
            "is_running": True,
            "message": f"✅ Callback server is running on port {port}",
            "details": {
                "automatic_startup": "Enabled (starts with MCP server)",
                "automatic_shutdown": "Enabled (stops with MCP server)",
                "singleton_pattern": "Uses singleton CallbackServerManager for lifecycle management"
            }
        }
        
    except Exception as e:
        logger.error(f"Error checking callback server status: {e}")
        return {
            "status": "error",
            "error": f"Error checking server status: {e}"
        }


def get_server() -> FastMCP:
    """Get the FastMCP server instance."""
    return mcp 