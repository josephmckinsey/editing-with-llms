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
    confidence: Optional[int | str] = None  # Numeric (0-100%) or categorical (unsure/likely/very likely/certain)
    severity: Optional[str] = None  # low/medium/high (if requested)


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
    numbered_lines = [f"{i + 1:6d}→{line}" for i, line in enumerate(lines)]
    return "\n".join(numbered_lines)


def strategy_line_numbered_arrow_padded(text: str) -> str:
    """
    Strategy 1a-padded: Arrow format but padded with spaces to match token count of structured markers.

    This tests the hypothesis that token count (not structure) drives performance.
    Arrow overhead: ~7-8 chars
    Structured overhead: ~19-20 chars (<line n="N">...</line>)
    Difference: ~12 chars, so we add 12 trailing spaces per line.

    Example:
         1→First line
         2→Second line
    """
    lines = text.split("\n")
    # Padding to match structured markers overhead
    # <line n="N"> = 12 chars (for single digit N), </line> = 7 chars = ~19 total
    # Arrow format "     N→" = ~7 chars, difference ~12 chars
    PADDING = "            "  # 12 spaces
    numbered_lines = [f"{i + 1:6d}→{line}{PADDING}" for i, line in enumerate(lines)]
    return "\n".join(numbered_lines)


def strategy_line_numbered_pipe(text: str) -> str:
    """
    Strategy 1b: Prepend line numbers with pipe to each line.

    Example:
         1 | First line
         2 | Second line
    """
    lines = text.split("\n")
    numbered_lines = [f"{i + 1:6d} | {line}" for i, line in enumerate(lines)]
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
    marked_lines = ["<document>"]
    for i, line in enumerate(lines, 1):
        marked_lines.append(f'<line n="{i}">{line}</line>')
    marked_lines.append("</document>")
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


def parse_structured_output_categorical(
    response: str, original_text: str
) -> List[Issue]:
    """
    Parse structured output with categorical confidence and severity.

    Format:
        LINE: 5
        TEXT: text
        ISSUE: explanation
        CONFIDENCE: certain
        SEVERITY: high
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

        if "line" in issue_data and "text" in issue_data:
            # Extract categorical confidence
            confidence_str = issue_data.get("confidence", "").strip().lower()

            issues.append(
                Issue(
                    text=issue_data.get("text", ""),
                    issue_type="typo",
                    explanation=issue_data.get("issue", ""),
                    line_number=int(issue_data.get("line", 0)),
                    strategy="structured_output_categorical",
                    confidence=confidence_str,
                    severity=issue_data.get("severity", "").lower(),
                )
            )

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
# PARSERS WITH CONFIDENCE/SEVERITY
# ============================================================================


def parse_line_citations_confidence(response: str, original_text: str) -> List[Issue]:
    """
    Parse line citations with confidence and severity.

    Format: Line 5: [text] (explanation) | Confidence: 95% | Severity: high
    """
    issues = []
    # Match pattern with confidence and severity
    pattern = r"[Ll]ine\s+(\d+).*?\[([^\]]+)\].*?\|\s*Confidence:\s*(\d+)%\s*\|\s*Severity:\s*(\w+)"
    matches = re.finditer(pattern, response)

    for match in matches:
        line_num = int(match.group(1))
        text = match.group(2)
        confidence = int(match.group(3))
        severity = match.group(4).lower()

        issues.append(
            Issue(
                text=text,
                issue_type="typo",
                explanation="Found via line citation",
                line_number=line_num,
                strategy="line_citations_confidence",
                confidence=confidence,
                severity=severity,
            )
        )

    return issues


def parse_line_citations_categorical(response: str, original_text: str) -> List[Issue]:
    """
    Parse line citations with categorical confidence and severity.

    Format: Line 5: [text] (explanation) | Confidence: certain | Severity: high
    """
    issues = []
    # Match pattern with categorical confidence
    # Confidence can be: unsure, likely, very likely, certain
    pattern = r"[Ll]ine\s+(\d+).*?\[([^\]]+)\].*?\|\s*Confidence:\s*([a-z\s]+?)\s*\|\s*Severity:\s*(\w+)"
    matches = re.finditer(pattern, response)

    for match in matches:
        line_num = int(match.group(1))
        text = match.group(2)
        confidence = match.group(3).strip().lower()
        severity = match.group(4).lower()

        issues.append(
            Issue(
                text=text,
                issue_type="typo",
                explanation="Found via line citation",
                line_number=line_num,
                strategy="line_citations_categorical",
                confidence=confidence,
                severity=severity,
            )
        )

    return issues


def parse_structured_output_confidence(
    response: str, original_text: str
) -> List[Issue]:
    """
    Parse structured output with confidence and severity.

    Format:
        LINE: 5
        TEXT: text
        ISSUE: explanation
        CONFIDENCE: 95%
        SEVERITY: high
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

        if "line" in issue_data and "text" in issue_data:
            # Extract confidence (handle both "95%" and "95" formats)
            confidence_str = issue_data.get("confidence", "0%")
            confidence = (
                int(re.search(r"\d+", confidence_str).group())
                if re.search(r"\d+", confidence_str)
                else 0
            )

            issues.append(
                Issue(
                    text=issue_data.get("text", ""),
                    issue_type="typo",
                    explanation=issue_data.get("issue", ""),
                    line_number=int(issue_data.get("line", 0)),
                    strategy="structured_output_confidence",
                    confidence=confidence,
                    severity=issue_data.get("severity", "").lower(),
                )
            )

    return issues


# ============================================================================
# CONFIDENCE/SEVERITY PROMPTS
# ============================================================================

PROMPT_LINE_CITATIONS_CONFIDENCE_4LEVEL = """You are a proofreader. Carefully review the provided text for typos, spelling mistakes, and grammatical errors.

Focus on issues you are more confident in.

For each issue you find, cite it with:
- Line number
- Problematic text in square brackets
- Brief explanation
- Confidence: unsure/likely/very likely/certain
- Severity: low/medium/high

Format:
    - Line 5: [refrigderator] (spelling error) | Confidence: certain | Severity: high
    - Line 10: [runng] (spelling error) | Confidence: very likely | Severity: medium

If there are no errors, say "There are no errors found."
"""

PROMPT_LINE_CITATIONS_CONFIDENCE_3LEVEL = """You are a proofreader. Carefully review the provided text for typos, spelling mistakes, and grammatical errors.

Focus on issues you are more confident in.

For each issue you find, cite it with:
- Line number
- Problematic text in square brackets
- Brief explanation
- Confidence: likely/very likely/certain
- Severity: low/medium/high

Format:
    - Line 5: [refrigderator] (spelling error) | Confidence: certain | Severity: high
    - Line 10: [runng] (spelling error) | Confidence: very likely | Severity: medium

If there are no errors, say "There are no errors found."
"""

PROMPT_STRUCTURED_OUTPUT_CONFIDENCE_4LEVEL = """You are a proofreader. Carefully review the provided text for typos, spelling mistakes, and grammatical errors.

Focus on issues you are more confident in.

For each issue you find, output in this format:

LINE: <line number>
TEXT: <problematic text>
ISSUE: <brief explanation>
CONFIDENCE: <unsure/likely/very likely/certain>
SEVERITY: <low/medium/high>

Example:
LINE: 5
TEXT: refrigderator
ISSUE: spelling error
CONFIDENCE: certain
SEVERITY: high

If there are no errors, say "There are no errors found."
"""

PROMPT_STRUCTURED_OUTPUT_CONFIDENCE_3LEVEL = """You are a proofreader. Carefully review the provided text for typos, spelling mistakes, and grammatical errors.

Focus on issues you are more confident in.

For each issue you find, output in this format:

LINE: <line number>
TEXT: <problematic text>
ISSUE: <brief explanation>
CONFIDENCE: <likely/very likely/certain>
SEVERITY: <low/medium/high>

Example:
LINE: 5
TEXT: refrigderator
ISSUE: spelling error
CONFIDENCE: certain
SEVERITY: high

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
        f"\n{'=' * 70}\nTesting: {input_strategy_name} + {output_strategy_name} (Trial {trial_num})\n{'=' * 70}"
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

    # Known real errors and false positives from Experiment 1
    REAL_ERRORS = {74, 73, 53, 32}
    FALSE_POSITIVES = {1, 49, 50, 51, 52, 63}

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

    print(
        f"Test document: {len(test_excerpt)} characters, {len(test_excerpt.split(chr(10)))} lines"
    )
    print(f"First 200 chars: {test_excerpt[:200]}...")
    print(f"\nRunning {NUM_TRIALS} trials per strategy combination...\n")

    # Store all results for comparison
    all_results = []

    # Test 4 combinations: Categorical confidence scales (3-level vs 4-level)
    # Testing: unsure/likely/very likely/certain vs likely/very likely/certain
    test_combinations = [
        # (input_name, input_fn, output_name, prompt, parser, confidence_levels)
        (
            "Arrow",
            strategy_line_numbered_arrow,
            "Structured",
            PROMPT_STRUCTURED_OUTPUT_CONFIDENCE_4LEVEL,
            parse_structured_output_categorical,
            "4-level",
        ),
        (
            "Arrow",
            strategy_line_numbered_arrow,
            "Structured",
            PROMPT_STRUCTURED_OUTPUT_CONFIDENCE_3LEVEL,
            parse_structured_output_categorical,
            "3-level",
        ),
        (
            "Arrow",
            strategy_line_numbered_arrow,
            "Line citations",
            PROMPT_LINE_CITATIONS_CONFIDENCE_4LEVEL,
            parse_line_citations_categorical,
            "4-level",
        ),
        (
            "Arrow",
            strategy_line_numbered_arrow,
            "Line citations",
            PROMPT_LINE_CITATIONS_CONFIDENCE_3LEVEL,
            parse_line_citations_categorical,
            "3-level",
        ),
    ]

    # Categorical confidence levels for filtering
    # 4-level: unsure < likely < very likely < certain
    # 3-level: likely < very likely < certain
    CONFIDENCE_FILTERS = {
        "4-level": [["very likely", "certain"], ["certain"]],  # Filter to 2+ or 3+ levels
        "3-level": [["very likely", "certain"], ["certain"]],  # Filter to 2+ or 3 levels
    }

    for (
        input_name,
        input_fn,
        output_name,
        output_prompt,
        output_parser,
        confidence_levels,
    ) in test_combinations:
        trial_results = []

        strategy_label = f"{input_name} + {output_name} ({confidence_levels})"

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

                # Store all issues (we'll filter at different thresholds during analysis)
                trial_results.append(
                    {
                        "trial": trial,
                        "response": response,
                        "issues_found": len(issues),
                        "issues": issues,
                    }
                )

            except Exception as e:
                print(f"Error running strategy trial {trial}: {e}")
                import traceback

                traceback.print_exc()

        # Compute statistics across trials
        issue_counts = [r["issues_found"] for r in trial_results]

        stats = {
            "input_strategy": input_name,
            "output_strategy": output_name,
            "confidence_levels": confidence_levels,
            "num_trials": len(trial_results),
            "mean_issues": statistics.mean(issue_counts) if issue_counts else 0,
            "stdev_issues": statistics.stdev(issue_counts)
            if len(issue_counts) > 1
            else 0,
            "min_issues": min(issue_counts) if issue_counts else 0,
            "max_issues": max(issue_counts) if issue_counts else 0,
            "trials": trial_results,
        }

        all_results.append(stats)

        # Print stats for this combination
        print(f"\n{'=' * 70}")
        print(f"{strategy_label} Statistics:")
        print(f"  Mean: {stats['mean_issues']:.2f} issues")
        print(f"  Std Dev: {stats['stdev_issues']:.2f}")
        print(f"  Range: [{stats['min_issues']}, {stats['max_issues']}]")
        print(f"{'=' * 70}\n")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY OF ALL STRATEGIES (sorted by mean issues found)")
    print("=" * 70)

    # Sort by mean issues found (descending)
    sorted_results = sorted(all_results, key=lambda x: x["mean_issues"], reverse=True)

    for result in sorted_results:
        conf_label = f" ({result['confidence_levels']})"
        print(
            f"{result['input_strategy']:15} + {result['output_strategy']:15}{conf_label:10} | "
            f"Mean: {result['mean_issues']:5.2f} ± {result['stdev_issues']:4.2f} | "
            f"Range: [{result['min_issues']:2d}, {result['max_issues']:2d}]"
        )

    # Precision/Recall Analysis at Multiple Thresholds
    print("\n" + "=" * 80)
    print("PRECISION/RECALL ANALYSIS (comparing to known errors)")
    print("=" * 80)

    quality_scores = []

    def compute_quality_metrics(strategy, allowed_levels=None):
        """Compute quality metrics for a strategy, optionally filtering by confidence levels."""
        all_lines = set()
        for trial in strategy["trials"]:
            for issue in trial["issues"]:
                if issue.line_number:
                    # Filter by categorical confidence if specified
                    if allowed_levels is not None:
                        if isinstance(issue.confidence, str) and issue.confidence in allowed_levels:
                            all_lines.add(issue.line_number)
                    else:
                        # No filtering - include all
                        all_lines.add(issue.line_number)

        # Categorize
        real_hits = all_lines & REAL_ERRORS
        false_hits = all_lines & FALSE_POSITIVES
        unknown_hits = all_lines - REAL_ERRORS - FALSE_POSITIVES

        # Calculate metrics
        recall = len(real_hits) / len(REAL_ERRORS) if REAL_ERRORS else 0
        precision = len(real_hits) / len(all_lines) if all_lines else 0

        # F1 score
        if recall + precision > 0:
            f1 = 2 * (precision * recall) / (precision + recall)
        else:
            f1 = 0

        return {
            "recall": recall,
            "precision": precision,
            "f1": f1,
            "real": len(real_hits),
            "false": len(false_hits),
            "unknown": len(unknown_hits),
            "total_flagged": len(all_lines),
        }

    for strategy in all_results:
        base_name = f"{strategy['input_strategy']} + {strategy['output_strategy']}"
        levels = strategy["confidence_levels"]

        # No filter (all levels)
        metrics = compute_quality_metrics(strategy, None)
        quality_scores.append(
            {
                "name": f"{base_name} ({levels}, all)",
                "filter": "all",
                "confidence_levels": levels,
                "base_name": base_name,
                **metrics,
            }
        )

        # Filter to higher confidence levels
        for filter_set in CONFIDENCE_FILTERS[levels]:
            filter_label = "+".join(filter_set)
            metrics = compute_quality_metrics(strategy, filter_set)
            quality_scores.append(
                {
                    "name": f"{base_name} ({levels}, {filter_label})",
                    "filter": filter_label,
                    "confidence_levels": levels,
                    "base_name": base_name,
                    **metrics,
                }
            )

    # Sort by F1 score
    quality_scores.sort(key=lambda x: x["f1"], reverse=True)

    print(f"\n{'Strategy':50} | Recall | Prec | F1   | Real | False | Unk | Total")
    print("-" * 105)
    for s in quality_scores:
        print(
            f"{s['name']:50} | {s['recall'] * 100:5.0f}% | {s['precision'] * 100:4.0f}% | "
            f"{s['f1']:.2f} | {s['real']:4d} | {s['false']:5d} | {s['unknown']:3d} | {s['total_flagged']:5d}"
        )

    # Filter Comparison for Categorical Confidence
    print("\n" + "=" * 100)
    print(
        "FILTER COMPARISON (showing how precision/recall change with confidence filtering)"
    )
    print("=" * 100)

    # Group by base strategy name and confidence levels
    filter_groups = {}
    for s in quality_scores:
        key = (s["base_name"], s["confidence_levels"])
        if key not in filter_groups:
            filter_groups[key] = []
        filter_groups[key].append(s)

    for (base_name, levels) in sorted(filter_groups.keys()):
        variants = filter_groups[(base_name, levels)]

        # Find baseline (all levels)
        baseline = next((v for v in variants if v["filter"] == "all"), None)
        filtered_variants = [v for v in variants if v["filter"] != "all"]

        if baseline:
            print(f"\n{base_name} ({levels}):")
            print(
                f"  {'Filter':30} | Precision | Recall | F1   | Total | ΔPrec | ΔRecall"
            )
            print(f"  {'-' * 85}")

            # Print baseline
            print(
                f"  {'All levels (no filter)':30} | {baseline['precision'] * 100:8.1f}% | {baseline['recall'] * 100:5.0f}% | "
                f"{baseline['f1']:.2f} | {baseline['total_flagged']:5d} |   -   |    -"
            )

            # Print filtered variants
            for variant in filtered_variants:
                delta_prec = variant["precision"] - baseline["precision"]
                delta_recall = variant["recall"] - baseline["recall"]
                filter_name = f"Only: {variant['filter']}"
                print(
                    f"  {filter_name:30} | {variant['precision'] * 100:8.1f}% | {variant['recall'] * 100:5.0f}% | "
                    f"{variant['f1']:.2f} | {variant['total_flagged']:5d} | {delta_prec * 100:+5.1f}% | {delta_recall * 100:+7.0f}%"
                )

    # Save results to file for later analysis
    results_file = Path(__file__).parent / "confidence_test_results.json"
    with open(results_file, "w") as f:
        # Convert Issues to dicts for JSON serialization
        json_results = []
        for r in all_results:
            json_r = r.copy()
            # Convert trial issues to dicts
            json_trials = []
            for trial in r["trials"]:
                json_trial = trial.copy()
                # Convert issues to dict
                json_trial["issues"] = [
                    {
                        "text": i.text,
                        "type": i.issue_type,
                        "explanation": i.explanation,
                        "line": i.line_number,
                        "strategy": i.strategy,
                        "confidence": i.confidence,
                        "severity": i.severity,
                    }
                    for i in trial["issues"]
                ]
                json_trials.append(json_trial)
            json_r["trials"] = json_trials
            json_results.append(json_r)

        # Also save quality analysis
        output = {
            "results": json_results,
            "quality_analysis": quality_scores,
            "known_real_errors": list(REAL_ERRORS),
            "known_false_positives": list(FALSE_POSITIVES),
        }

        json.dump(output, f, indent=2)

    print(f"\n\nResults saved to: {results_file}")
    print(f"Total API calls: {len(test_combinations) * NUM_TRIALS}")


if __name__ == "__main__":
    main()
