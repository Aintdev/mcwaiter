from pathlib import Path
import subprocess
from mcwaiter.config import ensure_config, save_config
from mcwaiter.helpers import parse_loader
from mcwaiter.logger import logger as log
from mcwaiter.errors import UserCancelledError
from mcwaiter.input import parse_arguments, ensure_data, select_build
from mcwaiter.requests import get_builds
import mcwaiter.constants as C
import logging as logging
from shutil import rmtree

def main():
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

def config(args):
    ensure_data(args, C.EDITOR_F)
    subprocess.run([args.editor, str(C.CONFIG_FILE)], check=True, shell=True)

def create(args):
    args = ensure_data(args, C.ALL_CREATE_F)
    log.info("Creating.")
    calculate_build(args)

    SERVER_PATH = Path(C.config.get("DEFAULTS", "serverpath")) / args.name
    SERVER_PATH.mkdir(parents=True, exist_ok=True)

def calculate_build(args):
    loader, loader_version = parse_loader(args.loader)

    result, multiple = get_builds(args.version, loader, loader_version)

    if multiple:
        build = select_build(result)
        log.debug(build.__dict__)
    
def delete(args):
    ensure_data(args, C.ALL_DELETE_F)
    if not args.confirm_override: 
        return
    log.info("Deleting.")