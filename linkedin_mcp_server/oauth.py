"""OAuth 2.0 authentication for LinkedIn API."""

import secrets
import os
from typing import Optional, Dict, Any, List
from urllib.parse import urlencode, parse_qs, urlparse

import requests
from requests_oauthlib import OAuth2Session

from .config import get_config

# Allow insecure transport for localhost development
# This is safe for development but should not be used in production
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

class LinkedInOAuth:
    """LinkedIn OAuth 2.0 authentication handler following official LinkedIn documentation."""
    
    def __init__(self):
        """Initialize the OAuth handler."""
        self.oauth_session: Optional[OAuth2Session] = None
        
    @property
    def config(self):
        """Get fresh configuration on each access."""
        return get_config()
    
    def get_authorization_url(self, scopes: Optional[List[str]] = None, state: Optional[str] = None) -> str:
        """
        Generate the authorization URL for LinkedIn OAuth 2.0.
        
        Following: https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow
        
        Args:
            scopes: List of OAuth scopes to request
            state: Optional state parameter for CSRF protection
            
        Returns:
            Authorization URL string
            
        Raises:
            ValueError: If unsupported scopes are provided
        """
        if scopes is None:
            scopes = self.config.default_scopes
        
        # Validate scopes
        self._validate_scopes(scopes)
            
        if state is None:
            state = secrets.token_urlsafe(32)
        
        # Create OAuth2 session - NO PKCE for LinkedIn
        self.oauth_session = OAuth2Session(
            client_id=self.config.client_id,
            redirect_uri=self.config.redirect_uri,
            scope=scopes
        )
        
        # Generate authorization URL following LinkedIn's spec
        authorization_url, state = self.oauth_session.authorization_url(
            self.config.authorization_base_url,
            state=state
        )
        
        return authorization_url
    
    def _validate_scopes(self, scopes: List[str]) -> None:
        """
        Validate that all requested scopes are supported by LinkedIn.
        
        Args:
            scopes: List of scopes to validate
            
        Raises:
            ValueError: If any unsupported scopes are found
        """
        supported_scopes = set(self.config.supported_scopes)
        requested_scopes = set(scopes)
        
        unsupported_scopes = requested_scopes - supported_scopes
        
        if unsupported_scopes:
            unsupported_list = list(unsupported_scopes)
            supported_list = list(supported_scopes)
            
            error_msg = f"""
Unsupported LinkedIn scopes detected: {unsupported_list}

Supported scopes are: {supported_list}

Please update your scopes to use only the supported ones.
            """.strip()
            
            raise ValueError(error_msg)
    
    def exchange_code_for_token(self, authorization_response: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token.
        
        Following LinkedIn's exact specification:
        POST https://www.linkedin.com/oauth/v2/accessToken
        Content-Type: application/x-www-form-urlencoded
        
        Args:
            authorization_response: The full callback URL with code parameter
            
        Returns:
            Token dictionary containing access_token, expires_in, etc.
        """
        # Parse the authorization response to get the code
        parsed_url = urlparse(authorization_response)
        query_params = parse_qs(parsed_url.query)
        
        if 'code' not in query_params:
            raise ValueError("Authorization code not found in response")
        
        auth_code = query_params['code'][0]
        
        # Prepare the token exchange request exactly as LinkedIn expects
        token_data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'client_id': self.config.client_id,
            'client_secret': self.config.client_secret,
            'redirect_uri': self.config.redirect_uri
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        # Make the token exchange request
        response = requests.post(
            self.config.token_url,
            data=token_data,
            headers=headers,
            timeout=30
        )
        
        if response.status_code != 200:
            error_detail = f"Status: {response.status_code}, Response: {response.text}"
            raise Exception(f"Token exchange failed: {error_detail}")
        
        token_response = response.json()
        return token_response
    
    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an expired access token.
        
        Note: LinkedIn typically uses re-authorization rather than refresh tokens.
        
        Args:
            refresh_token: The refresh token
            
        Returns:
            New token dictionary
        """
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post(self.config.token_url, data=data, headers=headers)
        response.raise_for_status()
        
        return response.json()
    
    def revoke_token(self, token: str) -> bool:
        """
        Revoke an access token.
        
        Args:
            token: The access token to revoke
            
        Returns:
            True if successful, False otherwise
        """
        # LinkedIn doesn't have a standard revoke endpoint
        # Tokens expire automatically, so we just return True
        return True
    
    def validate_token(self, access_token: str) -> bool:
        """
        Validate an access token by making a test API call.
        
        Args:
            access_token: The access token to validate
            
        Returns:
            True if token is valid, False otherwise
        """
        try:
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(
                f"{self.config.api_base_url}/userinfo",
                headers=headers,
                timeout=10
            )
            return response.status_code == 200
        except Exception:
            return False


class TokenManager:
    """Manages OAuth tokens for the LinkedIn API."""
    
    def __init__(self):
        """Initialize the token manager."""
        self._tokens: Dict[str, Dict[str, Any]] = {}
        self._session_to_user: Dict[str, str] = {}  # Maps session_id to linkedin_user_id
        self._user_to_session: Dict[str, str] = {}  # Maps linkedin_user_id to session_id
    
    def create_session(self) -> str:
        """
        Create a new authentication session.
        
        Returns:
            Unique session ID
        """
        session_id = secrets.token_urlsafe(32)
        return session_id
    
    def store_token_with_session(self, session_id: str, token_data: Dict[str, Any], linkedin_user_id: str) -> None:
        """
        Store token data for a session and map it to LinkedIn user ID.
        
        Args:
            session_id: Unique session identifier
            token_data: Token data from OAuth flow
            linkedin_user_id: LinkedIn user ID obtained from profile
        """
        self._tokens[linkedin_user_id] = token_data
        self._session_to_user[session_id] = linkedin_user_id
        self._user_to_session[linkedin_user_id] = session_id
    
    def get_user_id_from_session(self, session_id: str) -> Optional[str]:
        """
        Get LinkedIn user ID from session ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            LinkedIn user ID if found, None otherwise
        """
        return self._session_to_user.get(session_id)
    
    def store_token(self, user_id: str, token_data: Dict[str, Any]) -> None:
        """
        Store token data for a user.
        
        Args:
            user_id: LinkedIn user identifier
            token_data: Token data from OAuth flow
        """
        self._tokens[user_id] = token_data
    
    def get_token(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get stored token data for a user.
        
        Args:
            user_id: LinkedIn user identifier
            
        Returns:
            Token data if found, None otherwise
        """
        return self._tokens.get(user_id)
    
    def remove_token(self, user_id: str) -> bool:
        """
        Remove stored token data for a user.
        
        Args:
            user_id: LinkedIn user identifier
            
        Returns:
            True if token was removed, False if not found
        """
        if user_id in self._tokens:
            del self._tokens[user_id]
            # Clean up session mappings
            session_id = self._user_to_session.get(user_id)
            if session_id:
                del self._user_to_session[user_id]
                del self._session_to_user[session_id]
            return True
        return False
    
    def get_access_token(self, user_id: str) -> Optional[str]:
        """
        Get the access token for a user.
        
        Args:
            user_id: LinkedIn user identifier
            
        Returns:
            Access token if found, None otherwise
        """
        token_data = self.get_token(user_id)
        if token_data:
            return token_data.get("access_token")
        return None 