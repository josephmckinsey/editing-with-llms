"""CLI for editing-with-llms."""

import sys
import click
import llm
from pathlib import Path
from typing import Optional

from .config import get_profile, load_profiles
from .prompts import generate_system_prompt, format_user_prompt
from .parsers import parse_structured_output
from .formatters import format_issues, StreamingFormatter


@click.command()
@click.argument("profile", required=False)
@click.argument("input_file", type=click.Path(exists=True), required=False)
@click.option(
    "--config",
    type=click.Path(exists=True),
    help="Path to config file (default: search for .editing-config.yaml)",
)
@click.option("--model", help="Override profile model")
@click.option(
    "--output-format",
    type=click.Choice(["compiler", "streaming", "json"]),
    help="Override output format",
)
@click.option(
    "--no-scope-restriction",
    is_flag=True,
    help="Disable scope restriction",
)
@click.option(
    "--list-profiles",
    "list_profiles_flag",
    is_flag=True,
    help="List available profiles and exit",
)
@click.option("--dry-run", is_flag=True, help="Print prompts without calling LLM")
@click.option(
    "--char-limit",
    type=int,
    default=50000,
    help="Warn if input exceeds this many characters (default: 50000)",
)
def main(
    profile: str,
    input_file: str,
    config: Optional[str],
    model: Optional[str],
    output_format: Optional[str],
    no_scope_restriction: bool,
    list_profiles_flag: bool,
    dry_run: bool,
    char_limit: int,
):
    """Check writing with LLM-based proofreading.

    Uses named profiles from .editing-config.yaml for reproducible checking.

    Examples:
        writing-buddy quick-spell document.md
        writing-buddy bachelors-reader --model gpt-4o document.md
        writing-buddy --list-profiles
    """
    config_path = Path(config) if config else None

    # Handle --list-profiles
    if list_profiles_flag:
        profiles = load_profiles(config_path)
        click.echo("Available profiles:")
        for name, prof in profiles.items():
            checks_str = ", ".join(prof.checks)
            model_str = prof.model or "default"
            click.echo(f"  {name}: {checks_str} (model: {model_str})")
        return

    # Validate required arguments
    if not profile or not input_file:
        click.echo(
            "Error: PROFILE and INPUT_FILE are required (unless using --list-profiles)",
            err=True,
        )
        sys.exit(1)

    # Load profile
    try:
        check_profile = get_profile(profile, config_path)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Apply CLI overrides
    if model:
        check_profile.model = model
    if output_format:
        check_profile.output_format = output_format
    if no_scope_restriction:
        # Switch to no scope restriction
        check_profile.prompt_config.scope_restriction = False

    # Read input file
    input_path = Path(input_file)
    with open(input_path, "r", encoding="utf-8") as f:
        text = f.read()

    # Check character limit and warn
    if len(text) > char_limit:
        click.echo(
            f"Warning: Input file has {len(text):,} characters (limit: {char_limit:,})",
            err=True,
        )
        click.echo(
            f"This will use approximately {len(text) * len(check_profile.checks) / 1000:.1f}k tokens per check.",
            err=True,
        )
        click.echo(
            f"Running {len(check_profile.checks)} check(s) will make {len(check_profile.checks)} LLM call(s).",
            err=True,
        )
        if not click.confirm("Continue?"):
            return

    # Get model
    if check_profile.model:
        llm_model = llm.get_model(check_profile.model)
    else:
        # Get default model from llm
        llm_model = llm.get_model()

    # Dry run mode: print prompts and exit
    if dry_run:
        for check_type in check_profile.checks:
            click.echo(f"\n{'=' * 70}")
            click.echo(f"CHECK: {check_type}")
            click.echo(f"MODEL: {llm_model.model_id}")
            click.echo(f"{'=' * 70}")

            system_prompt = generate_system_prompt(
                check_type,
                check_profile.prompt_config,
                reader=check_profile.reader,
                function=check_profile.function,
                custom_instructions=check_profile.custom_instructions,
            )
            user_prompt = format_user_prompt(
                text,
                check_type,
                reader=check_profile.reader,
                function=check_profile.function,
            )

            click.echo("\nSYSTEM PROMPT:")
            click.echo(system_prompt)
            click.echo("\nUSER PROMPT:")
            click.echo(
                user_prompt[:500] + "..." if len(user_prompt) > 500 else user_prompt
            )
        return

    # Streaming format doesn't support multiple checks
    if check_profile.output_format == "streaming" and len(check_profile.checks) > 1:
        click.echo(
            "Error: Streaming format does not support multiple checks. Use compiler or json format.",
            err=True,
        )
        sys.exit(1)

    # Run all checks
    all_issues = []

    for i, check_type in enumerate(check_profile.checks):
        if len(check_profile.checks) > 1:
            click.echo(
                f"\n--- Running check {i + 1}/{len(check_profile.checks)}: {check_type} ---",
                err=True,
            )

        # Generate prompts
        system_prompt = generate_system_prompt(
            check_type,
            check_profile.prompt_config,
            reader=check_profile.reader,
            function=check_profile.function,
            custom_instructions=check_profile.custom_instructions,
        )
        user_prompt = format_user_prompt(
            text,
            check_type,
            reader=check_profile.reader,
            function=check_profile.function,
        )

        # Call LLM with reasoning tokens if using Gemini
        llm_options = {}
        if (
            check_profile.prompt_config.use_reasoning
            and "gemini" in llm_model.model_id.lower()
        ):
            llm_options["reasoning_max_tokens"] = 2000

        # Handle streaming vs compiler output
        if check_profile.output_format == "streaming":
            # Streaming format: print to console + write to output.txt
            formatter = StreamingFormatter()
            response = llm_model.prompt(
                user_prompt, system=system_prompt, **llm_options
            )
            output = formatter.format_and_stream(response)
            # Note: streaming format doesn't parse to Issues
        else:
            # Compiler/JSON format: parse response to Issues
            try:
                response = llm_model.prompt(
                    user_prompt, system=system_prompt, **llm_options
                )

                # Collect full response
                response_text = ""
                for chunk in response:
                    response_text += chunk

                # Parse response
                issues = parse_structured_output(
                    response_text,
                    text,
                    issue_type=check_type,
                )

                all_issues.extend(issues)

            except Exception as e:
                click.echo(f"Error during {check_type} check: {e}", err=True)
                sys.exit(1)

    # Format and output all issues (for compiler/JSON format)
    if check_profile.output_format != "streaming":
        output = format_issues(all_issues, input_path.name, check_profile.output_format)

        # Print to stdout
        if output:
            click.echo(output)
        else:
            click.echo("No issues found.")


if __name__ == "__main__":
    main()
