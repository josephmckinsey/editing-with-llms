"""Parsing functions for LLM output."""

import re
from typing import List, Optional
from .models import Issue


def find_line_number(text_snippet: str, original_text: str) -> Optional[int]:
    """Find the line number where text_snippet appears in original_text.

    Args:
        text_snippet: The text to search for
        original_text: The full original text

    Returns:
        Line number (1-indexed) where text_snippet appears, or None if not found
    """
    lines = original_text.split("\n")
    text_snippet_lower = text_snippet.strip().lower()

    for i, line in enumerate(lines, start=1):
        if text_snippet_lower in line.lower():
            return i

    return None


def parse_structured_output(
    response: str, original_text: str, issue_type: str = "typo"
) -> List[Issue]:
    """Parse structured output format (TEXT: / ISSUE: format).

    Args:
        response: LLM response text
        original_text: Original text being checked
        issue_type: Type of check being performed

    Returns:
        List of Issue objects
    """
    issues = []
    blocks = response.split("\n\n")

    for block in blocks:
        lines = block.strip().split("\n")
        issue_data = {}

        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                issue_data[key.strip().lower()] = value.strip()

        if "text" in issue_data:
            # Extract confidence if present
            confidence = None
            if "confidence" in issue_data:
                confidence_str = issue_data["confidence"]
                match = re.search(r"\d+", confidence_str)
                if match:
                    confidence = int(match.group())

            # Compute line number from text snippet
            # We always have plain text input, so we always compute line numbers
            line_number = find_line_number(issue_data.get("text", ""), original_text)

            issues.append(
                Issue(
                    text=issue_data.get("text", ""),
                    issue_type=issue_type,
                    explanation=issue_data.get("issue", ""),
                    line_number=line_number,
                    confidence=confidence,
                    severity=issue_data.get("severity", "").lower()
                    if "severity" in issue_data
                    else None,
                )
            )

    return issues
