import click
import llm

TYPO_SYSTEM_PROMPT = """You are a proofreader. Carefully review the provided text for typos, spelling mistakes, and grammatical errors. For each issue you find, write a line with the offending text in square brackets as shown below. Never try and correct an error yourself. If there are no errors, say "There are no errors found."

Example:

    User: Check the following:

    Oh no, my refridgerator is runnng! Why does it always have to end Like that?

    You: 
    - ...my [refrigderator] is [runng]!
    - ...end [Like] that?
"""

UNCLEAR_SYSTEM_PROMPT = """You are a writing analyst. Carefully review the provided text for unclear sentences and confusing or ambiguous statements. For each issue you find, write a line with the unclear or problematic sentence in square brackets as shown below. Do not attempt to rewrite or clarify the sentence yourself. If there are no unclear or confusing sentences, say "There are no unclear or confusing sentences found."

Example:

    User: Check the following:

    The team met to discuss the project timeline and assigned tasks to each member. The process was completed, but the results, which were unexpected, led to further questions about the initial assumptions and the overall direction, making it difficult to determine the next steps. Everyone agreed to meet again next week to review progress.

    You:
    - [The process was completed, but the results, which were unexpected, led to further questions about the initial assumptions and the overall direction, making it difficult to determine the next steps.]
"""

READER_SYSTEM_PROMPT = """You are a reading accessibility analyst. The user will describe a specific reader, and you will estimate whether that reader will struggle to understand the provided text. For each issue you find, write a line with the problematic sentence or phrase in square brackets, and briefly explain why it may be difficult for the described reader. If there are no issues, say 'There are no accessibility issues found for the described reader.'

Example:

    User: Check the following for a mathematician who knows some programming:

    How can we handle both state and error handling in a Haskell program? The solution uses a monad transformer stack to manage side effects in a lazy functional language.

    You:
    - [The solution uses a monad transformer stack to manage side effects in a lazy functional language.] (This sentence uses advanced functional programming terminology that may not be familiar to a mathematician with only some programming experience.)
"""


VALUE_SYSTEM_PROMPT = """You are an editor focused on gatekeeping. The user will describe a specific reader. Review the provided text and assess whether it provides clear value to that reader. For each section that lacks value, write a line with the problematic sentence or section in square brackets, and briefly explain why it may not be valuable for the described reader. If the text is valuable throughout, say "The text provides value to its readers."

Example:

    User: Check the following from the perspective of a beginner Python programmer:

    Python is a versatile programming language that is widely used in web development, data science, and automation. Its simple syntax makes it accessible to newcomers, and there is a large community that provides support and resources. I spent several months researching the history of Python before writing this article.

    You:
    - [I spent several months researching the history of Python before writing this article.] (This information about the writer's process does not provide practical value to a beginner Python programmer.)
"""

FUNCTION_SYSTEM_PROMPT = """You are an writing analyst. The user will specify the intended function of a text (e.g., inform, convince, challenge, entertain, impress, solve problems) and describe a specific reader. Carefully review the provided text and assess whether it accomplishes this function for the described reader. For each section that does not serve the intended function, write a line with the problematic sentence or section in square brackets, and briefly explain why it does not fulfill the intended function for that reader. If the text fully accomplishes its function, say "The text accomplishes its intended function."

Example:

    User: Check the following for whether it would convince a business manager:

    Our new software solution has reduced operational costs by 30% for several Fortune 500 companies. It integrates seamlessly with existing workflows and offers 24/7 customer support. I chose to write about this product because I find its technical architecture fascinating.

    You:
    - [I chose to write about this product because I find its technical architecture fascinating.] (This sentence focuses on the writer's interest rather than convincing a business manager to adopt the software.)
"""

GUESS_FUNCTION_SYSTEM_PROMPT = """You are a writing analyst. The user will describe a specific reader. Read the following article or introduction. What do you think the main function or purpose of this text is for that reader? Suggested categories include: inform, convince, entertain, challenge, impress, solve problems. Answer with a single word and a short explanation."""

GUESS_VALUE_SYSTEM_PROMPT = """You are a critical reader. The user will describe a specific reader. Read the following article or introduction. What do you think the main value or benefit is for that reader? Suggested categories include: practical advice, new knowledge, entertainment, inspiration, or other. Answer with a short phrase and a brief explanation. If there is little or no value, say so and explain why."""

GUESS_READER_SYSTEM_PROMPT = """You are a writing analyst. Read the following article or introduction. Who do you think the intended readers are? Suggest a likely audience or reader profile (e.g., beginners, experts, business managers, children, general public, etc.) and briefly explain your reasoning. If there are multiple plausible audiences, list each one. If the intended audience is unclear, say so and explain why."""


@click.command()
@click.option(
    "--check",
    type=click.Choice(
        [
            "typo",
            "clarity",
            "reader",
            "value",
            "function",
            "guess-function",
            "guess-value",
            "guess-reader",
        ],
        case_sensitive=False,
    ),
    default="typo",
    show_default=True,
    help="Type of check to perform: 'typo' (default), 'clarity', 'reader', 'value', 'function', 'guess-function', 'guess-value', or 'guess-reader'",
)
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--model", default=None, help="Model name or alias to use with llm")
@click.option(
    "--reader",
    default=None,
    help="Describe the intended reader for the 'reader', 'value', or 'function' check.",
)
@click.option(
    "--function",
    default=None,
    help="Describe the intended function for the 'function' check (e.g., inform, convince, entertain, etc.).",
)
def main(check, input_file, model, reader, function):
    """Check for typos/grammar, clarity, reader accessibility, value, or function in the given text file using the llm tool as a Python library."""
    # Read the input file
    with open(input_file, "r", encoding="utf-8") as f:
        prompt = f.read()

    # Select system prompt
    if check == "clarity":
        system_prompt = UNCLEAR_SYSTEM_PROMPT
    elif check == "reader":
        system_prompt = READER_SYSTEM_PROMPT
    elif check == "value":
        system_prompt = VALUE_SYSTEM_PROMPT
    elif check == "function":
        system_prompt = FUNCTION_SYSTEM_PROMPT
    elif check == "guess-function":
        system_prompt = GUESS_FUNCTION_SYSTEM_PROMPT
    elif check == "guess-value":
        system_prompt = GUESS_VALUE_SYSTEM_PROMPT
    elif check == "guess-reader":
        system_prompt = GUESS_READER_SYSTEM_PROMPT
    else:
        system_prompt = TYPO_SYSTEM_PROMPT

    # Compose prompt
    if check == "reader":
        reader_desc = reader or "a general reader"
        prompt_text = (
            f"Check the following from the perspective of {reader_desc}:\n\n" + prompt
        )
    elif check == "value":
        reader_desc = reader or "a general reader"
        prompt_text = (
            f"Check the following from the perspective of {reader_desc}:\n\n" + prompt
        )
    elif check == "function":
        reader_desc = reader or "a general reader"
        function_desc = function or "inform"
        prompt_text = (
            f"Check the following for whether it would {function_desc} {reader_desc}:\n\n"
            + prompt
        )
    elif check == "guess-function":
        reader_desc = reader or "a general reader"
        prompt_text = f"For {reader_desc}:\n\n" + prompt
    elif check == "guess-value":
        reader_desc = reader or "a general reader"
        prompt_text = f"For {reader_desc}:\n\n" + prompt
    elif check == "guess-reader":
        prompt_text = prompt
    else:
        prompt_text = "Check the following:\n\n" + prompt

    # Use llm Python API
    llm_model = llm.get_model(model) if model else llm.get_model()
    response = llm_model.prompt(prompt_text, system=system_prompt)
    output_chunks = []
    for chunk in response:
        print(chunk, end="", flush=True)
        output_chunks.append(chunk)
    output = "".join(output_chunks)

    # Output to file
    output_file = "output.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output)
    print(f"\nResults written to {output_file}")


if __name__ == "__main__":
    main()
