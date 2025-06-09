"""LinkedIn API client for making authenticated requests."""

from typing import Dict, Any, Optional, List
import requests
from datetime import datetime, timezone

from .config import get_config


class LinkedInAPIError(Exception):
    """Exception raised when LinkedIn API returns an error."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class LinkedInAPIClient:
    """Client for making authenticated requests to LinkedIn API."""
    
    def __init__(self, access_token: str):
        """
        Initialize the LinkedIn API client.
        
        Args:
            access_token: OAuth 2.0 access token for authentication
        """
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        })
    
    @property
    def config(self):
        """Get fresh configuration on each access."""
        return get_config()
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        Make an authenticated request to the LinkedIn API.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            **kwargs: Additional arguments for requests
            
        Returns:
            JSON response data
            
        Raises:
            LinkedInAPIError: If the API request fails
        """
        url = f"{self.config.api_base_url}{endpoint}"
        
        try:
            response = self.session.request(method, url, timeout=30, **kwargs)
            
            # Handle different response codes
            if response.status_code == 401:
                raise LinkedInAPIError("Unauthorized - access token may be expired", 401)
            elif response.status_code == 403:
                raise LinkedInAPIError("Forbidden - insufficient permissions", 403)
            elif response.status_code == 429:
                raise LinkedInAPIError("Rate limit exceeded", 429)
            elif not response.ok:
                error_data = None
                try:
                    error_data = response.json()
                except Exception:
                    pass
                raise LinkedInAPIError(
                    f"API request failed with status {response.status_code}",
                    response.status_code,
                    error_data
                )
            
            return response.json() if response.content else {}
            
        except requests.exceptions.RequestException as e:
            raise LinkedInAPIError(f"Request failed: {str(e)}")
    
    def get_profile(self, fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get the authenticated user's LinkedIn profile using OpenID Connect.
        
        Args:
            fields: List of profile fields to retrieve (ignored for OpenID Connect)
            
        Returns:
            Profile data dictionary
        """
        endpoint = "/userinfo"
        
        # OpenID Connect userinfo endpoint doesn't use field projection
        # It returns standard OpenID Connect claims
        return self._make_request("GET", endpoint)
    
    def get_email_address(self) -> Dict[str, Any]:
        """
        Get the authenticated user's email address.
        
        Returns:
            Email address data
        """
        endpoint = "/emailAddress"
        params = {"q": "members", "projection": "(elements*(handle~))"}
        return self._make_request("GET", endpoint, params=params)
    
    def get_connections(self, start: int = 0, count: int = 50) -> Dict[str, Any]:
        """
        Get the authenticated user's 1st degree connections.
        
        Args:
            start: Start index for pagination
            count: Number of connections to retrieve (max 500)
            
        Returns:
            Connections data
        """
        endpoint = "/connections"
        params = {
            "q": "viewer",
            "start": start,
            "count": min(count, 500)  # LinkedIn limits to 500
        }
        return self._make_request("GET", endpoint, params=params)
    
    def search_people(self, keywords: str, start: int = 0, count: int = 10) -> Dict[str, Any]:
        """
        Search for people on LinkedIn.
        
        Args:
            keywords: Search keywords
            start: Start index for pagination  
            count: Number of results to retrieve
            
        Returns:
            Search results
        """
        endpoint = "/people"
        params = {
            "q": "search",
            "keywords": keywords,
            "start": start,
            "count": count
        }
        return self._make_request("GET", endpoint, params=params)
    
    def get_organizations(self, start: int = 0, count: int = 50) -> Dict[str, Any]:
        """
        Get organizations that the authenticated user is an admin of.
        
        Args:
            start: Start index for pagination
            count: Number of organizations to retrieve
            
        Returns:
            Organizations data
        """
        endpoint = "/organizationAcls"
        params = {
            "q": "roleAssignee",
            "start": start,
            "count": count,
            "projection": "(elements*(organization~(id,name,vanityName)))"
        }
        return self._make_request("GET", endpoint, params=params)
    
    def share_content(self, text: str, visibility: str = "PUBLIC") -> Dict[str, Any]:
        """
        Share content on LinkedIn.
        
        Args:
            text: Content text to share
            visibility: Visibility setting (PUBLIC, CONNECTIONS)
            
        Returns:
            Share response data
        """
        endpoint = "/ugcPosts"
        
        # Get user profile to get the author URN
        profile = self.get_profile()
        # OpenID Connect userinfo returns user ID in 'sub' field
        user_id = profile.get('sub')
        if not user_id:
            raise LinkedInAPIError("Unable to get user ID from profile")
        
        author_urn = f"urn:li:person:{user_id}"
        
        payload = {
            "author": author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": visibility
            }
        }
        
        return self._make_request("POST", endpoint, json=payload)
    
    def get_user_info(self) -> Dict[str, Any]:
        """
        Get comprehensive user information using OpenID Connect userinfo endpoint.
        
        Returns:
            User information including profile and email
        """
        try:
            # OpenID Connect userinfo endpoint returns both profile and email data
            user_info = self.get_profile()
            
            # The userinfo endpoint already includes email if the email scope was granted
            # No need for separate email API call
            
            return user_info
            
        except Exception as e:
            raise LinkedInAPIError(f"Failed to get user info: {str(e)}")
    
    def get_activity_summary(self) -> Dict[str, Any]:
        """
        Get a summary of user's LinkedIn activity.
        
        Returns:
            Activity summary data
        """
        try:
            summary = {
                "profile": self.get_profile(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "connections_available": False,
                "organizations_available": False
            }
            
            # Try to get connections count
            try:
                connections = self.get_connections(count=1)
                if "paging" in connections:
                    summary["connections_count"] = connections["paging"].get("total", 0)
                    summary["connections_available"] = True
            except Exception:
                pass
            
            # Try to get organizations
            try:
                orgs = self.get_organizations(count=1)
                if "elements" in orgs:
                    summary["organizations_count"] = len(orgs["elements"])
                    summary["organizations_available"] = True
            except Exception:
                pass
            
            return summary
            
        except Exception as e:
            raise LinkedInAPIError(f"Failed to get activity summary: {str(e)}") 