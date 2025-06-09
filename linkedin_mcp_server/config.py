"""Configuration settings for LinkedIn MCP Server."""

import sys
import logging
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Set up logging
logger = logging.getLogger(__name__)


class LinkedInConfig(BaseSettings):
    """LinkedIn API configuration settings."""
    
    # LinkedIn API credentials
    client_id: str = Field(default="", env="CLIENT_ID")
    client_secret: str = Field(default="", env="CLIENT_SECRET")
    redirect_uri: str = Field(default="", env="REDIRECT_URI")
    
    # OAuth 2.0 settings
    authorization_base_url: str = "https://www.linkedin.com/oauth/v2/authorization"
    token_url: str = "https://www.linkedin.com/oauth/v2/accessToken"
    
    # API settings
    api_base_url: str = "https://api.linkedin.com/v2"
    
    # Default scopes for LinkedIn API
    # Following: https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow
    # IMPORTANT: Only these scopes are supported by LinkedIn's current API:
    # - "profile": Basic profile information (name, headline, etc.)
    # - "email": Email address access  
    # - "openid": Required for OpenID Connect flow (provides user ID)
    # - "w_member_social": Required for posting content
    default_scopes: List[str] = [
        "profile",        # Basic profile information 
        "email",          # Email address access
        "openid",         # Required for OpenID Connect flow
        "w_member_social" # Required for posting content
    ]
    
    # Supported LinkedIn scopes (for validation)
    supported_scopes: List[str] = [
        "profile",
        "email", 
        "openid",
        "w_member_social"
    ]
    
    # MCP Server settings
    server_name: str = Field(default="LinkedIn MCP Server", env="MCP_SERVER_NAME")
    server_version: str = Field(default="0.1.0", env="MCP_SERVER_VERSION")
    
    # Production settings
    production_mode: bool = Field(default=False, env="PRODUCTION_MODE")
    server_host: str = Field(default="0.0.0.0", env="MCP_SERVER_HOST")
    server_port: int = Field(default=8000, env="MCP_SERVER_PORT")
    transport_mode: str = Field(default="sse", env="MCP_TRANSPORT")
    
    def __init__(self, **data):
        # Manually handle environment variables that aren't being picked up
        import os
        if not data.get('server_host') and os.getenv('MCP_SERVER_HOST'):
            data['server_host'] = os.getenv('MCP_SERVER_HOST')
        if not data.get('server_port') and os.getenv('MCP_SERVER_PORT'):
            data['server_port'] = int(os.getenv('MCP_SERVER_PORT'))
        if not data.get('transport_mode') and os.getenv('MCP_TRANSPORT'):
            data['transport_mode'] = os.getenv('MCP_TRANSPORT')
        if not data.get('production_mode') and os.getenv('PRODUCTION_MODE'):
            data['production_mode'] = os.getenv('PRODUCTION_MODE').lower() in ('true', '1', 'yes', 'on')
        super().__init__(**data)
    
    model_config = SettingsConfigDict(
        env_file=[".env", "../.env"],  # Try multiple locations
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        env_prefix="",  # No prefix for environment variables
        env_ignore_empty=True  # Ignore empty env values
    )


def get_config() -> LinkedInConfig:
    """Get a fresh configuration instance that reads current environment variables."""
    # Always create a new instance to pick up environment changes
    config = LinkedInConfig()
    
    # Debug: Print what values were loaded (only if debug is needed)
    # Uncomment these lines if you need to debug configuration loading
    # print(f"Loaded config - Client ID: {'***' if config.client_id else 'NOT SET'}")
    # print(f"Loaded config - Client Secret: {'***' if config.client_secret else 'NOT SET'}")
    
    return config


def validate_config() -> bool:
    """Validate that all required configuration is present."""
    try:
        config = get_config()
        
        # Check required fields
        if not config.client_id:
            logger.error("CLIENT_ID is required but not set")
            return False
            
        if not config.client_secret:
            logger.error("CLIENT_SECRET is required but not set")
            return False
            
        logger.info("Configuration validation passed")
        return True
        
    except Exception as e:
        logger.error(f"Configuration validation failed: {e}")
        return False 