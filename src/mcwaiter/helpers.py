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

import re
import subprocess
from pathlib import Path


def find_javas() -> set[i.JavaVersion]:
    java_versions: set[i.JavaVersion] = set()

    for java in Path("/usr/lib/jvm").glob("*/bin/java"):
        try:
            if java.parent.parent.is_symlink():
                continue

            if not java.is_file() or not java.stat().st_mode & 0o111:
                continue

            result = subprocess.run(
                [str(java), "-version"],
                capture_output=True,
                text=True,
                check=False,
                cwd="/",
                timeout=5,
            )

            output = result.stdout + "\n" + result.stderr

            if result.returncode != 0:
                continue

            match = re.search(
                r'version\s+"?(\d+)(?:\.(\d+))?',
                output,
                re.IGNORECASE,
            )

            if not match:
                continue

            major = int(match.group(1))

            if major == 1 and match.group(2):
                major = int(match.group(2))

            java_versions.add(i.JavaVersion(
                display_name=java.parent.parent.name,
                main_version_id=major,
                path=java,
                new_flag=True,
            ))

        except (OSError, subprocess.SubprocessError, ValueError):
            continue

    return java_versions

def print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [
        max(len(str(row[i])) for row in [headers, *rows])
        for i in range(len(headers))
    ]

    def format_row(row):
        return "  ".join(
            str(value).ljust(widths[i])
            for i, value in enumerate(row)
        )

    print(format_row(headers))
    print("  ".join("-" * width for width in widths))

    for row in rows:
        print(format_row(row))