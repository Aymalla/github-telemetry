"""Tests for GitHub signature validation."""

import hashlib
import hmac

from src.shared.github_signature import validate_github_signature


def compute_signature(payload: bytes, secret: str) -> str:
    """Compute a valid GitHub signature for testing."""
    signature = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return f"sha256={signature}"


class TestValidateGitHubSignature:
    """Tests for validate_github_signature function."""

    def test_valid_signature(self) -> None:
        """Test that a valid signature is accepted."""
        payload = b'{"action": "completed"}'
        secret = "test-secret"
        signature = compute_signature(payload, secret)

        result = validate_github_signature(payload, signature, secret)
        assert result is True

    def test_invalid_signature(self) -> None:
        """Test that an invalid signature is rejected."""
        payload = b'{"action": "completed"}'
        secret = "test-secret"
        wrong_signature = "sha256=invalid"

        result = validate_github_signature(payload, wrong_signature, secret)
        assert result is False

    def test_missing_signature(self) -> None:
        """Test that a missing signature is rejected."""
        payload = b'{"action": "completed"}'
        secret = "test-secret"

        result = validate_github_signature(payload, None, secret)
        assert result is False

    def test_no_secret_configured(self) -> None:
        """Test that validation passes when no secret is configured."""
        payload = b'{"action": "completed"}'

        result = validate_github_signature(payload, None, "")
        assert result is True

    def test_wrong_signature_format(self) -> None:
        """Test that wrong signature format is rejected."""
        payload = b'{"action": "completed"}'
        secret = "test-secret"
        wrong_format = "md5=invalid"

        result = validate_github_signature(payload, wrong_format, secret)
        assert result is False

    def test_tampered_payload(self) -> None:
        """Test that a tampered payload fails validation."""
        original_payload = b'{"action": "completed"}'
        secret = "test-secret"
        signature = compute_signature(original_payload, secret)

        tampered_payload = b'{"action": "failed"}'
        result = validate_github_signature(tampered_payload, signature, secret)
        assert result is False
