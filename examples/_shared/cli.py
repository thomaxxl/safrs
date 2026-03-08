"""Command-line argument helpers shared by examples."""

from __future__ import annotations

import argparse
from typing import Sequence


def parse_host(argv: Sequence[str], *, default_host: str = "127.0.0.1") -> str:
    """Parse `[HOST]` style positional args used by legacy examples."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("host", nargs="?", default=default_host)
    args, _unknown = parser.parse_known_args(list(argv))
    return str(args.host)


def parse_host_port(
    argv: Sequence[str], *, default_host: str = "127.0.0.1", default_port: int = 5000
) -> tuple[str, int]:
    """Parse `[HOST] [PORT]` style positional args used by legacy examples."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("host", nargs="?", default=default_host)
    parser.add_argument("port", nargs="?", type=int, default=default_port)
    args, _unknown = parser.parse_known_args(list(argv))
    return str(args.host), int(args.port)

