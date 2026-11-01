import configparser
from pathlib import Path

import mcwaiter.constants as C
import mcwaiter.service as service
from mcwaiter.user import sudo_permissions_fix
import shutil

DEFAULT_CONFIG = {
    "DEFAULTS": {
        "serverpath": "/opt/mcservers/",
        "editor": "",
        "shell": f"{shutil.which('bash') or ''}",
        "service-manager": f'{service.get_service_manager(False).displayname}'
    },
    "JAVA": {
        "auto": f"{shutil.which('java') or 'java'}"
    },
    "SERVICE": {
        "harden": "true",
        "network-isolation": "false",
        "deny-network": "false",
        "private-tmp": "true",
        "private-devices": "true",
        "protect-kernel": "true",
        "read-only-system": "false",
        "memory-limit": "0",
        "cpu-quota": "0",
        "tasks-limit": "0"
    }
}

def setup_config() -> None:
    for section, options in DEFAULT_CONFIG.items():
        if not C.config.has_section(section):
            C.config.add_section(section)

        for key, value in options.items():
            if not C.config.has_option(section, key):
                C.config.set(section, key, value)

    save_config()

def create_server_config(path_to_instance: Path):
    override = configparser.ConfigParser()
    
    override.add_section("OVERRIDES")

    for key in DEFAULT_CONFIG["SERVICE"].keys():
        override.set("OVERRIDES", key, "")

    with open(path_to_instance.parent / (path_to_instance.name + ".ini"), "w") as f:
        override.write(f)

def get_server_config(path_to_instance: Path):
    serv_cfg_file = path_to_instance.parent / (path_to_instance.name + ".ini")
    if not serv_cfg_file.exists():
        raise FileNotFoundError("Server config file does not exist.")
    serv_cfg = configparser.ConfigParser()
    serv_cfg.read(serv_cfg_file, encoding="UTF-8")
    return serv_cfg

def ensure_config() -> None:
    if C.CONFIG_FILE.exists():
        C.config.read(C.CONFIG_FILE)

    setup_config()

def save_config() -> None:
    with C.CONFIG_FILE.open("w") as f:
        C.config.write(f)
    sudo_permissions_fix(C.CONFIG_DIR)