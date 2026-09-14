"""
ContractIQ — Secret Scanner and Repository Protection Utility

Provides:
  - Lightweight scanning for accidentally exposed API keys and credentials.
  - Verification that git ignores .env configuration files.
  - Safe reporting: NEVER prints or exposes secret values in reports or outputs.
"""

from dataclasses import dataclass
import os
from pathlib import Path
import re
import subprocess
from typing import List


@dataclass(frozen=True)
class SecretFinding:
    file_path: str
    line_number: int
    rule_id: str
    description: str

    def format_safe_message(self) -> str:
        """Formats finding without printing the raw secret value."""
        return f"[{self.rule_id}] {self.file_path}:{self.line_number} — {self.description}"


# Detection rules for common high-risk secret formats
SECRET_PATTERNS = [
    (
        "GOOGLE_API_KEY",
        re.compile(r"AIza[0-9A-Za-z_-]{35}"),
        "Google/Gemini API key pattern detected",
    ),
    (
        "PRIVATE_KEY",
        re.compile(r"-----BEGIN\s+[A-Z0-9_-]*\s*PRIVATE\s+KEY-----"),
        "Private encryption key block detected",
    ),
    (
        "DATABASE_CREDENTIALS",
        re.compile(
            r"(?:postgres(?:ql)?|mysql|mongodb)(?:\+[a-zA-Z0-9_-]+)?://[^:\s\"']+:(?!(?i:\[REDACTED\]|password|<password>|pass|sample|example|dummy|mock))[^@\s\"']+@[a-zA-Z0-9.-]+"
        ),
        "Database URI with plaintext password detected",
    ),
    (
        "AWS_ACCESS_KEY",
        re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
        "AWS access key ID detected",
    ),
    (
        "GENERIC_BEARER_JWT",
        re.compile(r"\bBearer\s+eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{20,}\b"),
        "Live Bearer JWT token pattern detected",
    ),
]

SAFE_PLACEHOLDER_MARKERS = [
    "example",
    "placeholder",
    "change-this",
    "changeme",
    "your-",
    "your_",
    "<your",
    "dummy",
    "fake",
    "mock",
    "[redacted",
    "${",
    "env_var",
    "synthetic",
]


def is_safe_placeholder(text: str) -> bool:
    lower = text.lower()
    return any(marker in lower for marker in SAFE_PLACEHOLDER_MARKERS)


def scan_text(content: str, file_path: str = "<memory>") -> List[SecretFinding]:
    findings: List[SecretFinding] = []
    lines = content.splitlines()

    for line_idx, line in enumerate(lines, start=1):
        if is_safe_placeholder(line):
            continue

        for rule_id, pattern, desc in SECRET_PATTERNS:
            match = pattern.search(line)
            if match:
                matched_str = match.group(0)
                if not is_safe_placeholder(matched_str):
                    findings.append(
                        SecretFinding(
                            file_path=file_path,
                            line_number=line_idx,
                            rule_id=rule_id,
                            description=desc,
                        )
                    )
    return findings


def scan_file(path: Path) -> List[SecretFinding]:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
        return scan_text(content, file_path=str(path))
    except Exception:
        return []


def get_tracked_files(repo_root: Path) -> List[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    paths = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            paths.append(repo_root / line)
    return paths


def scan_tracked_repository(repo_root: Path) -> List[SecretFinding]:
    findings: List[SecretFinding] = []
    tracked = get_tracked_files(repo_root)
    skip_extensions = {".png", ".jpg", ".jpeg", ".ico", ".svg", ".pdf", ".woff", ".woff2", ".pyc"}

    for fpath in tracked:
        if fpath.suffix.lower() in skip_extensions:
            continue
        if fpath.is_file():
            findings.extend(scan_file(fpath))

    return findings


def verify_env_files_ignored(repo_root: Path) -> bool:
    test_files = [".env", "backend/.env", "frontend/.env", ".env.local"]
    for env_file in test_files:
        res = subprocess.run(
            ["git", "check-ignore", env_file],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            tracked_check = subprocess.run(
                ["git", "ls-files", "--error-unmatch", env_file],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
            )
            if tracked_check.returncode == 0:
                return False
    return True


if __name__ == "__main__":
    import sys
    root = Path(__file__).resolve().parents[2]
    findings = scan_tracked_repository(root)
    env_ok = verify_env_files_ignored(root)

    if not env_ok:
        print("[ERROR] .env files are not properly ignored by git!")
        sys.exit(1)

    if findings:
        print(f"[SECURITY ALERT] {len(findings)} potential secrets detected:")
        for f in findings:
            print("  " + f.format_safe_message())
        sys.exit(1)
    else:
        print("[SECURITY CHECK PASSED] No secrets detected in tracked repository files.")
        sys.exit(0)
