from pathlib import Path
import subprocess
from mcwaiter.config import ensure_config, save_config
from mcwaiter.helpers import parse_loader
from mcwaiter.logger import logger as log
from mcwaiter.errors import UserCancelledError
from mcwaiter.input import parse_arguments, ensure_data
import mcwaiter.constants as C
import logging as logging

def main():
    log.setLevel(logging.DEBUG)
    ensure_config()
    args = parse_arguments()

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
    get_build(args)

    SERVER_PATH = Path(C.config.get("DEFAULTS", "serverpath")) / args.name
    SERVER_PATH.mkdir(parents=True, exist_ok=True)

def get_build(args):
    loader, version = parse_loader(args.loader)
    # get version here
    
def delete(args):
    ensure_data(args, C.ALL_DELETE_F)
    if not args.confirm_override: 
        return
    log.info("Deleting.")