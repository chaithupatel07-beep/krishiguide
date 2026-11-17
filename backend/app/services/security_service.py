import re
import time
from typing import Dict, Tuple, Optional
from fastapi import HTTPException, status
from app.core.config import settings
from app.core.logging import logger

# Comprehensive Prompt Injection patterns
INJECTION_SIGNATURES = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.IGNORECASE),
    re.compile(r"disregard\s+(all\s+)?(previous|prior|system)\s+prompts?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(in\s+)?(dan|developer|unrestricted|jailbroken)\s+mode", re.IGNORECASE),
    re.compile(r"bypass\s+(all\s+)?(safety|security|content)\s+filters?", re.IGNORECASE),
    re.compile(r"system\s*:\s*you\s+must", re.IGNORECASE),
    re.compile(r"<\s*\|?im_start\|?\s*>", re.IGNORECASE),
    re.compile(r"\[\s*INST\s*\]\s*<<SYS>>", re.IGNORECASE),
    re.compile(r"reveal\s+(your\s+)?(system\s+prompt|secret\s+key|api\s+key)", re.IGNORECASE),
]

# In-memory sliding window rate limiter
_request_timestamps: Dict[str, list] = {}


class SecurityService:
    @staticmethod
    def validate_and_sanitize_query(query: str, max_length: int = 1000) -> str:
        """
        Validates user query length, checks for prompt injection attacks,
        and sanitizes dangerous delimiters.
        """
        if not query or not query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question cannot be empty.",
            )

        clean_q = query.strip()
        if len(clean_q) < 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question must be at least 3 characters long.",
            )

        if len(clean_q) > max_length:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Question exceeds maximum allowed length of {max_length} characters.",
            )

        # Check for Prompt Injection attempts
        for sig in INJECTION_SIGNATURES:
            if sig.search(clean_q):
                logger.warning(f"Security Alert: Blocked prompt injection attempt: '{clean_q[:60]}...'")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid request content detected. Please ask legitimate agricultural questions.",
                )

        # Strip non-printable and suspicious escape characters
        sanitized = "".join(ch for ch in clean_q if ch.isprintable() or ch in "\n\t")
        return sanitized

    @staticmethod
    def check_rate_limit(client_id: str, max_requests: Optional[int] = None, window_seconds: int = 60) -> None:
        """
        Enforces token-bucket sliding window rate limit per IP or user.
        """
        limit = max_requests or settings.RATE_LIMIT_PER_MINUTE
        now = time.time()
        cutoff = now - window_seconds

        timestamps = _request_timestamps.get(client_id, [])
        # Prune old timestamps
        timestamps = [t for t in timestamps if t > cutoff]

        if len(timestamps) >= limit:
            logger.warning(f"Rate limit exceeded for client: {client_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Maximum {limit} queries per minute allowed. Please wait before retrying.",
            )

        timestamps.append(now)
        _request_timestamps[client_id] = timestamps

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough estimation of token count (~4 characters per token)."""
        if not text:
            return 0
        return max(1, len(text) // 4)

