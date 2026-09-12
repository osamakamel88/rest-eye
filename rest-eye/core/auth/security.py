import hashlib
import hmac
import base64
import json
import time
from typing import Optional, Dict, Any
from ..config import config

def get_password_hash(password: str) -> str:
    """Secure PBKDF2-HMAC-SHA256 password hashing (zero external C-compiler dependencies)"""
    salt = "recode_rest_eye_salt_2026"
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return base64.b64encode(key).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return hmac.compare_digest(get_password_hash(plain_password), hashed_password)

def base64url_encode(input_bytes: bytes) -> str:
    return base64.urlsafe_b64encode(input_bytes).rstrip(b'=').decode('utf-8')

def base64url_decode(input_str: str) -> bytes:
    rem = len(input_str) % 4
    if rem > 0:
        input_str += '=' * (4 - rem)
    return base64.urlsafe_b64decode(input_str.encode('utf-8'))

def create_access_token(data: dict, expires_delta_minutes: Optional[int] = None) -> str:
    """Creates a standard signed JWT Token"""
    to_encode = data.copy()
    expire = time.time() + ((expires_delta_minutes or config.jwt_access_token_expire_minutes) * 60)
    to_encode.update({"exp": expire, "iat": time.time()})

    header = {"alg": config.jwt_algorithm, "typ": "JWT"}
    header_b64 = base64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    payload_b64 = base64url_encode(json.dumps(to_encode, separators=(',', ':')).encode('utf-8'))

    signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
    signature = hmac.new(config.jwt_secret.encode('utf-8'), signing_input, hashlib.sha256).digest()
    sig_b64 = base64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"

def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and verifies a JWT Token"""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        
        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        expected_sig = hmac.new(config.jwt_secret.encode('utf-8'), signing_input, hashlib.sha256).digest()
        actual_sig = base64url_decode(sig_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        # Verify expiration
        payload_bytes = base64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode('utf-8'))
        if payload.get("exp", 0) < time.time():
            return None  # Token expired

        return payload
    except Exception:
        return None
