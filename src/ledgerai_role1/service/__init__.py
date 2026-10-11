"""Role 1 Document Intelligence Service."""

from ledgerai_role1.service.app import create_app
from ledgerai_role1.service.config import Role1Settings

__all__ = ["Role1Settings", "create_app"]
