#!/usr/bin/env python3
"""
Compatibility wrapper for the canonical full Flask demo.

`demo_full.py` is kept at this path for backwards compatibility.
Use `demo_pythonanywhere_com.py` as the maintained implementation.
"""

from __future__ import annotations

from demo_pythonanywhere_com import app, create_app, main, start_api

__all__ = ["app", "create_app", "main", "start_api"]


if __name__ == "__main__":
    main()

