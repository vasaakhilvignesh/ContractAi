"""
ContractIQ — Secret Scanner Test Suite

Verifies:
  1. Safe placeholders pass without detection.
  2. Fake/unmarked secrets are detected.
  3. Real-looking Google API key patterns are detected.
  4. Tracked repository source contains no real secrets.
  5. Environment files (.env, backend/.env) remain ignored.
  6. No secret values are printed or leaked in output messages.
"""

from pathlib import Path
import pytest

from app.core.secret_scanner import (
    SecretFinding,
    is_safe_placeholder,
    scan_text,
    scan_tracked_repository,
    verify_env_files_ignored,
)


class TestSecretScanner:
    """Tests for the repository secret detection utility."""

    def test_safe_placeholder_passes(self):
        """Safe placeholders (e.g. documentation, template, env var references) must pass."""
        safe_snippets = [
            "GEMINI_API_KEY=your-gemini-api-key-here",
            "DATABASE_URL=postgresql://user:<password>@localhost:5432/dbname",
            "JWT_SECRET_KEY=change-this-to-a-secure-random-secret-key-in-production",
            "Authorization: Bearer ${JWT_TOKEN}",
            "# Example: AIzaSyDummyPlaceholderKey1234567890",
            "API_KEY = os.environ.get('GEMINI_API_KEY', 'mock-key')",
        ]
        for snippet in safe_snippets:
            findings = scan_text(snippet)
            assert len(findings) == 0, f"Expected safe placeholder to pass: {snippet}"

    def test_fake_example_secret_detected(self):
        """Unmarked secrets (such as unmasked DB URIs or exposed tokens) must be detected."""
        # Build URI dynamically so the scanner does not flag this test file's own source.
        scheme = "postgresql"
        user = "app_user"
        password = "p4ssw0rd998877!"     # noqa: S106 — intentional test fixture, not a real credential
        host = "prod-db.corp-internal.net:5432"
        db = "prod_db"
        unmarked_db_uri = f"DATABASE_URL={scheme}://{user}:{password}@{host}/{db}"
        findings = scan_text(unmarked_db_uri)
        assert len(findings) > 0
        assert any(f.rule_id == "DATABASE_CREDENTIALS" for f in findings)

    def test_real_looking_google_api_key_patterns_detected(self):
        """Real-looking 39-character AIza Google API key patterns must be detected."""
        # Construct dynamically so the test file itself does not contain a static secret literal
        raw_key = "AIza" + "SyB" + "1234567890abcdefghijklmnopqrstuv"
        test_line = f"export GEMINI_API_KEY=\"{raw_key}\""

        findings = scan_text(test_line)
        assert len(findings) == 1
        assert findings[0].rule_id == "GOOGLE_API_KEY"

    def test_tracked_application_source_contains_no_secrets(self):
        """Scan all git-tracked files in the repository and ensure 0 findings."""
        repo_root = Path(__file__).resolve().parents[2]
        findings = scan_tracked_repository(repo_root)

        # Print safe messages if any fail
        if findings:
            safe_messages = [f.format_safe_message() for f in findings]
            pytest.fail(
                f"Tracked repository files contain {len(findings)} potential secret(s):\n"
                + "\n".join(safe_messages)
            )

    def test_env_files_remain_ignored(self):
        """Verify that .env, backend/.env, and local env files are ignored by git."""
        repo_root = Path(__file__).resolve().parents[2]
        assert verify_env_files_ignored(repo_root) is True

    def test_no_secret_values_printed_by_check(self):
        """Verifies that format_safe_message and SecretFinding NEVER include the secret string."""
        raw_key = "AIza" + "SyZ" + "9999999999abcdefghijklmnopqrstuv"
        test_content = f"GEMINI_KEY = '{raw_key}'"

        findings = scan_text(test_content, file_path="test_file.py")
        assert len(findings) == 1

        safe_msg = findings[0].format_safe_message()
        # Ensure raw secret is NOT present anywhere in the safe message or repr
        assert raw_key not in safe_msg
        assert raw_key not in findings[0].description
        assert raw_key not in findings[0].rule_id
