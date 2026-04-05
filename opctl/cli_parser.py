import argparse
from .command_schema import COMMAND_SCHEMA

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opctl", 
        description="Tactical Workstation Bootstrapper",
        formatter_class=argparse.RawTextHelpFormatter
    )

    IGNORE_KEYS = ["flags", "usage", "example", "valid_modes", "no_cli"]

    for param, config in COMMAND_SCHEMA.items():
        # Skip shell-only navigation commands
        if config.get("no_cli"):
            continue
            
        kwargs = {k: v for k, v in config.items() if k not in IGNORE_KEYS}
        parser.add_argument(*config["flags"], **kwargs)

    return parser