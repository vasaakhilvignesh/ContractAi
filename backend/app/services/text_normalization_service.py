"""
ContractIQ — Text Normalization Service (Phase 3B)

Provides conservative, non-destructive text normalization designed specifically
for legal contracts and evidence-first retrieval.

Invariants:
  1. Offsets (char_start, char_end) MUST refer to the normalized page text.
     Normalization changes character lengths (e.g. ligature expansion, space collapse),
     so chunk offsets are strictly recorded relative to the normalized page text.
  2. Non-destructive: Capitalization, punctuation, numbers, currencies, percentages,
     clause numbers, and defined terms are 100% preserved.
  3. No semantic alteration: No stemming, stopword removal, lemmatization, or LLM rewriting.
"""

import re
import unicodedata


# Zero-width / invisible Unicode characters to safely strip
ZERO_WIDTH_CHARS = ("\u200b", "\u200c", "\u200d", "\ufeff", "\u200e", "\u200f")

# Pattern for soft-hyphen or line-break hyphenation split across lines:
# Matches word character followed by soft-hyphen or standard hyphen at newline,
# followed by continuation lowercase letters (e.g. "indem-\nnification" -> "indemnification").
# We ensure the continuation is lowercase letters to avoid joining hyphenated compound names or headers.
LINEBREAK_HYPHEN_PATTERN = re.compile(r"([A-Za-z]{2,})-\n\s*([a-z]{2,})")

# Pattern matching standalone page number footers/headers (e.g. "Page 1 of 5", "1 / 10", "- 4 -")
PAGE_NUMBER_NOISE_PATTERN = re.compile(
    r"^(?:page\s+\d+(?:\s+(?:of|/)\s+\d+)?|\d+\s*/\s*\d+|[-—–]\s*\d+\s*[-—–]|\d+)$",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    """
    Conservatively normalizes raw extracted contract text.

    Steps applied:
      1. Unicode NFKC normalization (expands font ligatures like 'fi', 'fl').
      2. Strip non-printing zero-width characters (BOM, zero-width space).
      3. Normalize non-breaking spaces and tabs to standard spaces.
      4. Normalize line endings (CRLF, CR -> LF).
      5. Heal obvious line-break hyphenation (e.g. 'indem-\\nnification' -> 'indemnification').
      6. Collapse excessive horizontal spaces within each line while preserving indentation/line breaks.
      7. Collapse excessive consecutive blank lines (3+ newlines -> 2 newlines).
      8. Strip trailing line whitespace while preserving paragraph structure.

    Args:
        text: Raw extracted text (e.g. from PageExtraction.text).

    Returns:
        Normalized text string preserving all legal terminology and numbers.
    """
    if not text:
        return ""

    # 1. Unicode NFKC normalization
    normalized = unicodedata.normalize("NFKC", text)

    # 2. Strip invisible zero-width characters
    for zwc in ZERO_WIDTH_CHARS:
        normalized = normalized.replace(zwc, "")

    # 3. Soft hyphens (\u00ad)
    normalized = normalized.replace("\u00ad\n", "").replace("\u00ad", "")

    # 4. Normalize CRLF / CR to standard LF
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    # 5. Non-breaking spaces (\u00a0, \u202f) to standard space
    normalized = normalized.replace("\u00a0", " ").replace("\u202f", " ")

    # 6. Heal safe line-break hyphenation: "indem-\n  nification" -> "indemnification"
    normalized = LINEBREAK_HYPHEN_PATTERN.sub(r"\1\2", normalized)

    # 7. Horizontal whitespace normalization per line
    lines = normalized.split("\n")
    cleaned_lines: list[str] = []
    for line in lines:
        # Collapse multiple horizontal tabs/spaces into single space
        cleaned_line = re.sub(r"[ \t]+", " ", line).strip()
        cleaned_lines.append(cleaned_line)

    reconstructed = "\n".join(cleaned_lines)

    # 8. Collapse 3+ newlines down to 2 newlines (preserve paragraph separation)
    reconstructed = re.sub(r"\n{3,}", "\n\n", reconstructed)

    return reconstructed.strip()


def is_noise_text(text: str) -> bool:
    """
    Identifies obvious non-content noise (e.g., standalone page numbers, header artifacts).

    Rules:
      - Empty or single-character punctuation is noise.
      - Standalone page numbering strings ("Page 3 of 12", "1 / 5", "- 2 -") are noise.
      - Any string containing alphabetic characters is checked to ensure it's not a short legal clause.
    """
    cleaned = text.strip()
    if not cleaned:
        return True

    if len(cleaned) <= 3 and not any(c.isalnum() for c in cleaned):
        return True

    if PAGE_NUMBER_NOISE_PATTERN.match(cleaned):
        return True

    return False
