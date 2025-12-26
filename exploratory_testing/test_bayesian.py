#!/usr/bin/env python3
"""
Bayesian experiment testing 128 prompt combinations (2^7 factors) for LLM-based proofreading.
Uses hierarchical Bayesian modeling with adaptive sampling.
"""

import llm
import json
import random
import re
from pathlib import Path
from typing import List, Optional, Dict
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


@dataclass
class PromptConfig:
    """Configuration for a specific prompt combination."""

    use_arrow_format: bool  # Input: True=arrow line numbers, False=plain text
    use_structured_output: bool  # Output: True=structured, False=line citations
    avoid_style: bool  # Additional direction: "Avoid commenting on style"
    scope_restriction: (
        bool  # Scope: "Do not report errors outside spelling/grammar/typos"
    )
    use_confidence: bool  # Include confidence levels and filter at 80%
    prioritize_precision: bool  # Context: "Aim for >80% helpful, prioritize precision"
    use_reasoning: bool  # Thinking: Enable reasoning tokens

    def to_dict(self) -> Dict[str, bool]:
        """Convert to dictionary for storage."""
        return {
            "arrow_format": self.use_arrow_format,
            "structured_output": self.use_structured_output,
            "avoid_style": self.avoid_style,
            "scope_restriction": self.scope_restriction,
            "use_confidence": self.use_confidence,
            "prioritize_precision": self.prioritize_precision,
            "use_reasoning": self.use_reasoning,
        }

    @staticmethod
    def from_index(index: int) -> "PromptConfig":
        """Create PromptConfig from index (0-127)."""
        # Treat index as 7-bit binary number
        return PromptConfig(
            use_arrow_format=bool(index & 1),
            use_structured_output=bool(index & 2),
            avoid_style=bool(index & 4),
            scope_restriction=bool(index & 8),
            use_confidence=bool(index & 16),
            prioritize_precision=bool(index & 32),
            use_reasoning=bool(index & 64),
        )


def generate_all_configs() -> List[PromptConfig]:
    """Generate all 128 possible prompt configurations."""
    return [PromptConfig.from_index(i) for i in range(128)]


def format_input_arrow(text: str) -> str:
    """Arrow format: prepend line numbers with arrow to each line."""
    lines = text.split("\n")
    numbered_lines = [f"{i + 1:6d}→{line}" for i, line in enumerate(lines)]
    return "\n".join(numbered_lines)


def format_input_plain(text: str) -> str:
    """Plain text format: return text as-is."""
    return text


def generate_system_prompt(config: PromptConfig) -> str:
    """Generate system prompt based on configuration."""
    base = "You are a proofreader. Carefully review the provided text for typos, spelling mistakes, and grammatical errors."

    instructions = []

    # Add scope restriction if enabled
    if config.scope_restriction:
        instructions.append(
            "Do not report perceived errors outside of spelling, grammar, or typos."
        )

    # Add style avoidance if enabled
    if config.avoid_style:
        instructions.append("Avoid commenting on style.")

    # Add precision prioritization if enabled
    if config.prioritize_precision:
        instructions.append(
            "Aim for more than 80% of your errors being helpful. Expect users to rerun later if they need to find new errors, so prioritize precision."
        )

    # Add confidence instruction if enabled
    if config.use_confidence:
        instructions.append("Focus on issues you are more confident in.")

    # Build output format section
    if config.use_structured_output:
        if config.use_arrow_format:
            # With line numbers: ask for LINE field
            output_format = """
For each issue you find, output in this format:

LINE: <line number>
TEXT: <problematic text>
ISSUE: <brief explanation>"""
        else:
            # Without line numbers: only ask for TEXT
            output_format = """
For each issue you find, output in this format:

TEXT: <problematic text>
ISSUE: <brief explanation>"""

        if config.use_confidence:
            output_format += """
CONFIDENCE: <0-100%>
SEVERITY: <low/medium/high>"""

        output_format += "\n\nExample:"

        if config.use_arrow_format:
            output_format += """
LINE: 5"""

        output_format += """
TEXT: refrigderator
ISSUE: spelling error"""

        if config.use_confidence:
            output_format += """
CONFIDENCE: 95%
SEVERITY: high"""
    else:
        # Line citations format
        if config.use_arrow_format:
            output_format = "\n\nFor each issue, cite the line number and problematic text like: Line N: [text] (explanation)"
        else:
            output_format = "\n\nFor each issue, cite the problematic text like: [text] (explanation)"

        if config.use_confidence:
            output_format += " with confidence (0-100%) and severity (low/medium/high)."

    output_format += '\n\nIf there are no errors, say "There are no errors found."'

    # Combine all parts
    full_prompt = base
    if instructions:
        full_prompt += "\n\n" + " ".join(instructions)
    full_prompt += output_format

    return full_prompt


def find_line_number(text_snippet: str, original_text: str) -> Optional[int]:
    """Find the line number where text_snippet appears in original_text."""
    lines = original_text.split("\n")
    text_snippet_lower = text_snippet.strip().lower()

    for i, line in enumerate(lines, start=1):
        if text_snippet_lower in line.lower():
            return i

    return None


def parse_structured_output(
    response: str, original_text: str, use_arrow_format: bool
) -> List[Issue]:
    """Parse structured output format."""
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

            # Get line number
            if use_arrow_format and "line" in issue_data:
                # Trust the LLM's line number when using arrow format
                line_number = int(issue_data.get("line", 0))
            else:
                # Compute line number from text snippet when using plain text
                line_number = find_line_number(
                    issue_data.get("text", ""), original_text
                )

            issues.append(
                Issue(
                    text=issue_data.get("text", ""),
                    issue_type="typo",
                    explanation=issue_data.get("issue", ""),
                    line_number=line_number,
                    confidence=confidence,
                    severity=issue_data.get("severity", "").lower(),
                )
            )

    return issues


def parse_line_citations(
    response: str, original_text: str, use_arrow_format: bool
) -> List[Issue]:
    """Parse line citations format."""
    issues = []

    if use_arrow_format:
        # Pattern: Line N: [text] (explanation) [optional: confidence X%, severity: Y]
        pattern = r"Line (\d+):\s*\[([^\]]+)\]\s*\(([^)]+)\)"

        for match in re.finditer(pattern, response, re.IGNORECASE):
            line_num = int(match.group(1))
            text = match.group(2).strip()
            explanation = match.group(3).strip()

            # Try to extract confidence and severity if present
            confidence = None
            severity = None

            remaining_text = response[match.end() :]
            conf_match = re.search(
                r"confidence[:\s]+(\d+)%?", remaining_text[:100], re.IGNORECASE
            )
            if conf_match:
                confidence = int(conf_match.group(1))

            sev_match = re.search(
                r"severity[:\s]+(low|medium|high)", remaining_text[:100], re.IGNORECASE
            )
            if sev_match:
                severity = sev_match.group(1).lower()

            issues.append(
                Issue(
                    text=text,
                    issue_type="typo",
                    explanation=explanation,
                    line_number=line_num,
                    confidence=confidence,
                    severity=severity,
                )
            )
    else:
        # Pattern without line numbers: [text] (explanation)
        pattern = r"\[([^\]]+)\]\s*\(([^)]+)\)"

        for match in re.finditer(pattern, response):
            text = match.group(1).strip()
            explanation = match.group(2).strip()

            # Compute line number from text snippet
            line_num = find_line_number(text, original_text)

            # Try to extract confidence and severity if present
            confidence = None
            severity = None

            remaining_text = response[match.end() :]
            conf_match = re.search(
                r"confidence[:\s]+(\d+)%?", remaining_text[:100], re.IGNORECASE
            )
            if conf_match:
                confidence = int(conf_match.group(1))

            sev_match = re.search(
                r"severity[:\s]+(low|medium|high)", remaining_text[:100], re.IGNORECASE
            )
            if sev_match:
                severity = sev_match.group(1).lower()

            issues.append(
                Issue(
                    text=text,
                    issue_type="typo",
                    explanation=explanation,
                    line_number=line_num,
                    confidence=confidence,
                    severity=severity,
                )
            )

    return issues


def load_ground_truth() -> Dict[str, set]:
    """Load ground truth errors from true_errors.json."""
    truth_file = Path(__file__).parent / "true_errors.json"
    with open(truth_file, "r") as f:
        data = json.load(f)

    # Extract line numbers of true errors
    true_error_lines = {error["line"] for error in data["errors"]}

    return {"true_errors": true_error_lines, "all_errors": data["errors"]}


def run_single_trial(config: PromptConfig, test_text: str, model) -> List[Issue]:
    """Run a single trial with the given configuration."""
    # Format input
    if config.use_arrow_format:
        formatted_input = format_input_arrow(test_text)
    else:
        formatted_input = format_input_plain(test_text)

    # Generate system prompt
    system_prompt = generate_system_prompt(config)

    # Prepare full prompt
    full_prompt = f"Check the following text:\n\n{formatted_input}"

    # Call LLM with appropriate options
    options = {}
    if config.use_reasoning:
        options["reasoning_max_tokens"] = 2000

    response = model.prompt(full_prompt, system=system_prompt, **options)
    response_text = "".join(chunk for chunk in response)

    # Parse output
    if config.use_structured_output:
        issues = parse_structured_output(
            response_text, test_text, config.use_arrow_format
        )
    else:
        issues = parse_line_citations(response_text, test_text, config.use_arrow_format)

    # Filter by confidence if enabled
    if config.use_confidence:
        issues = [
            issue for issue in issues if issue.confidence and issue.confidence > 80
        ]

    return issues


def phase1():
    """Run Bayesian experiment with adaptive sampling."""
    print("Bayesian Experiment: Testing 128 prompt combinations")
    print("=" * 70)

    # Load test document (first 100 lines)
    test_file = Path(__file__).parent / "test"
    with open(test_file, "r", encoding="utf-8") as f:
        test_text = f.read()
    test_excerpt = "\n".join(test_text.split("\n")[:100])

    # Load ground truth
    ground_truth = load_ground_truth()
    true_error_lines = ground_truth["true_errors"]
    print(
        f"Ground truth: {len(true_error_lines)} true errors at lines {sorted(true_error_lines)}"
    )

    # Generate all configurations
    all_configs = generate_all_configs()
    print(f"Total configurations: {len(all_configs)}")

    # Get model
    model = llm.get_model()
    print(f"Using model: {model.model_id}\n")

    # Phase 1: Initial random sampling (100 samples)
    print("Phase 1: Initial random sampling (100 samples)")
    print("-" * 70)

    results = []
    num_initial_samples = 100

    for i in range(num_initial_samples):
        # Randomly select a configuration
        config = random.choice(all_configs)
        config_index = all_configs.index(config)

        print(
            f"Sample {i + 1}/{num_initial_samples}: Config {config_index}...",
            end=" ",
            flush=True,
        )

        try:
            issues = run_single_trial(config, test_excerpt, model)

            # Record result
            detected_lines = {
                issue.line_number for issue in issues if issue.line_number
            }
            true_positives = detected_lines & true_error_lines
            false_positives = detected_lines - true_error_lines

            result = {
                "config_index": config_index,
                "config": config.to_dict(),
                "issues_found": len(issues),
                "detected_lines": list(detected_lines),
                "true_positives": list(true_positives),
                "false_positives": list(false_positives),
                "precision": len(true_positives) / len(detected_lines)
                if detected_lines
                else 0,
                "recall": len(true_positives) / len(true_error_lines)
                if true_error_lines
                else 0,
            }

            results.append(result)
            print(
                f"{len(issues)} issues, P={result['precision']:.2f}, R={result['recall']:.2f}"
            )

        except Exception as e:
            print(f"ERROR: {e}")
            import traceback

            traceback.print_exc()

    # Save initial results
    results_file = Path(__file__).parent / "bayesian_phase1.json"
    with open(results_file, "w") as f:
        json.dump(
            {"phase": 1, "num_samples": len(results), "results": results}, f, indent=2
        )

    print(f"\nPhase 1 complete. Results saved to {results_file}")
    print(f"Total samples collected: {len(results)}")

    # TODO: Phase 2 will implement PyMC Bayesian model and adaptive sampling


if __name__ == "__main__":
    phase1()
