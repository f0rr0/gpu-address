"""One entry point; command dependencies load only when selected."""

import argparse
import importlib
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(prog="gpu-address")
    parser.add_argument(
        "command",
        choices=[
            "prepare",
            "expand",
            "train",
            "predict",
            "export",
            "diagnose",
            "rank-diagnosis",
            "teacher",
            "check",
        ],
    )
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(argv[:1])
    rest = argv[1:]
    importlib.import_module(f"gpu_address.{args.command.replace('-', '_')}").main(rest)
