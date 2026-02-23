"""LLM configuration for CrewAI agents.

Supports multiple LLM providers with fallback:
1. GROQ (preferred) - openai/gpt-oss-120b via GROQ_API_KEY
2. Claude Opus (fallback) - claude-opus-4-5 via ANTHROPIC_API_KEY

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

import os
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_groq import ChatGroq


def get_llm_for_crew() -> Any:
    """Get configured LLM for CrewAI agents.

    Checks environment variables in order of preference:
    1. GROQ_API_KEY - Uses GROQ with openai/gpt-oss-120b model
    2. ANTHROPIC_API_KEY - Uses Claude Opus 4.5 as fallback

    Returns:
        Configured LangChain LLM instance

    Raises:
        ValueError: If no valid API key is found

    Environment Variables:
        GROQ_API_KEY: API key for GROQ (https://console.groq.com/)
        ANTHROPIC_API_KEY: API key for Anthropic Claude
        LLM_TEMPERATURE: Temperature for generation (default: 0.1 for accuracy)
        LLM_MAX_TOKENS: Maximum tokens in response (default: 4096)
    """
    # Get common configuration
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "4096"))

    # Try GROQ first (preferred for cost/speed)
    groq_api_key: str | None = os.getenv("GROQ_API_KEY")
    if groq_api_key:
        print("Using GROQ LLM provider (openai/gpt-oss-120b)")
        llm: Any = ChatGroq(  # type: ignore[call-arg]
            groq_api_key=groq_api_key,
            model_name="openai/gpt-oss-120b",
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return llm

    # Fallback to Claude Opus
    anthropic_api_key: str | None = os.getenv("ANTHROPIC_API_KEY")
    if anthropic_api_key:
        print("Using Claude Opus LLM provider (claude-opus-4-5)")
        return ChatAnthropic(  # type: ignore[call-arg]
            anthropic_api_key=anthropic_api_key,
            model="claude-opus-4-5-20251101",
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # No valid API key found
    raise ValueError(
        "No LLM provider configured. Set either GROQ_API_KEY or ANTHROPIC_API_KEY "
        "environment variable."
    )


def get_llm_provider_name() -> str:
    """Get the name of the currently configured LLM provider.

    Returns:
        Provider name: "groq", "anthropic", or "none"

    Used for logging and diagnostics.
    """
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "none"


def validate_llm_config() -> dict[str, Any]:
    """Validate LLM configuration and return status.

    Returns:
        Dictionary with validation results:
        - provider: Name of configured provider
        - configured: Boolean indicating if LLM is configured
        - model: Model name being used
        - error: Error message if validation failed

    Used for health checks and startup validation.
    """
    provider: str = get_llm_provider_name()

    if provider == "groq":
        return {
            "provider": "groq",
            "configured": True,
            "model": "openai/gpt-oss-120b",
            "error": None,
        }

    if provider == "anthropic":
        return {
            "provider": "anthropic",
            "configured": True,
            "model": "claude-opus-4-5-20251101",
            "error": None,
        }

    return {
        "provider": "none",
        "configured": False,
        "model": None,
        "error": "No LLM API key configured (GROQ_API_KEY or ANTHROPIC_API_KEY)",
    }
