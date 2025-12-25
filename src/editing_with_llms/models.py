"""Data models for editing-with-llms."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


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
    """Configuration for prompt generation"""

    scope_restriction: bool = True  # Limit to spelling/grammar/typos
    prioritize_precision: bool = True  # Aim for >80% helpful
    use_reasoning: bool = True  # Enable reasoning tokens for Gemini

    def to_dict(self) -> Dict[str, bool]:
        """Convert to dictionary for storage/display."""
        return {
            "scope_restriction": self.scope_restriction,
            "prioritize_precision": self.prioritize_precision,
            "use_reasoning": self.use_reasoning,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "PromptConfig":
        """Create PromptConfig from dictionary."""
        return PromptConfig(
            scope_restriction=data.get("scope_restriction", True),
            prioritize_precision=data.get("prioritize_precision", True),
            use_reasoning=data.get("use_reasoning", True),
        )


@dataclass
class CheckProfile:
    """Represents a named check profile from configuration."""

    name: str
    checks: List[str]  # e.g., ["typo", "clarity", "reader"]
    model: Optional[str] = None  # e.g., "openrouter/google/gemini-2.5-pro-latest"
    reader: Optional[str] = None  # Reader description for reader-focused checks
    function: Optional[str] = None  # Function description for function checks
    output_format: str = "compiler"  # "compiler", "streaming", or "json"
    custom_instructions: Optional[str] = (
        None  # Additional instructions for system prompt
    )
    prompt_config: PromptConfig = field(default_factory=PromptConfig)

    @staticmethod
    def from_dict(name: str, data: Dict[str, Any]) -> "CheckProfile":
        """Create CheckProfile from config dictionary."""
        return CheckProfile(
            name=name,
            checks=data.get("checks", ["typo"]),
            model=data.get("model"),
            reader=data.get("reader"),
            function=data.get("function"),
            output_format=data.get("output_format", "compiler"),
            custom_instructions=data.get("custom_instructions"),
            prompt_config=PromptConfig.from_dict(data.get("prompt_config", {})),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/display."""
        result = {
            "checks": self.checks,
            "output_format": self.output_format,
            "prompt_config": self.prompt_config.to_dict(),
        }
        if self.model:
            result["model"] = self.model
        if self.reader:
            result["reader"] = self.reader
        if self.function:
            result["function"] = self.function
        if self.custom_instructions:
            result["custom_instructions"] = self.custom_instructions
        return result
