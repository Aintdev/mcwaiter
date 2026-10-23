from importlib.metadata import version as pkg_version
from importlib.metadata import metadata as pkg_metadata
from importlib.metadata import PackageNotFoundError

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

APP_VERSION: str = get_app_version()
APP_DESCRIPTION: str = get_app_description()

TEMP_FLAG_ONE: int = 0b1
TEMP_FLAG_TWO: int = 0b10