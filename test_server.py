#!/usr/bin/env python3
"""
Simple test to check if the Golang server is running
"""

import requests
import json

def test_health():
    """Test health endpoint"""
    try:
        response = requests.get("http://localhost:8083/health", timeout=5)
        print(f"Health Status: {response.status_code}")
        print(f"Health Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health Check Error: {e}")
        return False

def test_register():
    """Test register endpoint"""
    try:
        data = {
            "username": "testuser",
            "email": "testuser@example.com",
            "password": "testpass123",
            "role_id": 3
        }
        response = requests.post(
            "http://localhost:8083/api/v1/auth/register",
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"Register Status: {response.status_code}")
        print(f"Register Response: {response.text}")
        return response.status_code in [201, 409]  # 201 = created, 409 = conflict (already exists)
    except Exception as e:
        print(f"Register Error: {e}")
        return False

def test_login():
    """Test login endpoint"""
    try:
        data = {
            "username": "dattest@the20.vn",
            "password": "Fin20admin@1234"
        }
        response = requests.post(
            "http://localhost:8083/api/v1/auth/login",
            json=data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"Login Status: {response.status_code}")
        print(f"Login Response: {response.text}")
        
        if response.status_code == 200:
            try:
                response_data = response.json()
                token = response_data.get("access_token")
                print(f"Token: {token[:20] if token else 'None'}...")
                return token
            except:
                print("Cannot parse JSON response")
                return None
        return None
    except Exception as e:
        print(f"Login Error: {e}")
        return None

def main():
    print("=== Testing Golang API Server ===")
    
    print("\n1. Testing Health Endpoint...")
    if test_health():
        print("✅ Health endpoint is working")
    else:
        print("❌ Health endpoint failed")
        return
    
    print("\n2. Testing Register Endpoint...")
    if test_register():
        print("✅ Register endpoint is working")
    else:
        print("❌ Register endpoint failed")
    
    print("\n3. Testing Login Endpoint...")
    token = test_login()
    if token:
        print("✅ Login endpoint is working")
    else:
        print("❌ Login endpoint failed")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    main()