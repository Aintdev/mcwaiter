import mcwaiter.constants as C
from mcwaiter.user import sudo_permissions_fix
import shutil

DEFAULT_CONFIG = {
    "DEFAULTS": {
        "serverpath": "/opt/mcservers/",
        "editor": "",
        "shell": f"{shutil.which("bash")}"
    },
    "JAVA": {
        "auto": f"{shutil.which("java")}"
    },
}

def setup_config() -> None:
    for section, options in DEFAULT_CONFIG.items():
        if not C.config.has_section(section):
            C.config.add_section(section)

        for key, value in options.items():
            if not C.config.has_option(section, key):
                C.config.set(section, key, value)

    save_config()

def ensure_config() -> None:
    if C.CONFIG_FILE.exists():
        C.config.read(C.CONFIG_FILE)

    setup_config()

def save_config() -> None:
    with C.CONFIG_FILE.open("w") as f:
        C.config.write(f)
    sudo_permissions_fix(C.CONFIG_DIR)