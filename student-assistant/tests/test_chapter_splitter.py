"""split_by_chapter produces the right slices for given page ranges."""
import pytest


@pytest.mark.skip(reason="MVP1 implementation pending")
def test_split_respects_page_range() -> None:
    """Given a doc with page markers and a 2-chapter wiki, slices match page_range."""
    raise NotImplementedError


@pytest.mark.skip(reason="MVP1 implementation pending")
def test_split_no_page_markers_falls_back_to_single_file() -> None:
    """Doc with no page markers yields {'ch_all': full_doc} and warns."""
    raise NotImplementedError
