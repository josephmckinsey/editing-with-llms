#!/usr/bin/env python3
"""
Final strategy test: Arrow input + Structured output + Numeric confidence + Focus instruction
Running 50 trials to measure stability and true performance.
"""

import llm
from pathlib import Path
import json
import re
import statistics
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Issue:
    """Represents a potential writing issue found by the LLM."""

    text: str
    issue_type: str
    explanation: str
    line_number: Optional[int] = None
    confidence: Optional[int] = None  # 0-100%
    severity: Optional[str] = None


def strategy_line_numbered_arrow(text: str) -> str:
    """Arrow format: prepend line numbers with arrow to each line."""
    lines = text.split("\n")
    numbered_lines = [f"{i + 1:6d}→{line}" for i, line in enumerate(lines)]
    return "\n".join(numbered_lines)


def parse_structured_output_confidence(response: str) -> List[Issue]:
    """Parse structured output with numeric confidence."""
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
                    confidence=confidence,
                    severity=issue_data.get("severity", "").lower(),
                )
            )

    return issues


PROMPT_STRUCTURED_OUTPUT_CONFIDENCE = """You are a proofreader. Carefully review the provided text for typos, spelling mistakes, and grammatical errors.

Focus on issues you are more confident in.

For each issue you find, output in this format:

LINE: <line number>
TEXT: <problematic text>
ISSUE: <brief explanation>
CONFIDENCE: <0-100%>
SEVERITY: <low/medium/high>

Example:
LINE: 5
TEXT: refrigderator
ISSUE: spelling error
CONFIDENCE: 95%
SEVERITY: high

If there are no errors, say "There are no errors found."
"""


# Known ground truth from manual analysis
REAL_ERRORS = {74, 73, 53, 32}
FALSE_POSITIVES = {1, 49, 50, 51, 52, 63}


def main():
    """Run 50 trials of the final strategy."""
    NUM_TRIALS = 50

    # Load test document
    test_file = Path(__file__).parent / "test"
    if not test_file.exists():
        print(f"Error: Test file not found at {test_file}")
        return

    with open(test_file, "r", encoding="utf-8") as f:
        test_text = f.read()

    # Use first 100 lines
    test_excerpt = "\n".join(test_text.split("\n")[:100])

    print(f"Testing: Arrow input + Structured output + Numeric confidence + Focus")
    print(f"Running {NUM_TRIALS} trials...\n")

    trial_results = []
    model = llm.get_model()
    print(f"Using model: {model.model_id}\n")

    for trial in range(1, NUM_TRIALS + 1):
        print(f"Trial {trial}/{NUM_TRIALS}...", end=" ", flush=True)

        try:
            # Format input with arrow line numbers
            formatted_input = strategy_line_numbered_arrow(test_excerpt)
            full_prompt = f"Check the following text:\n\n{formatted_input}"

            # Call LLM
            response = model.prompt(full_prompt, system=PROMPT_STRUCTURED_OUTPUT_CONFIDENCE)
            response_text = "".join(chunk for chunk in response)

            # Parse output
            issues = parse_structured_output_confidence(response_text)

            trial_results.append({
                "trial": trial,
                "issues_found": len(issues),
                "issues": issues,
            })

            print(f"{len(issues)} issues")

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback
            traceback.print_exc()

    # Compute statistics
    issue_counts = [r["issues_found"] for r in trial_results]

    print(f"\n{'='*70}")
    print("BASIC STATISTICS")
    print(f"{'='*70}")
    print(f"Mean issues: {statistics.mean(issue_counts):.2f}")
    print(f"Std Dev: {statistics.stdev(issue_counts) if len(issue_counts) > 1 else 0:.2f}")
    print(f"Range: [{min(issue_counts)}, {max(issue_counts)}]")
    print(f"Median: {statistics.median(issue_counts):.2f}")

    # Analyze at different thresholds
    print(f"\n{'='*70}")
    print("PRECISION/RECALL AT DIFFERENT THRESHOLDS")
    print(f"{'='*70}")

    thresholds = [70, 75, 80, 85, 90, 95]

    results = []
    for threshold in thresholds:
        all_lines = set()
        for trial in trial_results:
            for issue in trial["issues"]:
                if issue.line_number and issue.confidence and issue.confidence > threshold:
                    all_lines.add(issue.line_number)

        real_hits = all_lines & REAL_ERRORS
        false_hits = all_lines & FALSE_POSITIVES
        unknown_hits = all_lines - REAL_ERRORS - FALSE_POSITIVES

        recall = len(real_hits) / len(REAL_ERRORS) if REAL_ERRORS else 0
        precision = len(real_hits) / len(all_lines) if all_lines else 0

        if recall + precision > 0:
            f1 = 2 * (precision * recall) / (precision + recall)
        else:
            f1 = 0

        results.append({
            "threshold": threshold,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "real": len(real_hits),
            "false": len(false_hits),
            "unknown": len(unknown_hits),
            "total": len(all_lines),
        })

        print(f">{threshold}%: Precision={precision*100:5.1f}% Recall={recall*100:5.0f}% F1={f1:.2f} "
              f"(Real={len(real_hits)} False={len(false_hits)} Unknown={len(unknown_hits)} Total={len(all_lines)})")

    # Find best threshold by F1
    best = max(results, key=lambda x: x["f1"])
    print(f"\nBest F1: >{best['threshold']}% (Precision={best['precision']*100:.1f}%, Recall={best['recall']*100:.0f}%, F1={best['f1']:.2f})")

    # Confidence distribution for real errors
    print(f"\n{'='*70}")
    print("CONFIDENCE DISTRIBUTION FOR REAL ERRORS")
    print(f"{'='*70}")

    for error_line in sorted(REAL_ERRORS):
        confidences = []
        for trial in trial_results:
            for issue in trial["issues"]:
                if issue.line_number == error_line and issue.confidence:
                    confidences.append(issue.confidence)

        if confidences:
            print(f"Line {error_line}: "
                  f"Found in {len(confidences)}/{NUM_TRIALS} trials, "
                  f"Confidence: min={min(confidences)} max={max(confidences)} "
                  f"mean={statistics.mean(confidences):.1f}")
        else:
            print(f"Line {error_line}: Never found")

    # Save results
    results_file = Path(__file__).parent / "final_strategy_results.json"
    with open(results_file, "w") as f:
        json_results = {
            "num_trials": NUM_TRIALS,
            "statistics": {
                "mean": statistics.mean(issue_counts),
                "stdev": statistics.stdev(issue_counts) if len(issue_counts) > 1 else 0,
                "min": min(issue_counts),
                "max": max(issue_counts),
                "median": statistics.median(issue_counts),
            },
            "threshold_analysis": results,
            "trials": [
                {
                    "trial": r["trial"],
                    "issues_found": r["issues_found"],
                    "issues": [
                        {
                            "text": i.text,
                            "explanation": i.explanation,
                            "line": i.line_number,
                            "confidence": i.confidence,
                            "severity": i.severity,
                        }
                        for i in r["issues"]
                    ],
                }
                for r in trial_results
            ],
        }
        json.dump(json_results, f, indent=2)

    print(f"\n\nResults saved to: {results_file}")
    print(f"Total API calls: {NUM_TRIALS}")


if __name__ == "__main__":
    main()
