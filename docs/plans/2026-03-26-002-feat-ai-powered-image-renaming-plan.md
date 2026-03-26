---
title: "feat: AI-powered image renaming based on content"
type: feat
status: completed
date: 2026-03-26
---

# AI-Powered Image Renaming

## Overview

Add an optional AI-powered rename step to banana-peel's processing pipeline. Instead of `Gemini_Generated_Image_abc_peeled.png`, processed images get descriptive filenames like `steak-dinner.png` based on what the vision API sees in the image.

Provider-agnostic (Gemini, OpenAI, Anthropic), opt-in, and gracefully falls back to `_peeled` naming when the API is unavailable.

## Problem Statement / Motivation

After processing, images still have meaningless `Gemini_Generated_Image_*_peeled.png` filenames. Users who generate many images end up with a folder full of indistinguishable files. The tool already handles watermark removal, compression, and destination folders — renaming completes the workflow.

## Proposed Solution

### Phase 1: Consolidate the processing pipeline

The processing pipeline is currently duplicated between `cli.py` (`clean` command, lines 124-177) and `watcher.py` (`_process` method, lines 93-173). Before adding AI rename, extract a shared `process_file()` function.

**New file: `src/banana_peel/processor.py`**

```python
def process_file(
    file_path: Path,
    watermark_config: WatermarkConfig,
    compression_config: CompressionConfig,
    rename_config: RenameConfig,
    destination: Path | None = None,
    dry_run: bool = False,
) -> ProcessResult:
    """Run the full pipeline: watermark removal -> compression -> rename -> move."""
    ...
```

Returns a `ProcessResult` dataclass with:
- `output_path: Path` — final file location
- `watermark_removed: bool`
- `bytes_saved: int`
- `renamed: bool` — whether AI rename was used vs `_peeled` fallback

Both `cli.py` and `watcher.py` call `process_file()` instead of inlining the pipeline.

### Phase 2: Provider-agnostic vision interface

**New file: `src/banana_peel/renamer.py`**

```python
class ImageRenamer(Protocol):
    def describe(self, image_path: Path) -> str:
        """Return a short description of the image content."""
        ...

class GeminiRenamer:
    """Uses google-generativeai SDK."""

class OpenAIRenamer:
    """Uses openai SDK."""

class AnthropicRenamer:
    """Uses anthropic SDK."""

def get_renamer(config: RenameConfig) -> ImageRenamer | None:
    """Factory: returns the configured renamer, or None if disabled."""
```

**Prompt** (hardcoded for v1):
> "Describe this image in 3-5 words for use as a filename. Reply with only the description, no punctuation."

**Slug generation:**
- Lowercase, strip non-alphanumeric, replace spaces/underscores with hyphens
- Collapse multiple hyphens
- Truncate to 60 characters at a word boundary
- On collision: append `-YYYYMMDD-HHmmss` timestamp
- Collision check looks at the destination directory if configured, source directory otherwise

### Phase 3: Config and CLI wiring

**Config (`config.toml`):**

```toml
[rename]
enabled = false              # Must opt-in
provider = "gemini"          # "gemini", "openai", "anthropic"
api_key = ""                 # Checked first; falls back to env var
model = ""                   # Empty = provider default
```

**API key resolution order:**
1. `rename.api_key` in config.toml (if non-empty)
2. Provider-specific env var: `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`

**New `RenameConfig` dataclass in `config.py`:**

```python
@dataclass
class RenameConfig:
    enabled: bool = False
    provider: str = "gemini"
    api_key: str = ""
    model: str = ""
```

**CLI flags (added to both `clean` and `watch`):**
- `--ai-rename` — enable AI renaming (overrides config)
- `--no-ai-rename` — disable AI renaming (overrides config)
- `--provider` — override provider
- `--api-key` — override API key (for one-shot use)

**Provider SDK dependencies** are optional extras in `pyproject.toml`:

```toml
[project.optional-dependencies]
gemini = ["google-generativeai>=0.5.0"]
openai = ["openai>=1.0.0"]
anthropic = ["anthropic>=0.20.0"]
ai = ["google-generativeai>=0.5.0", "openai>=1.0.0", "anthropic>=0.20.0"]
```

Install with: `pip install banana-peel[gemini]` or `pip install banana-peel[ai]`

## Technical Considerations

### Error handling and fallback

- If the configured provider SDK is not installed: log error at startup, fall back to `_peeled` naming
- If the API call fails (network, 500, malformed response): log warning, fall back to `_peeled` for that file, continue processing
- Rate limiting (429): retry up to 3 times with exponential backoff (1s, 2s, 4s), then fall back
- If API key is missing but rename is enabled: log warning once, disable rename for the session

### Dry-run behavior

Dry-run does **not** call the vision API (side-effect-free, costs nothing). Output shows:
```
Would process: Gemini_Generated_Image_abc.png -> <ai-renamed>.png
```

### Batch cost awareness

Before processing in `clean` command, if AI rename is enabled:
```
AI rename enabled: will make 47 API call(s)
```
No confirmation prompt — just a heads-up.

### Watch mode considerations

- The AI-renamed file (`steak-dinner.png`) won't match `_is_target()` since it doesn't start with `Gemini_Generated_Image_` — no self-trigger risk
- API latency (~200-500ms per call) runs in the timer thread — won't block the observer or other file events
- If the destination is the same as the watched directory, the `_our_mtime` guard still works since it tracks the final path

### Image sent to API

The image is sent **after** watermark removal but **before** compression. This gives the cleanest image for analysis without the watermark confusing the model. The image is read from disk (the watermark removal step already saved it back in-place).

## Acceptance Criteria

- [ ] Extract shared `process_file()` in `processor.py`, used by both `clean` and `watch`
- [ ] `ImageRenamer` protocol with Gemini, OpenAI, and Anthropic implementations
- [ ] Slug generation: kebab-case, max 60 chars, collision handling with timestamp
- [ ] `[rename]` config section with `enabled`, `provider`, `api_key`, `model`
- [ ] API key resolution: config value -> env var fallback
- [ ] `--ai-rename` / `--no-ai-rename` / `--provider` / `--api-key` CLI flags
- [ ] Provider SDKs as optional extras in pyproject.toml
- [ ] Graceful fallback to `_peeled` naming on any API failure
- [ ] Retry with backoff on rate limiting (3 attempts)
- [ ] Dry-run does not call the API
- [ ] Batch warning message showing API call count
- [ ] Tests: slug generation, collision handling, fallback behavior, config loading
- [ ] README updated with AI rename section
- [ ] CHANGELOG updated

## Dependencies & Risks

- **New dependency category**: First external API dependency. Made optional via extras to keep core tool installable without network dependencies.
- **API costs**: Gemini Flash is ~$0.00001/image, GPT-4o-mini similar. Negligible for normal use, but worth noting for large batch processing.
- **Provider SDK stability**: All three SDKs are mature and stable.
- **Pipeline refactor risk**: Consolidating the pipeline touches the core processing path. Existing tests should catch regressions but need careful review.

## Implementation Order

1. **`processor.py`** — Extract shared pipeline (refactor only, no new behavior)
2. **`renamer.py`** — Vision interface + slug generation (can be tested independently)
3. **Config + CLI wiring** — `RenameConfig`, CLI flags, optional dependency detection
4. **Integration** — Wire renamer into `process_file()`, update dry-run output
5. **Tests + docs** — Full test coverage, README, CHANGELOG

## Sources & References

- Similar implementations: `src/banana_peel/cli.py:124-177` (clean pipeline), `src/banana_peel/watcher.py:93-173` (watch pipeline)
- Config patterns: `src/banana_peel/config.py` (dataclass + TOML loading)
- CLI patterns: `src/banana_peel/cli.py:66-79` (typer option declarations)
