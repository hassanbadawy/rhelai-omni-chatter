"""build_prompt produces a valid messages array; parse_response validates schema."""
import pytest


@pytest.mark.skip(reason="MVP1 implementation pending")
def test_parse_response_rejects_missing_chapters() -> None:
    """A YAML response without `chapters` raises ValueError."""
    raise NotImplementedError


@pytest.mark.skip(reason="MVP1 implementation pending")
def test_parse_response_rejects_invalid_yaml() -> None:
    """Malformed YAML raises ValueError, not a silent partial parse."""
    raise NotImplementedError


@pytest.mark.skip(reason="MVP1 implementation pending")
def test_parse_response_accepts_minimal_valid() -> None:
    """A valid frontmatter with just `chapters[]` and `synthesis` round-trips."""
    raise NotImplementedError
