"""Prompt generation for editing-with-llms."""

from .models import PromptConfig


def generate_system_prompt(
    check_type: str,
    prompt_config: PromptConfig,
    reader: str = None,
    function: str = None,
    custom_instructions: str = None,
) -> str:
    """Generate system prompt based on check type and Config 106 findings.

    Args:
        check_type: Type of check (typo, clarity, reader, value, function, guess-*)
        prompt_config: Config 106 settings
        reader: Reader description (for reader-focused checks)
        function: Function description (for function checks)
        custom_instructions: Additional instructions to append to system prompt

    Returns:
        System prompt string
    """
    if check_type == "typo":
        prompt = _generate_typo_prompt(prompt_config)
    elif check_type == "clarity":
        prompt = _generate_clarity_prompt(prompt_config)
    elif check_type == "reader":
        prompt = _generate_reader_prompt(prompt_config)
    elif check_type == "value":
        prompt = _generate_value_prompt(prompt_config)
    elif check_type == "function":
        prompt = _generate_function_prompt(prompt_config)
    elif check_type == "guess-function":
        prompt = _generate_guess_function_prompt()
    elif check_type == "guess-value":
        prompt = _generate_guess_value_prompt()
    elif check_type == "guess-reader":
        prompt = _generate_guess_reader_prompt()
    else:
        raise ValueError(f"Unknown check type: {check_type}")

    # Append custom instructions if provided
    if custom_instructions:
        prompt += f"\n\nAdditional user instructions: {custom_instructions}"

    return prompt


def _generate_typo_prompt(config: PromptConfig) -> str:
    """Generate typo check system prompt using Config 106 pattern."""
    base = "You are a proofreader. Carefully review the provided text for typos, spelling mistakes, and grammatical errors."

    instructions = []

    # Scope restriction (Config 106: enabled)
    if config.scope_restriction:
        instructions.append(
            "Do not report perceived errors outside of spelling, grammar, or typos."
        )

    # Prioritize precision (Config 106: enabled)
    if config.prioritize_precision:
        instructions.append(
            "Aim for more than 80% of your errors being helpful. Expect users to rerun later if they need to find new errors, so prioritize precision."
        )

    output_format = """

For each issue you find, output in this format:

TEXT: <problematic text>
ISSUE: <brief explanation>

Example:

TEXT: refrigderator
ISSUE: spelling error"""

    output_format += '\n\nIf there are no errors, say "There are no errors found."'

    # Combine all parts
    full_prompt = base
    if instructions:
        full_prompt += "\n\n" + " ".join(instructions)
    full_prompt += output_format

    return full_prompt


def _generate_clarity_prompt(config: PromptConfig) -> str:
    """Generate clarity check system prompt."""
    base = "You are a writing analyst. Carefully review the provided text for unclear sentences and confusing or ambiguous statements."

    instructions = []

    if config.prioritize_precision:
        instructions.append(
            "Aim for more than 80% of your observations being helpful. Prioritize precision."
        )

    output_format = """

For each issue you find, output in this format:

TEXT: <unclear or problematic sentence>
ISSUE: <brief explanation of why it's unclear>

If there are no unclear or confusing sentences, say "There are no unclear or confusing sentences found."
"""

    full_prompt = base
    if instructions:
        full_prompt += "\n\n" + " ".join(instructions)
    full_prompt += output_format

    return full_prompt


def _generate_reader_prompt(config: PromptConfig) -> str:
    """Generate reader accessibility check system prompt."""
    base = "You are a reading accessibility analyst. The user will describe a specific reader, and you will estimate whether that reader will struggle to understand the provided text."

    instructions = []

    if config.prioritize_precision:
        instructions.append(
            "Aim for more than 80% of your observations being helpful. Prioritize precision."
        )

    output_format = """

For each issue you find, output in this format:

TEXT: <problematic sentence or phrase>
ISSUE: <brief explanation of why it may be difficult for the described reader>

If there are no accessibility issues found for the described reader, say "There are no accessibility issues found for the described reader."
"""
    
    full_prompt = base
    if instructions:
        full_prompt += "\n\n" + " ".join(instructions)
    full_prompt += output_format

    return full_prompt


def _generate_value_prompt(config: PromptConfig) -> str:
    """Generate value check system prompt."""
    base = "You are an editor focused on gatekeeping. The user will describe a specific reader. Review the provided text and assess whether it provides clear value to that reader."

    instructions = []

    if config.prioritize_precision:
        instructions.append(
            "Aim for more than 80% of your observations being helpful. Prioritize precision."
        )

    output_format = """

For each section that lacks value, output in this format:

TEXT: <problematic sentence or section>
ISSUE: <brief explanation of why it may not be valuable for the described reader>

If the text is valuable throughout, say "The text provides value to its readers."
"""
    

    full_prompt = base
    if instructions:
        full_prompt += "\n\n" + " ".join(instructions)
    full_prompt += output_format

    return full_prompt


def _generate_function_prompt(config: PromptConfig) -> str:
    """Generate function check system prompt."""
    base = "You are a writing analyst. The user will specify the intended function of a text (e.g., inform, convince, challenge, entertain, impress, solve problems) and describe a specific reader. Carefully review the provided text and assess whether it accomplishes this function for the described reader."

    instructions = []

    if config.prioritize_precision:
        instructions.append(
            "Aim for more than 80% of your observations being helpful. Prioritize precision."
        )

    output_format = """

For each section that does not serve the intended function, output in this format:

TEXT: <problematic sentence or section>
ISSUE: <brief explanation of why it does not fulfill the intended function for that reader>

If the text fully accomplishes its function, say "The text accomplishes its intended function."
"""

    full_prompt = base
    if instructions:
        full_prompt += "\n\n" + " ".join(instructions)
    full_prompt += output_format

    return full_prompt


def _generate_guess_function_prompt() -> str:
    """Generate guess-function system prompt."""
    return """You are a writing analyst. The user will describe a specific reader. Read the following article or introduction. What do you think the main function or purpose of this text is for that reader? Suggested categories include: inform, convince, entertain, challenge, impress, solve problems. Answer with a single word and a short explanation."""


def _generate_guess_value_prompt() -> str:
    """Generate guess-value system prompt."""
    return """You are a critical reader. The user will describe a specific reader. Read the following article or introduction. What do you think the main value or benefit is for that reader? Suggested categories include: practical advice, new knowledge, entertainment, inspiration, or other. Answer with a short phrase and a brief explanation. If there is little or no value, say so and explain why."""


def _generate_guess_reader_prompt() -> str:
    """Generate guess-reader system prompt."""
    return """You are a writing analyst. Read the following article or introduction. Who do you think the intended readers are? Suggest a likely audience or reader profile (e.g., beginners, experts, business managers, children, general public, etc.) and briefly explain your reasoning. If there are multiple plausible audiences, list each one. If the intended audience is unclear, say so and explain why."""


def format_user_prompt(
    text: str, check_type: str, reader: str = None, function: str = None
) -> str:
    """Format user prompt based on check type.

    Args:
        text: The text to check
        check_type: Type of check
        reader: Reader description (for reader-focused checks)
        function: Function description (for function checks)

    Returns:
        Formatted user prompt
    """
    if check_type == "reader":
        reader_desc = reader or "a general reader"
        return f"Check the following from the perspective of {reader_desc}:\n\n{text}"
    elif check_type == "value":
        reader_desc = reader or "a general reader"
        return f"Check the following from the perspective of {reader_desc}:\n\n{text}"
    elif check_type == "function":
        reader_desc = reader or "a general reader"
        function_desc = function or "inform"
        return f"Check the following for whether it would {function_desc} {reader_desc}:\n\n{text}"
    elif check_type in ["guess-function", "guess-value"]:
        reader_desc = reader or "a general reader"
        return f"For {reader_desc}:\n\n{text}"
    elif check_type == "guess-reader":
        return text
    else:
        # typo, clarity
        return f"Check the following:\n\n{text}"