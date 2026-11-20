#!/usr/bin/env python
"""
Mint a long-lived service token for non-interactive callers (n8n, cron, CI).

The API's normal login flow issues a 24h token for a human user. Automated
callers — e.g. the n8n workflows in ``infra/n8n/`` — need a token that
outlives a work day, so they authenticate as a service principal with the
same JWT secret instead of logging in again every morning.

Run (from the ``backend`` directory, so ``.env`` is picked up):

    python scripts/mint_service_token.py --days 90
    python scripts/mint_service_token.py --days 90 --write-env

``--write-env`` appends/updates ``FINSIGHT_SERVICE_TOKEN`` in the ``.env``
this settings object loaded, which is what the local n8n launcher
(``infra/n8n/start-local.ps1``) reads.

Treat the printed token like a password: it grants access to the demo
business's financials until it expires.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402
from app.core.security import create_access_token  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=90, help="token lifetime in days (default 90)")
    parser.add_argument("--business-id", default="demo-business-001")
    parser.add_argument("--subject", default="service:n8n@finsight.local")
    parser.add_argument(
        "--write-env",
        action="store_true",
        help="write/update FINSIGHT_SERVICE_TOKEN in backend/.env instead of only printing",
    )
    args = parser.parse_args()

    if args.days <= 0:
        parser.error("--days must be positive")

    settings = Settings()
    service_settings = settings.model_copy(update={"JWT_EXPIRE_MINUTES": args.days * 24 * 60})
    token = create_access_token(
        user_id=args.subject,
        business_id=args.business_id,
        role="owner",
        settings=service_settings,
    )

    if args.write_env:
        env_path = Path(getattr(settings, "model_config", {}).get("env_file", ".env"))
        if not env_path.is_absolute():
            env_path = Path.cwd() / env_path
        lines: list[str] = []
        if env_path.exists():
            lines = env_path.read_text(encoding="utf-8").splitlines()
        entry = f"FINSIGHT_SERVICE_TOKEN={token}"
        for i, line in enumerate(lines):
            if line.startswith("FINSIGHT_SERVICE_TOKEN="):
                lines[i] = entry
                break
        else:
            if lines and lines[-1].strip():
                lines.append("")
            lines.extend(["# --- Service token used by the n8n workflows ---", entry])
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Wrote FINSIGHT_SERVICE_TOKEN to {env_path}", file=sys.stderr)

    print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
