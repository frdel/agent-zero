#!/usr/bin/env python3
"""
Test script to verify FastA2A agent card routing and authentication.
"""

import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


import asyncio
from python.helpers import settings


def get_test_urls():
    """Get the URLs to test based on current settings."""
    try:
        cfg = settings.get_settings()
        token = cfg.get("mcp_server_token", "")

        if not token:
            print("❌ No mcp_server_token found in settings")
            return None

        base_url = "http://localhost:50101"

        urls = {
            "token_based": f"{base_url}/a2a/t-{token}/.well-known/agent.json",
            "bearer_auth": f"{base_url}/a2a/.well-known/agent.json",
            "api_key_header": f"{base_url}/a2a/.well-known/agent.json",
            "api_key_query": f"{base_url}/a2a/.well-known/agent.json?api_key={token}"
        }

        return {"token": token, "urls": urls}

    except Exception as e:
        print(f"❌ Error getting settings: {e}")
        return None


def print_test_commands():
    """Print curl commands to test FastA2A authentication."""
    data = get_test_urls()
    if not data:
        return

    token = data["token"]
    urls = data["urls"]

    print("🚀 FastA2A Agent Card Testing Commands")
    print("=" * 60)
    print(f"Current token: {token}")
    print()

    print("1️⃣  Token-based URL (recommended):")
    print(f"   curl -v '{urls['token_based']}'")
    print()

    print("2️⃣  Bearer authentication:")
    print(f"   curl -v -H 'Authorization: Bearer {token}' '{urls['bearer_auth']}'")
    print()

    print("3️⃣  API key header:")
    print(f"   curl -v -H 'X-API-KEY: {token}' '{urls['api_key_header']}'")
    print()

    print("4️⃣  API key query parameter:")
    print(f"   curl -v '{urls['api_key_query']}'")
    print()

    print("Expected response (if working):")
    print("   HTTP/1.1 200 OK")
    print("   Content-Type: application/json")
    print("   {")
    print('     "name": "Agent Zero",')
    print('     "version": "1.0.0",')
    print('     "skills": [...]')
    print("   }")
    print()

    print("Expected error (if auth fails):")
    print("   HTTP/1.1 401 Unauthorized")
    print("   Unauthorized")
    print()


def print_troubleshooting():
    """Print troubleshooting information."""
    print("🔧 Troubleshooting FastA2A Issues")
    print("=" * 40)
    print()
    print("1. Server not running:")
    print("   - Make sure Agent Zero is running: python run_ui.py")
    print("   - Check the correct port (default: 50101)")
    print()

    print("2. Authentication failures:")
    print("   - Verify token matches in settings")
    print("   - Check token format (should be 16 characters)")
    print("   - Try different auth methods")
    print()

    print("3. FastA2A not available:")
    print("   - Install FastA2A: pip install fasta2a")
    print("   - Check server logs for FastA2A configuration errors")
    print()

    print("4. Routing issues:")
    print("   - Verify /a2a prefix is working")
    print("   - Check DispatcherMiddleware configuration")
    print("   - Look for FastA2A startup messages in logs")
    print()


def validate_token_format():
    """Validate that the token format is correct."""
    try:
        cfg = settings.get_settings()
        token = cfg.get("mcp_server_token", "")

        print("🔍 Token Validation")
        print("=" * 25)

        if not token:
            print("❌ No token found")
            return False

        print(f"✅ Token found: {token}")
        print(f"✅ Token length: {len(token)} characters")

        if len(token) != 16:
            print("⚠️  Warning: Expected token length is 16 characters")

        # Check token characters
        if token.isalnum():
            print("✅ Token contains only alphanumeric characters")
        else:
            print("⚠️  Warning: Token contains non-alphanumeric characters")

        return True

    except Exception as e:
        print(f"❌ Error validating token: {e}")
        return False


async def test_server_connectivity():
    """Test basic server connectivity."""
    try:
        import httpx

        print("🌐 Server Connectivity Test")
        print("=" * 30)

        async with httpx.AsyncClient() as client:
            try:
                # Test basic server
                await client.get("http://localhost:50101/", timeout=5.0)
                print("✅ Agent Zero server is running")
                return True
            except httpx.ConnectError:
                print("❌ Cannot connect to Agent Zero server")
                print("   Make sure the server is running: python run_ui.py")
                return False
            except Exception as e:
                print(f"❌ Server connectivity error: {e}")
                return False

    except ImportError:
        print("ℹ️  httpx not available, skipping connectivity test")
        print("   Install with: pip install httpx")
        return None


def main():
    """Main test function."""
    print("🧪 FastA2A Agent Card Testing Utility")
    print("=" * 45)
    print()

    # Validate token
    if not validate_token_format():
        print()
        print_troubleshooting()
        return 1

    print()

    # Test connectivity if possible
    try:
        connectivity = asyncio.run(test_server_connectivity())
        print()

        if connectivity is False:
            print_troubleshooting()
            return 1

    except Exception as e:
        print(f"Error testing connectivity: {e}")
        print()

    # Print test commands
    print_test_commands()

    print("📋 Next Steps:")
    print("1. Start Agent Zero server if not running")
    print("2. Run one of the curl commands above")
    print("3. Check for successful 200 response with agent card JSON")
    print("4. If issues occur, see troubleshooting section")

    return 0


if __name__ == "__main__":
    sys.exit(main())
