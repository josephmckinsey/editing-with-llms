"""Configuration file loading for editing-with-llms."""

import yaml
from pathlib import Path
from typing import Dict, Optional
from .models import CheckProfile, PromptConfig


def find_config_file(start_dir: Path = None, config_filename: str = ".editing-config.yaml") -> Optional[Path]:
    """Search for config file in current directory and parent directories.

    Args:
        start_dir: Directory to start search from (default: current directory)
        config_filename: Name of config file to search for

    Returns:
        Path to config file, or None if not found
    """
    if start_dir is None:
        start_dir = Path.cwd()

    current = start_dir.resolve()

    # Search up to root
    while True:
        config_path = current / config_filename
        if config_path.exists():
            return config_path

        # Stop at filesystem root
        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def load_config_file(config_path: Path) -> Dict[str, CheckProfile]:
    """Load config file and parse into CheckProfile objects.

    Args:
        config_path: Path to YAML config file

    Returns:
        Dictionary mapping profile name to CheckProfile object
    """
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "profiles" not in data:
        raise ValueError(f"Config file {config_path} must contain 'profiles' section")

    profiles = {}
    for name, profile_data in data["profiles"].items():
        profiles[name] = CheckProfile.from_dict(name, profile_data)

    return profiles


def get_default_profiles() -> Dict[str, CheckProfile]:
    """Get default profiles when no config file is found.

    Returns:
        Dictionary of default CheckProfile objects
    """
    return {
        "quick-spell": CheckProfile(
            name="quick-spell",
            checks=["typo"],
            model="openrouter/google/gemini-2.5-pro-preview",
            output_format="compiler",
            prompt_config=PromptConfig(
                scope_restriction=True,
                prioritize_precision=True,
                use_reasoning=True,
            ),
        ),
        "bachelors-reader": CheckProfile(
            name="bachelors-reader",
            reader="a Bachelor's in mathematics who mostly knows what formal verification is",
            checks=["reader", "clarity", "value"],
            model="openrouter/anthropic/claude-3.5-sonnet",
            output_format="compiler",
            prompt_config=PromptConfig(
                scope_restriction=False,  # Broader checking for reader-focused
                prioritize_precision=True,
                use_reasoning=True,
            ),
        ),
        "clarity-check": CheckProfile(
            name="clarity-check",
            checks=["clarity"],
            model="openrouter/anthropic/claude-3.5-sonnet",
            output_format="compiler",
            prompt_config=PromptConfig(
                scope_restriction=False,
                prioritize_precision=True,
                use_reasoning=True,
            ),
        ),
    }


def load_profiles(config_path: Optional[Path] = None) -> Dict[str, CheckProfile]:
    """Load profiles from config file or return defaults.

    Args:
        config_path: Optional path to config file. If None, searches for .editing-config.yaml

    Returns:
        Dictionary mapping profile name to CheckProfile object
    """
    if config_path is None:
        config_path = find_config_file()

    if config_path is None:
        return get_default_profiles()

    return load_config_file(config_path)


def get_profile(profile_name: str, config_path: Optional[Path] = None) -> CheckProfile:
    """Get a specific profile by name.

    Args:
        profile_name: Name of the profile to retrieve
        config_path: Optional path to config file

    Returns:
        CheckProfile object

    Raises:
        ValueError: If profile not found
    """
    profiles = load_profiles(config_path)

    if profile_name not in profiles:
        available = ", ".join(profiles.keys())
        raise ValueError(
            f"Profile '{profile_name}' not found. Available profiles: {available}"
        )

    return profiles[profile_name]