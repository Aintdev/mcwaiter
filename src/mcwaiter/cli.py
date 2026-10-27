import json
import os
from pathlib import Path
import subprocess
from mcwaiter.config import ensure_config, save_config
from mcwaiter.helpers import is_windows, parse_loader, require_root
from mcwaiter.logger import logger as log
from mcwaiter.errors import UserCancelledError, DownloadError
from mcwaiter.input import Build, parse_arguments, ensure_data, select_build
from mcwaiter.requests import download, get_builds
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
        if args.command == 'create':
            create(args)
        elif args.command == 'delete':
            delete(args)
        elif args.command == 'config':
            config(args)
    except (KeyboardInterrupt, UserCancelledError):
        pass
    log.info("Exiting.")
    save_config()
    return 0

# Command "config"

def config(args):
    ensure_data(args, C.EDITOR_F)
    subprocess.run([args.editor, str(C.CONFIG_FILE)], check=True, shell=False)

# Command "create"

def create(args):
    require_root()

    args = ensure_data(args, C.ALL_CREATE_F)
    log.info("Creating.")

    if not user.get_user(args.name):
        user.create_user(args.name)
    else:
        log.error("Server with that name already exists.")

    cur_user = user.get_user(args.name)

    build = _calculate_build(args)

    server_dir = Path(C.config.get("DEFAULTS", "serverpath")) / args.name
    server_dir.mkdir(parents=True, exist_ok=True)

    _install(build, server_dir, cur_user)

    user.user_own(cur_user, server_dir)

def _install(build: Build, directory: Path, user: user.UserInfo) -> None:
    for instruction in build.installation:
        log.debug(json.dumps(instruction, indent=4))

        if instruction["type"] == "download":
            download(
                instruction["url"], 
                (Path(directory) / instruction["file"]).resolve(),
                instruction["size"]
            )

def _calculate_build(args):
    loader, loader_version = parse_loader(args.loader)

    result, multiple = get_builds(args.version, loader, loader_version)

    if multiple:
        build = select_build(result)
    else:
        build = result
    log.debug(build.__dict__)

    return build

# Command "delete"

def delete(args):
    ensure_data(args, C.ALL_DELETE_F)
    if not args.confirm_override: 
        return
    log.info("Deleting.")