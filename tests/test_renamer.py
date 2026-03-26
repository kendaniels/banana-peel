"""Tests for the AI renamer module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from banana_peel.config import RenameConfig
from banana_peel.renamer import (
    RetryingRenamer,
    _resolve_api_key,
    get_renamer,
    slugify,
)


class TestSlugify:
    def test_simple(self):
        assert slugify("Steak Dinner") == "steak-dinner"

    def test_punctuation_stripped(self):
        assert slugify("A beautiful sunset!") == "a-beautiful-sunset"

    def test_multiple_spaces(self):
        assert slugify("red   sports   car") == "red-sports-car"

    def test_underscores_to_hyphens(self):
        assert slugify("golden_gate_bridge") == "golden-gate-bridge"

    def test_unicode_stripped(self):
        assert slugify("caf\u00e9 latte art") == "caf-latte-art"

    def test_leading_trailing_hyphens(self):
        assert slugify("--hello world--") == "hello-world"

    def test_empty_string(self):
        assert slugify("") == ""

    def test_truncation_at_word_boundary(self):
        long_text = "a beautiful sunset over the pacific ocean with vibrant orange and pink hues"
        result = slugify(long_text, max_length=40)
        assert len(result) <= 40
        assert not result.endswith("-")
        assert result == "a-beautiful-sunset-over-the-pacific"

    def test_truncation_no_hyphen(self):
        result = slugify("superlongwordwithoutanyspaces", max_length=10)
        assert result == "superlongw"

    def test_max_length_exact(self):
        result = slugify("short", max_length=60)
        assert result == "short"

    def test_numbers_preserved(self):
        assert slugify("747 airplane") == "747-airplane"


class TestResolveApiKey:
    def test_config_key_preferred(self):
        config = RenameConfig(enabled=True, provider="gemini", api_key="my-key")
        assert _resolve_api_key(config) == "my-key"

    def test_env_var_fallback(self):
        config = RenameConfig(enabled=True, provider="openai", api_key="")
        with patch.dict("os.environ", {"OPENAI_API_KEY": "env-key"}):
            assert _resolve_api_key(config) == "env-key"

    def test_no_key_returns_none(self):
        config = RenameConfig(enabled=True, provider="gemini", api_key="")
        with patch.dict("os.environ", {}, clear=True):
            assert _resolve_api_key(config) is None


class TestGetRenamer:
    def test_disabled_returns_none(self):
        config = RenameConfig(enabled=False)
        assert get_renamer(config) is None

    def test_no_key_returns_none(self):
        config = RenameConfig(enabled=True, provider="gemini", api_key="")
        with patch.dict("os.environ", {}, clear=True):
            assert get_renamer(config) is None

    def test_unknown_provider_returns_none(self):
        config = RenameConfig(enabled=True, provider="unknown", api_key="key")
        assert get_renamer(config) is None

    def test_valid_config_returns_renamer(self):
        config = RenameConfig(enabled=True, provider="gemini", api_key="key")
        renamer = get_renamer(config)
        assert renamer is not None


class TestRetryingRenamer:
    def test_success_first_try(self):
        inner = MagicMock()
        inner.describe.return_value = "steak dinner"
        renamer = RetryingRenamer(inner)
        result = renamer.describe(Path("test.png"))
        assert result == "steak dinner"
        assert inner.describe.call_count == 1

    def test_retries_on_rate_limit(self):
        inner = MagicMock()
        inner.describe.side_effect = [
            Exception("429 rate limit"),
            "steak dinner",
        ]
        renamer = RetryingRenamer(inner)
        with patch("banana_peel.renamer.time.sleep"):
            result = renamer.describe(Path("test.png"))
        assert result == "steak dinner"
        assert inner.describe.call_count == 2

    def test_raises_on_non_retryable(self):
        inner = MagicMock()
        inner.describe.side_effect = ImportError("module not found")
        renamer = RetryingRenamer(inner)
        with pytest.raises(ImportError):
            renamer.describe(Path("test.png"))

    def test_falls_through_after_max_retries(self):
        inner = MagicMock()
        inner.describe.side_effect = Exception("429 rate limit")
        renamer = RetryingRenamer(inner)
        with patch("banana_peel.renamer.time.sleep"):
            with pytest.raises(Exception, match="429"):
                renamer.describe(Path("test.png"))
        assert inner.describe.call_count == 3
