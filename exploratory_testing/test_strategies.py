#!/usr/bin/env python3
"""
Test different strategies for sending text to LLMs and parsing their responses.

This script implements and compares:
1. Different input format strategies (how to send text)
2. Different output parsing strategies (how to get location data)
3. Format-aware handling (dealing with code/LaTeX/markdown)
"""

import llm
from pathlib import Path
import json
import re
import statistics
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class Issue:
    """Represents a potential writing issue found by the LLM."""

    text: str  # The problematic text
    issue_type: str  # "typo", "clarity", etc.
    explanation: str  # Why it's an issue
    line_number: Optional[int] = None  # Line number if we can extract it
    strategy: str = ""  # Which strategy found this


# ============================================================================
# INPUT FORMAT STRATEGIES
# ============================================================================


def strategy_line_numbered_arrow(text: str) -> str:
    """
    Strategy 1a: Prepend line numbers with arrow to each line (like Claude Code's Read tool).

    Example:
         1→First line
         2→Second line
    """
    lines = text.split("\n")
    numbered_lines = [f"{i+1:6d}→{line}" for i, line in enumerate(lines)]
    return "\n".join(numbered_lines)


def strategy_line_numbered_pipe(text: str) -> str:
    """
    Strategy 1b: Prepend line numbers with pipe to each line.

    Example:
         1 | First line
         2 | Second line
    """
    lines = text.split("\n")
    numbered_lines = [f"{i+1:6d} | {line}" for i, line in enumerate(lines)]
    return "\n".join(numbered_lines)


def strategy_structured_markers(text: str) -> str:
    """
    Strategy 2: Use XML-style tags to mark sections.

    Example:
        <document>
        <line n="1">First line</line>
        <line n="2">Second line</line>
        </document>
    """
    lines = text.split("\n")
    marked_lines = ['<document>']
    for i, line in enumerate(lines, 1):
        marked_lines.append(f'<line n="{i}">{line}</line>')
    marked_lines.append('</document>')
    return "\n".join(marked_lines)


def strategy_plain_text(text: str) -> str:
    """
    Strategy 3: Send plain text, rely on LLM to quote fragments.

    This is the simplest approach - just send the text as-is.
    """
    return text


# ============================================================================
# OUTPUT PARSING STRATEGIES
# ============================================================================


def parse_line_citations(response: str, original_text: str) -> List[Issue]:
    """
    Strategy 1: Parse responses that cite "Line N: [text]"

    Expected format:
        - Line 5: [refrigderator]
        - Line 10: [runng]
    """
    issues = []
    # Match patterns like "Line 5: [text]" or "line 5: [text]"
    pattern = r"[Ll]ine\s+(\d+).*?\[([^\]]+)\]"
    matches = re.finditer(pattern, response)

    for match in matches:
        line_num = int(match.group(1))
        text = match.group(2)
        issues.append(
            Issue(
                text=text,
                issue_type="typo",
                explanation="Found via line citation",
                line_number=line_num,
                strategy="line_citations",
            )
        )

    return issues


def parse_structured_output(response: str, original_text: str) -> List[Issue]:
    """
    Strategy 2: Parse structured format like:
        LINE: 5
        TEXT: refrigderator
        ISSUE: spelling error
    """
    issues = []
    # Split into blocks separated by blank lines
    blocks = response.split("\n\n")

    for block in blocks:
        lines = block.strip().split("\n")
        issue_data = {}

        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                issue_data[key.strip().lower()] = value.strip()

        if "line" in issue_data and "text" in issue_data:
            issues.append(
                Issue(
                    text=issue_data.get("text", ""),
                    issue_type="typo",
                    explanation=issue_data.get("issue", ""),
                    line_number=int(issue_data.get("line", 0)),
                    strategy="structured_output",
                )
            )

    return issues


def parse_json_output(response: str, original_text: str) -> List[Issue]:
    """
    Strategy 3: Parse JSON responses.

    Expected format:
        [
            {"line": 5, "text": "refrigderator", "issue": "spelling"},
            ...
        ]
    """
    issues = []
    try:
        # Try to extract JSON from the response
        # Look for array or object patterns
        json_match = re.search(r"(\[.*\]|\{.*\})", response, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(1))

            # Handle both array and single object
            if isinstance(data, dict):
                data = [data]

            for item in data:
                issues.append(
                    Issue(
                        text=item.get("text", ""),
                        issue_type=item.get("type", "typo"),
                        explanation=item.get("issue", item.get("explanation", "")),
                        line_number=item.get("line"),
                        strategy="json_output",
                    )
                )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"JSON parse error: {e}")

    return issues


def parse_fuzzy_matching(response: str, original_text: str) -> List[Issue]:
    """
    Strategy 4: Use fuzzy text matching to find quoted fragments in original.

    This extracts text in square brackets and tries to find it in the original.
    """
    issues = []
    # Extract text in square brackets
    pattern = r"\[([^\]]+)\]"
    matches = re.finditer(pattern, response)

    lines = original_text.split("\n")

    for match in matches:
        quoted_text = match.group(1)

        # Try to find this text in the original
        for line_num, line in enumerate(lines, 1):
            if quoted_text in line:
                issues.append(
                    Issue(
                        text=quoted_text,
                        issue_type="typo",
                        explanation="Found via fuzzy matching",
                        line_number=line_num,
                        strategy="fuzzy_matching",
                    )
                )
                break  # Only use first match

    return issues


# ============================================================================
# SYSTEM PROMPTS FOR EACH OUTPUT STRATEGY
# ============================================================================

PROMPT_LINE_CITATIONS = """You are a proofreader. Carefully review the provided text for typos, spelling mistakes, and grammatical errors.

For each issue you find, cite it with the line number and the offending text in square brackets:
    - Line 5: [refrigderator] (spelling error)
    - Line 10: [runng] (spelling error)

If there are no errors, say "There are no errors found."
"""

PROMPT_STRUCTURED_OUTPUT = """You are a proofreader. Carefully review the provided text for typos, spelling mistakes, and grammatical errors.

For each issue you find, output in this format:

LINE: <line number>
TEXT: <problematic text>
ISSUE: <brief explanation>

If there are no errors, say "There are no errors found."
"""

PROMPT_JSON_OUTPUT = """You are a proofreader. Carefully review the provided text for typos, spelling mistakes, and grammatical errors.

Output your findings as a JSON array of objects with this structure:
[
    {"line": <line number>, "text": "<problematic text>", "issue": "<explanation>"},
    ...
]

If there are no errors, output: []
"""

PROMPT_FUZZY_MATCHING = """You are a proofreader. Carefully review the provided text for typos, spelling mistakes, and grammatical errors.

For each issue you find, write the offending text in square brackets:
    - [refrigderator]
    - [runng]

If there are no errors, say "There are no errors found."
"""


# ============================================================================
# TEST RUNNER
# ============================================================================


def run_strategy_test(
    input_strategy_name: str,
    input_strategy_fn,
    output_strategy_name: str,
    output_prompt: str,
    output_parser_fn,
    test_text: str,
    trial_num: int = 1,
    model_name: Optional[str] = None,
) -> Tuple[str, List[Issue]]:
    """
    Run a single strategy combination and return results.

    Returns:
        (llm_response, parsed_issues)
    """
    print(
        f"\n{'='*70}\nTesting: {input_strategy_name} + {output_strategy_name} (Trial {trial_num})\n{'='*70}"
    )

    # Format input
    formatted_input = input_strategy_fn(test_text)

    # Prepare prompt
    full_prompt = f"Check the following text:\n\n{formatted_input}"

    # Call LLM
    model = llm.get_model(model_name) if model_name else llm.get_model()
    if trial_num == 1:
        print(f"Using model: {model.model_id}")

    response = model.prompt(full_prompt, system=output_prompt)
    response_text = "".join(chunk for chunk in response)

    print(f"\nLLM Response (truncated):\n{response_text[:200]}...\n")

    # Parse output
    issues = output_parser_fn(response_text, test_text)

    print(f"Parsed {len(issues)} issues")

    return response_text, issues


def main():
    """Run all strategy combinations on test document."""
    # Number of trials to run for each strategy
    NUM_TRIALS = 10

    # Load test document
    test_file = Path(__file__).parent / "test"
    if not test_file.exists():
        print(f"Error: Test file not found at {test_file}")
        return

    with open(test_file, "r", encoding="utf-8") as f:
        test_text = f.read()

    # For faster testing, use a smaller excerpt
    # Let's use the first 100 lines which should have more variety
    test_excerpt = "\n".join(test_text.split("\n")[:100])

    print(f"Test document: {len(test_excerpt)} characters, {len(test_excerpt.split(chr(10)))} lines")
    print(f"First 200 chars: {test_excerpt[:200]}...")
    print(f"\nRunning {NUM_TRIALS} trials per strategy combination...\n")

    # Define strategy combinations to test
    input_strategies = [
        ("Line-numbered (arrow)", strategy_line_numbered_arrow),
        ("Line-numbered (pipe)", strategy_line_numbered_pipe),
        ("Structured markers", strategy_structured_markers),
        ("Plain text", strategy_plain_text),
    ]

    output_strategies = [
        ("Line citations", PROMPT_LINE_CITATIONS, parse_line_citations),
        ("Structured output", PROMPT_STRUCTURED_OUTPUT, parse_structured_output),
        ("JSON output", PROMPT_JSON_OUTPUT, parse_json_output),
        ("Fuzzy matching", PROMPT_FUZZY_MATCHING, parse_fuzzy_matching),
    ]

    # Store all results for comparison
    all_results = []

    # Test 8 combinations to cover different approaches
    test_combinations = [
        # Input strategy index, Output strategy index
        (0, 0),  # Line-numbered (arrow) + Line citations
        (0, 2),  # Line-numbered (arrow) + JSON
        (1, 0),  # Line-numbered (pipe) + Line citations
        (1, 2),  # Line-numbered (pipe) + JSON
        (3, 3),  # Plain text + Fuzzy matching
        (3, 2),  # Plain text + JSON (to see if LLM can generate line numbers)
        (2, 1),  # Structured markers + Structured output
        (2, 2),  # Structured markers + JSON
    ]

    for input_idx, output_idx in test_combinations:
        input_name, input_fn = input_strategies[input_idx]
        output_name, output_prompt, output_parser = output_strategies[output_idx]

        trial_results = []

        # Run multiple trials
        for trial in range(1, NUM_TRIALS + 1):
            try:
                response, issues = run_strategy_test(
                    input_name,
                    input_fn,
                    output_name,
                    output_prompt,
                    output_parser,
                    test_excerpt,
                    trial_num=trial,
                    model_name=None,  # Use default model
                )

                trial_results.append({
                    "trial": trial,
                    "response": response,
                    "issues_found": len(issues),
                    "issues": issues,
                })

            except Exception as e:
                print(f"Error running strategy trial {trial}: {e}")
                import traceback
                traceback.print_exc()

        # Compute statistics across trials
        issue_counts = [r["issues_found"] for r in trial_results]

        stats = {
            "input_strategy": input_name,
            "output_strategy": output_name,
            "num_trials": len(trial_results),
            "mean_issues": statistics.mean(issue_counts) if issue_counts else 0,
            "stdev_issues": statistics.stdev(issue_counts) if len(issue_counts) > 1 else 0,
            "min_issues": min(issue_counts) if issue_counts else 0,
            "max_issues": max(issue_counts) if issue_counts else 0,
            "trials": trial_results,
        }

        all_results.append(stats)

        # Print stats for this combination
        print(f"\n{'='*70}")
        print(f"{input_name} + {output_name} Statistics:")
        print(f"  Mean: {stats['mean_issues']:.2f} issues")
        print(f"  Std Dev: {stats['stdev_issues']:.2f}")
        print(f"  Range: [{stats['min_issues']}, {stats['max_issues']}]")
        print(f"{'='*70}\n")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY OF ALL STRATEGIES (sorted by mean issues found)")
    print("=" * 70)

    # Sort by mean issues found (descending)
    sorted_results = sorted(all_results, key=lambda x: x['mean_issues'], reverse=True)

    for result in sorted_results:
        print(
            f"{result['input_strategy']:25} + {result['output_strategy']:20} | "
            f"Mean: {result['mean_issues']:5.2f} ± {result['stdev_issues']:4.2f} | "
            f"Range: [{result['min_issues']:2d}, {result['max_issues']:2d}]"
        )

    # Save results to file for later analysis
    results_file = Path(__file__).parent / "strategy_test_results.json"
    with open(results_file, "w") as f:
        # Convert Issues to dicts for JSON serialization
        json_results = []
        for r in all_results:
            json_r = r.copy()
            # Convert trial issues to dicts
            json_trials = []
            for trial in r["trials"]:
                json_trial = trial.copy()
                json_trial["issues"] = [
                    {
                        "text": i.text,
                        "type": i.issue_type,
                        "explanation": i.explanation,
                        "line": i.line_number,
                        "strategy": i.strategy,
                    }
                    for i in trial["issues"]
                ]
                json_trials.append(json_trial)
            json_r["trials"] = json_trials
            json_results.append(json_r)

        json.dump(json_results, f, indent=2)

    print(f"\n\nResults saved to: {results_file}")
    print(f"Total API calls: {len(test_combinations) * NUM_TRIALS}")


if __name__ == "__main__":
    main()
