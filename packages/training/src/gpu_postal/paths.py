"""CLI paths are relative to the working directory."""

from pathlib import Path

ROOT = Path.cwd()
SOURCE = Path(__file__).resolve().parent
