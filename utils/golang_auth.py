"""
Golang API Authentication Utility
Handles authentication with the Golang management and execution services.
"""

import os
import requests
import json
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class GolangAPIAuth:
    """Handles authentication with Golang API services"""
    
    def __init__(self, base_url: str = None):
        """
        Initialize the authentication handler
        
        Args:
            base_url: Base URL for the API service. If None, uses GOLANG_MGMT_API_URL from env
        """
        self.base_url = base_url or os.getenv('GOLANG_MGMT_API_URL', 'http://localhost:8083')
        self.username = os.getenv('GOLANG_API_USERNAME', '')
        self.password = os.getenv('GOLANG_API_PASSWORD', '')
        self.token = None
        
    def authenticate(self) -> bool:
        """
        Authenticate with Golang API and store token
        
        Returns:
            bool: True if authentication successful, False otherwise
        """
        try:
            auth_data = {
                "username": self.username,
                "password": self.password
            }
            
            print(f"🔐 Authenticating with: {self.base_url}/api/v1/auth/login")
            print(f"🔐 Auth data: {auth_data}")
            
            response = requests.post(
                f"{self.base_url}/api/v1/auth/login",
                json=auth_data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            print(f"🔐 Response Status: {response.status_code}")
            print(f"🔐 Response Headers: {dict(response.headers)}")
            print(f"🔐 Response Text: {response.text}")
            
            if response.status_code == 200:
                try:
                    auth_response = response.json()
                    self.token = auth_response.get("access_token")
                    print(f"✅ Successfully authenticated with Golang API")
                    print(f"✅ Token: {self.token[:20] if self.token else 'None'}...")
                    return True
                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
                    return False
            else:
                print(f"❌ Authentication failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error authenticating with Golang API: {str(e)}")
            return False
    
    def get_auth_headers(self) -> Dict[str, str]:
        """
        Get authentication headers for API requests
        
        Returns:
            Dict[str, str]: Headers with authorization token
        """
        if not self.token:
            if not self.authenticate():
                raise Exception("Failed to authenticate with Golang API")
        
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }
    
    def make_authenticated_request(self, method: str, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Make an authenticated request to the Golang API
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint (e.g., '/api/v1/execute/paper/orders')
            data: Request data for POST/PUT requests
            
        Returns:
            Dict[str, Any]: Response data or None if failed
        """
        try:
            headers = self.get_auth_headers()
            url = f"{self.base_url}{endpoint}"
            
            print(f"🌐 Making {method} request to: {url}")
            if data:
                print(f"📤 Request data: {data}")
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, timeout=10)
            elif method.upper() == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=10)
            elif method.upper() == 'PUT':
                response = requests.put(url, json=data, headers=headers, timeout=10)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=10)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            print(f"📥 Response Status: {response.status_code}")
            print(f"📥 Response Text: {response.text}")
            
            if response.status_code in [200, 201]:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    print("⚠️ Response is not valid JSON")
                    return {"success": True, "message": "Request successful"}
            else:
                print(f"❌ Request failed: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Error making authenticated request: {str(e)}")
            return None


# Global instance for easy access
_global_auth_instance = None

def get_golang_auth(base_url: str = None) -> GolangAPIAuth:
    """
    Get a global instance of GolangAPIAuth
    
    Args:
        base_url: Base URL for the API service
        
    Returns:
        GolangAPIAuth: Authentication instance
    """
    global _global_auth_instance
    if _global_auth_instance is None or (base_url and _global_auth_instance.base_url != base_url):
        _global_auth_instance = GolangAPIAuth(base_url)
    return _global_auth_instance


def authenticate_golang_api(base_url: str = None) -> bool:
    """
    Convenience function to authenticate with Golang API
    
    Args:
        base_url: Base URL for the API service
        
    Returns:
        bool: True if authentication successful
    """
    auth = get_golang_auth(base_url)
    return auth.authenticate()


def make_golang_api_call(method: str, endpoint: str, data: Optional[Dict[str, Any]] = None, base_url: str = None) -> Optional[Dict[str, Any]]:
    """
    Convenience function to make authenticated API calls
    
    Args:
        method: HTTP method
        endpoint: API endpoint
        data: Request data
        base_url: Base URL for the API service
        
    Returns:
        Dict[str, Any]: Response data or None if failed
    """
    auth = get_golang_auth(base_url)
    return auth.make_authenticated_request(method, endpoint, data)