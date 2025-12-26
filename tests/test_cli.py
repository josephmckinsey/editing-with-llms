"""Tests for the profile-based CLI."""

import os
import tempfile
import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from editing_with_llms.cli import main


@pytest.fixture
def runner():
    """Click test runner."""
    return CliRunner()


@pytest.fixture
def sample_text():
    """Sample text with typos for testing."""
    return "The refridgerator is runnng. This sentance has a typo."


@pytest.fixture
def temp_file(sample_text):
    """Create a temporary file with sample text."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write(sample_text)
        temp_path = f.name
    yield temp_path
    if os.path.exists(temp_path):
        os.remove(temp_path)


@pytest.fixture
def mock_llm_response():
    """Mock LLM response in structured format."""
    return """TEXT: refridgerator
ISSUE: spelling error - should be "refrigerator"

TEXT: runnng
ISSUE: spelling error - should be "running"

TEXT: sentance
ISSUE: spelling error - should be "sentence"
"""


@pytest.fixture
def mock_llm_setup():
    """Setup mock LLM with common configuration."""
    with patch("editing_with_llms.cli.llm") as mock_llm:
        mock_model = MagicMock()
        mock_model.model_id = "test-model"
        mock_llm.get_model.return_value = mock_model
        yield mock_llm, mock_model


def test_list_profiles(runner):
    """Test --list-profiles flag."""
    result = runner.invoke(main, ["--list-profiles"])
    assert result.exit_code == 0
    assert "quick-spell" in result.output
    assert "bachelors-reader" in result.output


def test_dry_run(runner, temp_file):
    """Test --dry-run flag shows prompts without calling LLM."""
    result = runner.invoke(main, ["quick-spell", "--dry-run", temp_file])
    assert result.exit_code == 0
    assert "SYSTEM PROMPT:" in result.output
    assert "USER PROMPT:" in result.output
    assert "You are a proofreader" in result.output
    assert "MODEL: openrouter/google/gemini-2.5-pro-preview" in result.output


def test_basic_typo_check(runner, temp_file, mock_llm_setup, mock_llm_response):
    """Test basic typo checking with mocked LLM."""
    _, mock_model = mock_llm_setup
    mock_model.model_id = "openrouter/google/gemini-2.5-pro-preview"
    mock_model.prompt.return_value = iter([mock_llm_response])

    result = runner.invoke(main, ["quick-spell", temp_file])

    assert result.exit_code == 0
    assert ".txt:1:1: typo:" in result.output
    assert "spelling" in result.output


def test_multiple_checks(runner, temp_file, mock_llm_setup):
    """Test profile with multiple checks runs them serially."""
    _, mock_model = mock_llm_setup
    mock_model.model_id = "openrouter/anthropic/claude-3.5-sonnet"
    mock_model.prompt.side_effect = [
        iter(["TEXT: test\nISSUE: clarity issue"]),
        iter(["TEXT: test\nISSUE: reader issue"]),
        iter(["TEXT: test\nISSUE: value issue"]),
    ]

    result = runner.invoke(main, ["bachelors-reader", temp_file])

    assert result.exit_code == 0
    assert mock_model.prompt.call_count == 3


def test_no_scope_restriction(runner, temp_file, mock_llm_setup, mock_llm_response):
    """Test --no-scope-restriction flag switches to Config 98."""
    _, mock_model = mock_llm_setup
    mock_model.prompt.return_value = iter([mock_llm_response])

    result = runner.invoke(main, ["quick-spell", "--no-scope-restriction", temp_file])

    assert result.exit_code == 0


def test_model_override(runner, temp_file, mock_llm_setup, mock_llm_response):
    """Test --model flag overrides profile model."""
    mock_llm, mock_model = mock_llm_setup
    mock_model.model_id = "custom-model"
    mock_model.prompt.return_value = iter([mock_llm_response])

    result = runner.invoke(main, ["quick-spell", "--model", "custom-model", temp_file])

    assert result.exit_code == 0
    mock_llm.get_model.assert_called_with("custom-model")


def test_json_output_format(runner, temp_file, mock_llm_setup, mock_llm_response):
    """Test --output-format json."""
    _, mock_model = mock_llm_setup
    mock_model.prompt.return_value = iter([mock_llm_response])

    result = runner.invoke(main, ["quick-spell", "--output-format", "json", temp_file])

    assert result.exit_code == 0
    assert "[" in result.output and "]" in result.output


def test_missing_arguments(runner):
    """Test that missing arguments show error."""
    result = runner.invoke(main, [])
    assert result.exit_code == 1
    assert "Error:" in result.output


def test_nonexistent_profile(runner, temp_file):
    """Test error when profile doesn't exist."""
    result = runner.invoke(main, ["nonexistent-profile", temp_file])
    assert result.exit_code == 1
    assert "Error:" in result.output
    assert "not found" in result.output


@patch("editing_with_llms.cli.click.confirm")
def test_char_limit_warning(mock_confirm, runner):
    """Test character limit warning for large files."""
    # Create large file
    large_text = "a" * 60000
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write(large_text)
        temp_path = f.name

    try:
        # User declines to continue
        mock_confirm.return_value = False

        runner.invoke(main, ["quick-spell", temp_path])

        # Should have prompted
        mock_confirm.assert_called_once()

    finally:
        os.remove(temp_path)


def test_streaming_multiple_checks(runner, temp_file, mock_llm_setup):
    """Test that streaming format works with multiple checks."""
    _, mock_model = mock_llm_setup
    mock_model.prompt.side_effect = [
        iter(["Check 1 output"]),
        iter(["Check 2 output"]),
        iter(["Check 3 output"]),
    ]

    result = runner.invoke(
        main, ["bachelors-reader", "--output-format", "streaming", temp_file]
    )

    assert result.exit_code == 0
    assert mock_model.prompt.call_count == 3


def test_reasoning_enabled(runner, temp_file, mock_llm_setup, mock_llm_response):
    """Test that reasoning is enabled with effort parameter."""
    _, mock_model = mock_llm_setup
    mock_model.model_id = "openrouter/google/gemini-2.5-pro-preview"
    mock_model.prompt.return_value = iter([mock_llm_response])

    result = runner.invoke(main, ["quick-spell", temp_file])

    assert result.exit_code == 0
    call_kwargs = mock_model.prompt.call_args.kwargs
    assert "reasoning_effort" in call_kwargs
    assert call_kwargs["reasoning_effort"] == "medium"


def test_no_errors_found(runner, temp_file, mock_llm_setup):
    """Test when LLM finds no errors."""
    _, mock_model = mock_llm_setup
    mock_model.prompt.return_value = iter(["There are no errors found."])

    result = runner.invoke(main, ["quick-spell", temp_file])

    assert result.exit_code == 0
    assert "No issues found" in result.output
