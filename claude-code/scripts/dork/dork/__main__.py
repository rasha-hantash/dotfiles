"""CLI entry point."""
from __future__ import annotations

import json
import logging
from pathlib import Path

import click

from dork.config import DorkConfig


@click.group()
def cli():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


@cli.command()
@click.option("--config", "config_path", default="dork.toml")
@click.option("--output", "output_path", default=None)
@click.option("--max", "max_candidates", default=30, type=int)
def fetch(config_path: str, output_path: str | None, max_candidates: int):
    """Fetch candidates and output JSON."""
    from dork.fetch import fetch_candidates

    config = DorkConfig.load(Path(config_path))
    candidates = fetch_candidates(config, max_candidates=max_candidates)
    output = json.dumps(candidates, indent=2)

    if output_path:
        Path(output_path).write_text(output)
        click.echo(f"Wrote {len(candidates)} candidates to {output_path}")
    else:
        click.echo(output)


if __name__ == "__main__":
    cli()
