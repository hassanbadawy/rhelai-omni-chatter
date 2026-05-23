"""Schema migration applies cleanly; CRUD round-trips for materials and chat."""
import pytest


@pytest.mark.skip(reason="MVP1 implementation pending")
async def test_migrate_applies_v001() -> None:
    """Run migrate against a fresh sqlite, verify schema_migrations row exists."""
    raise NotImplementedError


@pytest.mark.skip(reason="MVP1 implementation pending")
async def test_material_crud_round_trip() -> None:
    """Insert, read, update status, list — values match across the cycle."""
    raise NotImplementedError
