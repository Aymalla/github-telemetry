"""Shared test utilities."""

import hashlib
import hmac


def compute_signature(payload: bytes, secret: str) -> str:
    """Compute a valid GitHub signature for testing.

    Args:
        payload: Raw request body bytes
        secret: The webhook secret

    Returns:
        Signature string in format "sha256=<hex_digest>"
    """
    signature = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"sha256={signature}"
