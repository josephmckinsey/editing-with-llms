"""Output formatters for editing-with-llms."""

from typing import List
from pathlib import Path
import json
from .models import Issue


class CompilerFormatter:
    """Format issues in compiler-style format: file:line:col: type: message"""

    def format(self, issues: List[Issue], filename: str) -> str:
        """Format issues as compiler-style output.

        Args:
            issues: List of Issue objects
            filename: Name of the file being checked

        Returns:
            Formatted output string
        """
        if not issues:
            return ""

        lines = []
        for issue in issues:
            line_num = issue.line_number or 1
            col_num = 1  # Phase 1: always column 1
            lines.append(
                f"{filename}:{line_num}:{col_num}: {issue.issue_type}: {issue.explanation}"
            )

        return "\n".join(lines)


class StreamingFormatter:
    """Format issues in streaming text format with output.txt file."""

    def __init__(self, output_file: str = "output.txt"):
        """Initialize streaming formatter.

        Args:
            output_file: Path to output file (default: output.txt)
        """
        self.output_file = output_file

    def format_and_stream(self, response_stream, print_fn=print) -> str:
        """Stream LLM response to console and collect output.

        Args:
            response_stream: Iterable of response chunks
            print_fn: Function to print output (default: print)

        Returns:
            Complete response text
        """
        output_chunks = []
        for chunk in response_stream:
            print_fn(chunk, end="", flush=True)
            output_chunks.append(chunk)

        output = "".join(output_chunks)

        # Write to file
        with open(self.output_file, "w", encoding="utf-8") as f:
            f.write(output)

        print_fn(f"\nResults written to {self.output_file}")

        return output


def format_issues(
    issues: List[Issue], filename: str, output_format: str = "compiler"
) -> str:
    """Format issues according to specified output format.

    Args:
        issues: List of Issue objects
        filename: Name of the file being checked
        output_format: Format type ("compiler", "streaming", or "json")

    Returns:
        Formatted output string
    """
    if output_format == "compiler":
        formatter = CompilerFormatter()
        return formatter.format(issues, filename)
    elif output_format == "json":
        return json.dumps(
            [
                {
                    "text": issue.text,
                    "issue_type": issue.issue_type,
                    "explanation": issue.explanation,
                    "line_number": issue.line_number,
                    "confidence": issue.confidence,
                    "severity": issue.severity,
                }
                for issue in issues
            ],
            indent=2,
        )
    else:
        raise ValueError(f"Unknown output format: {output_format}")