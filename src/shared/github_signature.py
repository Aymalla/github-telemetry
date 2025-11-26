"""GitHub webhook signature validation utilities."""

import hashlib
import hmac
import logging

logger = logging.getLogger(__name__)


def validate_github_signature(
    payload: bytes,
    signature_header: str | None,
    secret: str,
) -> bool:
    """Validate the GitHub webhook signature.

    GitHub uses HMAC-SHA256 to sign webhook payloads. This function validates
    that the provided signature matches the expected signature computed from
    the payload and secret.

    Args:
        payload: Raw request body bytes
        signature_header: The X-Hub-Signature-256 header value
        secret: The webhook secret configured in GitHub

    Returns:
        True if signature is valid, False otherwise
    """
    if not secret:
        logger.warning("No webhook secret configured, skipping signature validation")
        return True

    if not signature_header:
        logger.warning("No signature header provided")
        return False

    if not signature_header.startswith("sha256="):
        logger.warning("Invalid signature format, expected sha256=")
        return False

    # Extract the signature from the header
    expected_signature = signature_header[7:]  # Remove "sha256=" prefix

    # Compute the expected signature
    computed_signature = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Use constant-time comparison to prevent timing attacks
    is_valid = hmac.compare_digest(computed_signature, expected_signature)

    if not is_valid:
        logger.warning("Webhook signature validation failed")

    return is_valid
