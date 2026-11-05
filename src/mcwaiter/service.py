import configparser
from dataclasses import dataclass, field
from pathlib import Path
import shutil
import subprocess
import sys
import mcwaiter.config as config
from mcwaiter.errors import NoManagerFoundError, UnknownManagerError
import mcwaiter.constants as C

@dataclass(frozen=True)
class ServiceManager:
    displayname: str = field(default="")
    running_check: list[str] | None = field(default=None)
    running_response: str | None = field(default=None)

_SERVICE_MANAGERS: dict[str, ServiceManager] = {
    "systemd": ServiceManager(
        displayname = "systemd", 
        running_check = ["systemctl", "show-environment"],
        running_response = None
    ),
}

def get_service_manager(no_config: bool = True, safe: bool = False):
    preffered = None
    if no_config and (config_service_manager := C.config.get("DEFAULTS", "service-manager", fallback=preffered)):
        preffered = config_service_manager

    if preffered:
        manager = _SERVICE_MANAGERS.get(preffered, None)
    else:
        manager = _get_service_manager()

    if not manager:
        if safe:
            return ServiceManager("", None, None)
        raise NoManagerFoundError("No available service manager found.")

    if no_config and C.config.get("DEFAULTS", "service-manager") != manager.displayname:
        C.config.set("DEFAULTS", "service-manager", manager.displayname)
        config.save_config()
    return manager

def ensure_service(manager: ServiceManager):
    """Checks if service has been setup for autostarts and do so if not."""
    pass

def start(path_to_instance: Path, manager: ServiceManager):
    match manager.displayname:
        case "systemd":
            return _start_sysd(path_to_instance)
        case _:
            raise UnknownManagerError('Service-Manager "' + manager.displayname + '" is not supported.')

def stop(path_to_instance: Path, manager: ServiceManager):
    match manager.displayname:
        case "systemd":
            return _stop_sysd(path_to_instance)
        case _:
            raise UnknownManagerError('Service-Manager "' + manager.displayname + '" is not supported.')

def status(path_to_instance: Path, manager: ServiceManager, silent=False):
    match manager.displayname:
        case "systemd":
            return _status_sysd(path_to_instance, silent)
        case _:
            raise UnknownManagerError('Service-Manager "' + manager.displayname + '" is not supported.')

def restart(path_to_instance: Path, manager: ServiceManager):
    match manager.displayname:
        case "systemd":
            return _restart_sysd(path_to_instance)
        case _:
            raise UnknownManagerError('Service-Manager "' + manager.displayname + '" is not supported.')

def enable_autostart(manager: ServiceManager):
    match manager.displayname:
        case "systemd":
            return _enable_autostart_sysd()
        case _:
            raise UnknownManagerError('Service-Manager "' + manager.displayname + '" is not supported.')

def disable_autostart(manager: ServiceManager):
    match manager.displayname:
        case "systemd":
            return _disable_autostart_sysd()
        case _:
            raise UnknownManagerError('Service-Manager "' + manager.displayname + '" is not supported.')

# INTERNALS

def _get_service_manager() -> ServiceManager:
    for manager in _SERVICE_MANAGERS.values():
        if not shutil.which(manager.running_check[0]):
            continue
        if _test_manager(manager): return manager
    return None

def _test_manager(manager: ServiceManager) -> bool:
    try:
        result = subprocess.run(
            manager.running_check,
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
    except Exception:
        return False
    matches_expected_response = (result.stdout.strip() == manager.running_response) if manager.running_response else True
    return result.returncode == 0 and matches_expected_response

## systemd

def _start_sysd(path_to_instance: Path):
    command = [
        "systemd-run",
        "--unit", f"minecraft-{path_to_instance.name}",
        "--collect",
        *_get_properties_sysd(config.get_server_config(path_to_instance)),
        "--working-directory", str(path_to_instance),
        "--",
        (path_to_instance / "run.sh"),
    ]

    subprocess.run(command, check=True)

def _get_properties_sysd(serv_cfg: configparser.ConfigParser) -> list[str]:
    def get_option(key: str) -> str:
        override = serv_cfg.get("OVERRIDES", key, fallback="").strip()
        if override:
            return override
        return C.config.get("SERVICE", key)

    properties = []

    def add_property(name: str, value: str) -> None:
        properties.append(f"--property={name}={value}")

    if get_option("harden").lower() == "true":
        add_property("NoNewPrivileges", "yes")
        add_property("RestrictSUIDSGID", "yes")
        add_property("LockPersonality", "yes")
        add_property("RestrictRealtime", "yes")

    if get_option("network-isolation").lower() == "true":
        add_property("PrivateNetwork", "yes")
    elif get_option("deny-network").lower() == "true":
        add_property("IPAddressDeny", "any")

    if get_option("private-tmp").lower() == "true":
        add_property("PrivateTmp", "yes")

    if get_option("private-devices").lower() == "true":
        add_property("PrivateDevices", "yes")

    if get_option("protect-kernel").lower() == "true":
        add_property("ProtectKernelTunables", "yes")
        add_property("ProtectKernelModules", "yes")
        add_property("ProtectKernelLogs", "yes")
        add_property("ProtectControlGroups", "yes")

    if get_option("read-only-system").lower() == "true":
        add_property("ProtectSystem", "strict")
        add_property("ProtectHome", "yes")

    auto_restart = get_option("auto-restart").lower()
    if auto_restart:
        add_property("Restart", auto_restart)

    restart_delay = get_option("restart-sec").lower()
    if restart_delay:
        add_property("RestartSec", restart_delay)

    memory = get_option("memory-limit")
    if memory != "0":
        add_property("MemoryMax", memory)

    cpu = get_option("cpu-quota")
    if cpu != "0":
        add_property("CPUQuota", cpu)

    tasks = get_option("tasks-limit")
    if tasks != "0":
        add_property("TasksMax", tasks)

    return properties
    
def _stop_sysd(path_to_instance) -> str:
    command = [
        "systemctl",
        "stop", f"minecraft-{path_to_instance.name}"
    ]
    
    return subprocess.run(command, check=False)

def _status_sysd(path_to_instance: Path, silent):
    command = [
        "systemctl",
        "status",
        f"minecraft-{path_to_instance.name}.service",
    ]

    return subprocess.run(
        command,
        check=False,
        stdout=subprocess.DEVNULL if silent else None,
        stderr=subprocess.DEVNULL if silent else None,
    )

def _restart_sysd(path_to_instance):
    ...

def _deamon_reload() -> None:
    subprocess.run(
        ["systemctl", "daemon-reload"],
        capture_output=True,
        text=True,
        check=True
    )

def _enable_autostart_sysd() -> None:
    service = "mcwaiter-autostart"
    service_file = Path("/etc/systemd/system") / (service + ".service")
    if not service_file.exists():
        with open(service_file, "w") as f:
            f.write(
f"""[Unit]
Description=mcwaiter Minecraft Server Autostart
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart={Path(sys.argv[0]).resolve()} autostart --run
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
""")
    
    _deamon_reload()

    subprocess.run(
        ["systemctl", "enable", service],
        capture_output=True,
        text=True,
        check=True
    )


def _disable_autostart_sysd():
    service = "mcwaiter-autostart"
    service_file = Path("/etc/systemd/system") / (service + ".service")

    subprocess.run(
        ["systemctl", "disable", "--now", service],
        capture_output=True,
        text=True,
        check=True
    )
    
    if service_file.exists():
        service_file.unlink()

    _deamon_reload()
