"""Service runner for Role 2 Accounting Core."""

from __future__ import annotations

import uvicorn

from ledgerai_role2.api.app import create_role2_app
from ledgerai_role2.config import Role2Settings


def main() -> None:
    settings = Role2Settings()
    app = create_role2_app(settings)
    uvicorn.run(app, host="0.0.0.0", port=8102)


if __name__ == "__main__":
    main()
