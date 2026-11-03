from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
import hashlib
import hmac
import base64
import json
from app.core.config import settings

# Lightweight base64url JWT utilities compliant with standard HS256 without external dependencies
def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _base64url_decode(data: str) -> bytes:
    padding = "=" * (4 - (len(data) % 4)) if len(data) % 4 != 0 else ""
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None, claims: Optional[Dict[str, Any]] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    header = {"alg": "HS256", "typ": "JWT"}
    payload: Dict[str, Any] = {
        "sub": str(subject),
        "exp": int(expire.timestamp()),
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    if claims:
        payload.update(claims)
        
    encoded_header = _base64url_encode(json.dumps(header).encode("utf-8"))
    encoded_payload = _base64url_encode(json.dumps(payload).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    
    signature = hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        signing_input,
        hashlib.sha256
    ).digest()
    
    encoded_signature = _base64url_encode(signature)
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        encoded_header, encoded_payload, encoded_signature = parts
        signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
        
        expected_sig = hmac.new(
            settings.JWT_SECRET_KEY.encode("utf-8"),
            signing_input,
            hashlib.sha256
        ).digest()
        
        actual_sig = _base64url_decode(encoded_signature)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
            
        payload = json.loads(_base64url_decode(encoded_payload).decode("utf-8"))
        exp = payload.get("exp")
        if exp and datetime.now(timezone.utc).timestamp() > exp:
            return None
            
        return payload
    except Exception:
        return None
