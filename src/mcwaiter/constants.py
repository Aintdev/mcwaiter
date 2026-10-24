import configparser
from importlib.metadata import version as pkg_version
from importlib.metadata import metadata as pkg_metadata
from importlib.metadata import PackageNotFoundError
from platformdirs import user_config_path
from pathlib import Path

def get_app_version() -> str:
    try:
        return pkg_version("mcwaiter")
    except PackageNotFoundError:
        return "unknown"

def get_app_description() -> str | None:
    try:
        return pkg_metadata("mcwaiter")["Summary"] or "No description found."
    except PackageNotFoundError:
        return "No description found."

API = "https://mcjars.app/api/"

APP_VERSION: str = get_app_version()
APP_DESCRIPTION: str = get_app_description()

# Config stuff
CONFIG_DIR: Path = user_config_path("mcwaiter", appauthor=False)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE: Path = CONFIG_DIR / "config.ini"

config = configparser.ConfigParser()

# Flags
VERSION_F: int = 0x1
NAME_F: int = 0x2
LOADER_F: int = 0x4
CONFIRM_DELETION_F: int = 0x8
EDITOR_F: int = 0x10

ALL_CREATE_F: int = NAME_F | VERSION_F | LOADER_F
ALL_DELETE_F: int = NAME_F | CONFIRM_DELETION_F
