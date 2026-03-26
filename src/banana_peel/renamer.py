"""AI-powered image renaming via vision APIs."""

from __future__ import annotations

import base64
import logging
import os
import re
import time
from pathlib import Path
from typing import Protocol

from banana_peel.config import RenameConfig

logger = logging.getLogger("banana_peel")

_PROMPT = "Describe this image in 3-5 words for use as a filename. Reply with only the description, no punctuation."

_MAX_SLUG_LENGTH = 60

_PROVIDER_ENV_VARS = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}

_DEFAULT_MODELS = {
    "gemini": "gemini-2.0-flash",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-haiku-4-5-20251001",
}

_MAX_RETRIES = 3
_RETRY_DELAYS = [1, 2, 4]


def slugify(text: str, max_length: int = _MAX_SLUG_LENGTH) -> str:
    """Convert a text description to a kebab-case filename slug.

    - Lowercase
    - Strip non-alphanumeric (except hyphens and spaces)
    - Replace spaces/underscores with hyphens
    - Collapse multiple hyphens
    - Truncate at word boundary to max_length
    """
    text = text.lower().strip()
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"[^a-z0-9\-]", "", text)
    text = re.sub(r"-+", "-", text)
    text = text.strip("-")

    if len(text) <= max_length:
        return text

    # Truncate at word boundary
    truncated = text[:max_length]
    last_hyphen = truncated.rfind("-")
    if last_hyphen > 0:
        truncated = truncated[:last_hyphen]
    return truncated.strip("-")


def _read_image_base64(image_path: Path) -> str:
    """Read an image file and return base64-encoded data."""
    return base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")


class ImageRenamer(Protocol):
    """Protocol for vision API providers."""

    def describe(self, image_path: Path) -> str:
        """Return a short description of the image content."""
        ...


class GeminiRenamer:
    """Rename images using Google's Gemini vision API."""

    def __init__(self, api_key: str, model: str = ""):
        self._api_key = api_key
        self._model = model or _DEFAULT_MODELS["gemini"]

    def describe(self, image_path: Path) -> str:
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError(
                "google-generativeai is required for Gemini renaming. "
                "Install with: pip install banana-peel[gemini]"
            )

        genai.configure(api_key=self._api_key)
        model = genai.GenerativeModel(self._model)

        image_data = image_path.read_bytes()
        response = model.generate_content(
            [
                _PROMPT,
                {"mime_type": "image/png", "data": image_data},
            ]
        )
        return response.text.strip()


class OpenAIRenamer:
    """Rename images using OpenAI's vision API."""

    def __init__(self, api_key: str, model: str = ""):
        self._api_key = api_key
        self._model = model or _DEFAULT_MODELS["openai"]

    def describe(self, image_path: Path) -> str:
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai is required for OpenAI renaming. "
                "Install with: pip install banana-peel[openai]"
            )

        client = OpenAI(api_key=self._api_key)
        b64 = _read_image_base64(image_path)

        response = client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                    ],
                }
            ],
            max_tokens=50,
        )
        return response.choices[0].message.content.strip()


class AnthropicRenamer:
    """Rename images using Anthropic's vision API."""

    def __init__(self, api_key: str, model: str = ""):
        self._api_key = api_key
        self._model = model or _DEFAULT_MODELS["anthropic"]

    def describe(self, image_path: Path) -> str:
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError(
                "anthropic is required for Anthropic renaming. "
                "Install with: pip install banana-peel[anthropic]"
            )

        client = Anthropic(api_key=self._api_key)
        b64 = _read_image_base64(image_path)

        response = client.messages.create(
            model=self._model,
            max_tokens=50,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": _PROMPT},
                    ],
                }
            ],
        )
        return response.content[0].text.strip()


_PROVIDERS: dict[str, type] = {
    "gemini": GeminiRenamer,
    "openai": OpenAIRenamer,
    "anthropic": AnthropicRenamer,
}


def _resolve_api_key(config: RenameConfig) -> str | None:
    """Resolve API key from config, then env var."""
    if config.api_key:
        return config.api_key

    env_var = _PROVIDER_ENV_VARS.get(config.provider)
    if env_var:
        return os.environ.get(env_var)

    return None


def get_renamer(config: RenameConfig) -> ImageRenamer | None:
    """Factory: returns the configured renamer, or None if disabled/unavailable."""
    if not config.enabled:
        return None

    api_key = _resolve_api_key(config)
    if not api_key:
        logger.warning(
            "AI rename enabled but no API key found. "
            "Set rename.api_key in config or %s env var.",
            _PROVIDER_ENV_VARS.get(config.provider, "PROVIDER_API_KEY"),
        )
        return None

    provider_cls = _PROVIDERS.get(config.provider)
    if provider_cls is None:
        logger.warning("Unknown rename provider: %s", config.provider)
        return None

    return provider_cls(api_key=api_key, model=config.model)


class RetryingRenamer:
    """Wraps an ImageRenamer with retry logic for rate limiting."""

    def __init__(self, inner: ImageRenamer):
        self._inner = inner

    def describe(self, image_path: Path) -> str:
        last_error: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                return self._inner.describe(image_path)
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                # Only retry on rate limits or transient server errors
                if "429" in error_str or "rate" in error_str or "500" in error_str or "503" in error_str:
                    if attempt < _MAX_RETRIES - 1:
                        delay = _RETRY_DELAYS[attempt]
                        logger.warning("Rate limited, retrying in %ds...", delay)
                        time.sleep(delay)
                        continue
                # Non-retryable error
                raise
        raise last_error  # type: ignore[misc]
