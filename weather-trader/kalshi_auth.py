"""Kalshi RSA authentication utilities."""
import json
import base64
import datetime
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature


def load_credentials():
    """Load Kalshi credentials from config."""
    cred_path = Path.home() / ".config" / "kalshi" / "credentials.json"
    if not cred_path.exists():
        raise FileNotFoundError(f"Credentials not found at {cred_path}")
    
    with open(cred_path) as f:
        return json.load(f)


def load_private_key(private_key_pem: str):
    """Load RSA private key from PEM string."""
    return serialization.load_pem_private_key(
        private_key_pem.encode('utf-8'),
        password=None,
        backend=default_backend()
    )


def sign_request(private_key, timestamp: str, method: str, path: str) -> str:
    """Sign a request with RSA-PSS.
    
    Args:
        private_key: Loaded RSA private key
        timestamp: Current timestamp in milliseconds
        method: HTTP method (GET, POST, etc.)
        path: URL path (without query params)
    
    Returns:
        Base64-encoded signature
    """
    # Kalshi requires: timestamp + method + path (without query string)
    message = f"{timestamp}{method}{path}".encode('utf-8')
    
    try:
        signature = private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode('utf-8')
    except InvalidSignature as e:
        raise ValueError("RSA sign PSS failed") from e


def get_auth_headers(method: str, path: str, creds: dict = None) -> dict:
    """Generate authentication headers for Kalshi API.
    
    Args:
        method: HTTP method
        path: URL path (e.g., /trade-api/v2/portfolio/balance)
        creds: Credentials dict (loads from file if None)
    
    Returns:
        Headers dict with KALSHI-ACCESS-* keys
    """
    if creds is None:
        creds = load_credentials()
    
    key_id = creds["key_id"]
    private_key_pem = creds["private_key"]
    
    # Generate timestamp
    timestamp_ms = int(datetime.datetime.now().timestamp() * 1000)
    timestamp_str = str(timestamp_ms)
    
    # Strip query params from path
    path_without_query = path.split('?')[0]
    
    # Load key and sign
    private_key = load_private_key(private_key_pem)
    signature = sign_request(private_key, timestamp_str, method, path_without_query)
    
    return {
        'KALSHI-ACCESS-KEY': key_id,
        'KALSHI-ACCESS-SIGNATURE': signature,
        'KALSHI-ACCESS-TIMESTAMP': timestamp_str
    }


if __name__ == "__main__":
    # Test authentication
    print("Testing Kalshi authentication...")
    
    try:
        creds = load_credentials()
        print(f"✅ Loaded credentials for key: {creds['key_id'][:8]}...")
        
        # Test signing
        headers = get_auth_headers("GET", "/trade-api/v2/portfolio/balance")
        print(f"✅ Generated auth headers:")
        print(f"   KALSHI-ACCESS-KEY: {headers['KALSHI-ACCESS-KEY'][:8]}...")
        print(f"   KALSHI-ACCESS-TIMESTAMP: {headers['KALSHI-ACCESS-TIMESTAMP']}")
        print(f"   KALSHI-ACCESS-SIGNATURE: {headers['KALSHI-ACCESS-SIGNATURE'][:20]}...")
        print("\n✅ Authentication ready!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
