import argparse
from mcwaiter.constants import APP_VERSION, APP_DESCRIPTION
import questionary

def parse_arguments():
    parser = argparse.ArgumentParser(
        prog="mcwaiter",
        description=APP_DESCRIPTION,
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {APP_VERSION}",
    )

    args = parser.parse_args()

    return args

def ensure_data(flags: int) -> None:
    # add questionary questions here
    return