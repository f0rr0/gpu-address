"""CLI paths are relative to the working directory, or GPU_ADDRESS_HOME."""

import os
from pathlib import Path

ROOT = Path(os.environ.get("GPU_ADDRESS_HOME", ".")).resolve()
SOURCE = Path(__file__).resolve().parent
