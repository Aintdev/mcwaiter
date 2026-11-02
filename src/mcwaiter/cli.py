import json
import os
from pathlib import Path
import shutil
import zipfile
import questionary
from mcwaiter.config import create_server_config, ensure_config
from mcwaiter.helpers import edit_file, is_windows, parse_loader, print_table, require_root, safe_path
from mcwaiter.logger import logger as log
from mcwaiter.errors import NoManagerFoundError, NoVersionFoundError, ServerStateError, UnknownManagerError, UserCancelledError
from mcwaiter.input import Build, get_java_path, parse_arguments, ensure_data, select_build, ask, make_jvm_args
from mcwaiter.requests import download, get_builds, get_java_version
import mcwaiter.service as sv
import mcwaiter.user as user
import mcwaiter.constants as C
import logging as logging
from shutil import rmtree

def main():
    if is_windows():
        log.critical("Tool is not windows compatible - please run in unix-like.")
        return 1
    ensure_config()
    args = parse_arguments()
    log.setLevel(logging.DEBUG if C.DEBUG_ON else logging.INFO)
    if C.DEBUG_ON:
        debug_dir = C.CONFIG_DIR / ".debug"
        if debug_dir.exists():
            rmtree(debug_dir, ignore_errors=True)

    try:
        if args.command == 'shell':
            shell(args)
        elif args.command == 'chown':
            chown(args)
        elif args.command == 'create':
            create(args)
        elif args.command == 'delete':
            delete(args)
        elif args.command == 'config':
            config(args)
        elif args.command == 'edit':
            edit(args)
        elif args.command == 'start':
            start(args)
        elif args.command == 'stop':
            stop(args)
        elif args.command == 'status':
            status(args)
        elif args.command == 'ls':
            ls(args)
        elif args.command == 'autostart':
            autostart(args)
    except (KeyboardInterrupt, UserCancelledError):
        log.info("Cancelled.")
    except ServerStateError as e:
        log.critical("ServerStateError: " + str(e))
    except NoVersionFoundError as e:
        log.error("No version for given parameters found. " if not e else e)
    except NoManagerFoundError as e:
        log.error("No service manager found. " if not e else e)
    return 0

def server_exists(name: str):
    log.debug(str((Path(C.config.get("DEFAULTS", "serverpath")) / name / "server.jar").exists()) + str((Path(C.config.get("DEFAULTS", "serverpath")) / name / "server.jar")))
    return \
        user.user_exists(C.USER_PREFIX + name) \
        and (Path(C.config.get("DEFAULTS", "serverpath")) / name).exists()

def ensure_server(name: str):
    if not server_exists(name):
        raise ServerStateError(f"User or folder with name {name} not found.")

def ensure_server_creatable(name: str):
    if  user.user_exists(C.USER_PREFIX + name) \
        or (
            (Path(C.config.get("DEFAULTS", "serverpath")) / name).exists()
            and not any((Path(C.config.get("DEFAULTS", "serverpath")) / name).iterdir())
        ):
        raise ServerStateError(f"User or folder at {C.config.get("DEFAULTS", "serverpath")} with name {name} already exists.")

# Command "edit"
def edit(args):
    require_root()
    ensure_server(args.name)
    username = C.USER_PREFIX + args.name

    server_dir = safe_path(Path(C.config.get("DEFAULTS", "serverpath")), str(Path(args.name)))

    real_path = safe_path(Path(C.config.get("DEFAULTS", "serverpath")), str(Path(args.name) / args.relpath))

    edit_file(real_path)
    user.user_own(user.get_user(C.USER_PREFIX + args.name), server_dir)

# Command "shell"

def shell(args):
    require_root()
    ensure_server(args.name)
    this_user = user.get_user(C.USER_PREFIX + args.name)

    os.execvp("sudo", [
        "sudo",
        "-u", this_user.username,
        "-H",
        "sh", "-c", 'cd "$HOME" && exec "$0"',
        C.config.get("DEFAULTS", "shell"),
    ])

# Command "config"

def config(args):
    ensure_data(args, C.EDITOR_F)

    if args.name:
        require_root()
        ensure_server(args.name)
        return edit_file(Path(C.config.get("DEFAULTS", "serverpath")) / (args.name + ".ini"), args.editor)
    return edit_file(C.CONFIG_FILE, args.editor)

# Command "chown"

def chown(args): 
    require_root()
    ensure_server(args.name)
    user.user_own(user.get_user(C.USER_PREFIX + args.name), Path(C.config.get("DEFAULTS", "serverpath")) / args.name)

# Command "create"

def create(args):
    require_root()
    ensure_server_creatable(args.name)

    args = ensure_data(args, C.ALL_CREATE_F)
    log.info("Creating.")

    this_user_str = C.USER_PREFIX + str(args.name).lower()
    server_dir = Path(C.config.get("DEFAULTS", "serverpath")) / args.name

    build = _calculate_build(args)

    try:
        if not user.user_exists(this_user_str):
            user.create_user(this_user_str, server_dir)
        else:
            log.error("Server with that name already exists.")
            return

        cur_user = user.get_user(this_user_str)

        _install(args, build, server_dir, cur_user)

        log.info("Finished successfully.")
    except:
        delete(args, _force=True)
        raise


def _install(args, build: Build, directory: Path, user_info: user.UserInfo) -> None:
    for instruction in build.installation:
        log.debug(json.dumps(instruction, indent=4))

        if instruction["type"] == "download":
           download(
               url = instruction["url"], 
               filepath = safe_path(directory, instruction["file"]),
               show_progressbar = True,
               expected_filesize = instruction.get("size", 0)                
           )
        elif instruction["type"] == "unzip":
            zip_file = safe_path(directory, str(Path(instruction["location"]) / instruction["file"]))
            log.info(f"Unzipping {zip_file}...")

            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                zip_ref.extractall(directory)
        elif instruction["type"] == "remove":
            file = safe_path(directory, instruction["location"])
            log.info(f"Deleting {file.name}...")

            if file.is_dir(): 
                shutil.rmtree(file, True)
            elif file.exists():
                file.unlink()

    run_file = directory / "run.sh"
    with open(run_file, "w") as f:
        f.write(
f"""#!{C.config.get("DEFAULTS", "shell")}

cd "$(dirname "$0")"

{get_java_path(get_java_version(args.version)).path} @user_jvm_args.txt -jar server.jar --nogui "$@"
""")
    run_file.chmod(0o755)

    make_jvm_args(args, directory)

    create_server_config(directory)

    eula_ask = ask(questionary.confirm, "Do you agree to the Minecraft EULA (https://aka.ms/MinecraftEULA)?", can_cancel=True, default=False)
    eula_accept = "true" if eula_ask else "false"
    with open(directory / "eula.txt", "w") as f:
        f.write(
f"""#By changing the setting below to TRUE you are indicating your agreement to our EULA (https://account.mojang.com/documents/minecraft_eula).
eula={eula_accept}"""
        )
    
    user.user_own(user_info, directory)

def _calculate_build(args):
    loader, loader_version = parse_loader(args.loader)

    result, multiple = get_builds(args.version, loader, loader_version)

    if not result.get("builds") and not result.get("build"):
        log.debug(json.dumps(result, indent=4))
        raise NoVersionFoundError("No version found.")

    if multiple:
        build = select_build(result)
    else:
        result = result["build"]
        build = Build(
            id = result["id"],
            name = result["name"] ,
            versionId = result["versionId"],
            projectVersionId = result["projectVersionId"],
            experimental = result["experimental"],
            installation = result["installation"]
        )
    log.debug(build.__dict__)

    return build

# Command "delete"

def delete(args, /, _force = False):
    require_root()
    ensure_server(args.name)

    if not _force: 
        ensure_data(args, C.ALL_DELETE_F)
        if not args.confirm_override: 
            return
    log.info("Deleting." if not _force else "Reverting.")

    stop(args)

    user.delete_user(C.USER_PREFIX + args.name, remove_home=True)
    cfg_file: Path = Path(C.config.get("DEFAULTS", "serverpath")) / (args.name + ".ini")
    cfg_file.unlink(missing_ok=True)

def start(args):
    require_root()
    ensure_server(args.name)
    
    server_dir = Path(C.config.get("DEFAULTS", "serverpath")) / args.name
    try:
        sv.start(server_dir, sv.get_service_manager())
    except UnknownManagerError:
        log.critical("Manager is not supported by mcwaiter.")

def stop(args):
    require_root()
    ensure_server(args.name)
    
    server_dir = Path(C.config.get("DEFAULTS", "serverpath")) / args.name
    try:
        sv.stop(server_dir, sv.get_service_manager())
    except UnknownManagerError:
        log.critical("Manager is not supported by mcwaiter.")

def status(args):
    ensure_server(args.name)
    
    server_dir = Path(C.config.get("DEFAULTS", "serverpath")) / args.name
    try:
        sv.status(server_dir, sv.get_service_manager())
    except UnknownManagerError:
        log.critical("Manager is not supported by mcwaiter.")

def ls(args):
    serverpath = Path(C.config.get("DEFAULTS", "serverpath"))
    manager = sv.get_service_manager()

    rows = []

    for path in sorted(serverpath.iterdir()):
        if not path.is_dir():
            continue

        running = sv.status(path, manager, silent=True)

        rows.append([
            path.name,
            "Yes" if running.returncode == 0 else "No",
            str(path),
        ])

    if not rows:
        print("No servers found.")
        return

    print_table(["Name", "Running", "Path"], rows)

def autostart(args):
    pass