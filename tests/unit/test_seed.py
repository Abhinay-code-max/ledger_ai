from uuid import UUID

import pytest

from ledgerai_backend.core.config import Settings
from ledgerai_backend.database.seed import stable_id


def test_seed_ids_are_deterministic_and_distinct() -> None:
    first = stable_id("nova:tenant")
    assert first == stable_id("nova:tenant")
    assert first != stable_id("nova:organization")
    assert isinstance(first, UUID)


def test_production_seed_settings_require_secure_configuration() -> None:
    with pytest.raises(ValueError):
        Settings(environment="production")
