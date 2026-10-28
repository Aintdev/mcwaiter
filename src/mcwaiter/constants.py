import configparser
from importlib.metadata import version as pkg_version
from importlib.metadata import metadata as pkg_metadata
from importlib.metadata import PackageNotFoundError
import os
import pwd
from platformdirs import user_config_path
from pathlib import Path
from mcwaiter.user import sudo_permissions_fix

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

def get_config_dir() -> Path:
    sudo_user = os.environ.get("SUDO_USER")

    if os.geteuid() == 0 and sudo_user:
        home = Path(pwd.getpwnam(sudo_user).pw_dir)
        return home / ".config" / "mcwaiter"

    return user_config_path("mcwaiter", appauthor=False)

DEBUG_ON = False

API = "https://mcjars.app/api/"

APP_VERSION: str = get_app_version()
APP_DESCRIPTION: str = get_app_description()

USER_PREFIX = "mcwaiter-"

# Config stuff
CONFIG_DIR: Path = get_config_dir()
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
sudo_permissions_fix(CONFIG_DIR)
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
