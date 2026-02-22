"""Test Kalshi API connection."""
import requests
from kalshi_auth import get_auth_headers

# Kalshi moved their API to api.elections.kalshi.com
API_BASE = "https://api.elections.kalshi.com"

def test_connection():
    """Test connection to Kalshi API."""
    print(f"Testing Kalshi connection...")
    print(f"Base URL: {API_BASE}")
    print()
    
    # Test 1: Get balance (requires auth)
    print("1. Testing /trade-api/v2/portfolio/balance...")
    try:
        path = "/trade-api/v2/portfolio/balance"
        headers = get_auth_headers("GET", path)
        
        resp = requests.get(
            f"{API_BASE}{path}",
            headers=headers,
            timeout=30
        )
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✅ SUCCESS!")
            print(f"   Balance: ${data.get('balance', 'N/A')}")
            print(f"   Available: ${data.get('available_balance', 'N/A')}")
        else:
            print(f"   ❌ Error {resp.status_code}: {resp.text[:300]}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    print()
    
    # Test 2: Get markets (requires auth)
    print("2. Testing /trade-api/v2/markets...")
    try:
        path = "/trade-api/v2/markets?limit=5"
        headers = get_auth_headers("GET", path)
        
        resp = requests.get(
            f"{API_BASE}{path}",
            headers=headers,
            timeout=30
        )
        
        if resp.status_code == 200:
            data = resp.json()
            markets = data.get("markets", [])
            print(f"   ✅ SUCCESS!")
            print(f"   Found {len(markets)} markets")
            if markets:
                print(f"   Example: {markets[0].get('ticker', 'N/A')}")
        else:
            print(f"   ❌ Error {resp.status_code}: {resp.text[:300]}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")
    
    print()
    
    # Test 3: Get exchange status (public, no auth)
    print("3. Testing /trade-api/v2/exchange/status...")
    try:
        resp = requests.get(
            f"{API_BASE}/trade-api/v2/exchange/status",
            timeout=30
        )
        
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✅ SUCCESS!")
            print(f"   Exchange: {data.get('exchange_active', 'N/A')}")
            print(f"   Trading: {data.get('trading_active', 'N/A')}")
        else:
            print(f"   ❌ Error {resp.status_code}")
    except Exception as e:
        print(f"   ❌ Exception: {e}")


if __name__ == "__main__":
    test_connection()
