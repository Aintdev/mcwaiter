import os
from pathlib import Path
import random
import shutil
import string
import subprocess
import sys
import questionary
from mcwaiter.config import save_config
from mcwaiter.errors import ServerStateError
import mcwaiter.input as i
from mcwaiter.logger import logger as log
import mcwaiter.constants as C

def random_str(N: int) -> str:
    # Source - https://stackoverflow.com/a/2257449
    # Posted by Ignacio Vazquez-Abrams, modified by community. See post 'Timeline' for change history
    # Retrieved 2026-10-24, License - CC BY-SA 4.0

    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=N))

def parse_loader(arg: str) -> tuple[str, str | None]:
    if "@" in arg:
        name, ver = arg.split("@", 1)
        return (name, ver)

    return (arg, None)

def is_windows():
    return os.name == 'nt'

def require_root():
    if os.geteuid() == 0:
        return

    log.debug("Raised privileges.")

    script = Path(sys.argv[0]).resolve()

    subprocess.run(
        ["sudo", sys.executable, str(script), *sys.argv[1:]],
        check=True,
    )
    sys.exit(0)

def safe_path(base: Path, relative: str) -> Path:
    base = base.resolve()
    target = (base / relative).resolve()
    if target == base or not target.is_relative_to(base):
        raise ServerStateError(f"Path {relative!r} points outside the server directory.")
    return target

def edit_file(path: Path, param = None):
    if param:
        C.config.set("DEFAULTS", "editor", param)
    if not C.config.get("DEFAULTS", "editor"):
        C.config.set("DEFAULTS", "editor", i.ask(questionary.text, "Editor:"))
    save_config()

    editor = C.config.get("DEFAULTS", "editor")
    if shutil.which(editor):
        subprocess.run([editor, str(path)])
        return
    else:
        log.error("Invalid editor. Set editor in config by executing: 'mcwaiter config YOUR_EDITOR_HERE' and set it manually.")
    