"""CLI entry points.

Commands:
- `student-assistant migrate`  — apply pending SQL migrations from migrations/v00N_*.sql
- `student-assistant doctor`   — verify Docling + LLM reachability + DB schema version
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click
import httpx

from config import load
from services.storage import Storage

logger = logging.getLogger(__name__)

_DOCTOR_TIMEOUT = 5.0


def _migrations_dir() -> Path:
    return Path(__file__).resolve().parent / "migrations"


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )


@click.group()
def main() -> None:
    """student-assistant CLI."""


@main.command()
def migrate() -> None:
    """Apply pending migrations."""
    cfg = load()
    _setup_logging(cfg.log_level)

    async def _run() -> None:
        storage = Storage(cfg.sqlite_path)
        try:
            await storage.connect()
            await storage.migrate(_migrations_dir())
            click.echo(f"[ok] migrations applied at {cfg.sqlite_path}")
        finally:
            await storage.close()

    asyncio.run(_run())


@main.command()
def doctor() -> None:
    """Health-check the local environment (Docling, LLM, DB)."""
    cfg = load()
    _setup_logging(cfg.log_level)

    async def _check_docling(url: str) -> tuple[bool, str]:
        async with httpx.AsyncClient(timeout=_DOCTOR_TIMEOUT, follow_redirects=True) as client:
            for path in ("/health", "/"):
                try:
                    r = await client.get(f"{url}{path}")
                    if 200 <= r.status_code < 400:
                        return True, f"Docling: ok ({url})"
                except Exception as e:  # noqa: BLE001
                    last_err = f"Docling: {type(e).__name__}: {e}"
        return False, last_err

    async def _check_llm(base_url: str, api_key: str) -> tuple[bool, str]:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        try:
            async with httpx.AsyncClient(
                timeout=_DOCTOR_TIMEOUT, headers=headers
            ) as client:
                r = await client.get(f"{base_url}/models")
            if r.status_code < 400:
                return True, f"LLM: ok ({base_url})"
            return False, f"LLM: HTTP {r.status_code} from {base_url}"
        except Exception as e:  # noqa: BLE001
            return False, f"LLM: {type(e).__name__}: {e}"

    async def _check_db() -> tuple[bool, str]:
        storage = Storage(cfg.sqlite_path)
        try:
            await storage.connect()
            async with storage.conn.execute(
                "SELECT MAX(version) AS v FROM schema_migrations;"
            ) as cur:
                row = await cur.fetchone()
            if row is None or row["v"] is None:
                return False, f"DB: schema_migrations empty — run migrate"
            return True, f"DB: schema v{int(row['v'])} ({cfg.sqlite_path})"
        except Exception as e:  # noqa: BLE001
            return False, f"DB: {type(e).__name__}: {e}"
        finally:
            try:
                await storage.close()
            except Exception:  # noqa: BLE001
                pass

    async def _run() -> int:
        # Read runtime URLs from DB if available, else fall back to config defaults.
        storage = Storage(cfg.sqlite_path)
        docling_url = cfg.initial_docling_url
        llm_base_url = cfg.initial_llm_base_url
        llm_api_key = cfg.initial_llm_api_key
        try:
            await storage.connect()
            docling_url = (await storage.get_setting("docling_url")) or docling_url
            llm_base_url = (await storage.get_setting("llm_base_url")) or llm_base_url
            llm_api_key = (await storage.get_setting("llm_api_key")) or llm_api_key
        except Exception:  # noqa: BLE001
            pass
        finally:
            try:
                await storage.close()
            except Exception:  # noqa: BLE001
                pass

        results = await asyncio.gather(
            _check_docling(docling_url),
            _check_llm(llm_base_url, llm_api_key),
            _check_db(),
        )
        all_ok = True
        for ok, msg in results:
            click.echo(f"{'[ok]' if ok else '[fail]'} {msg}")
            if not ok:
                all_ok = False
        return 0 if all_ok else 1

    rc = asyncio.run(_run())
    if rc != 0:
        sys.exit(rc)


if __name__ == "__main__":
    main()
