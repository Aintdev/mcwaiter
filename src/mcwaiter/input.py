import argparse
from mcwaiter.helpers import random_str
from mcwaiter.logger import logger as log
import mcwaiter.constants as C
from mcwaiter.errors import UserCancelledError
from mcwaiter.requests import get_loaders
from typing import Any, Callable
import questionary

def parse_arguments():
    parser = argparse.ArgumentParser(
        prog="mcwaiter",
        description=C.APP_DESCRIPTION,
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {C.APP_VERSION}",
    )

    subparser = parser.add_subparsers(
        dest="command",
        required=True,
    )

    setup = subparser.add_parser(
        "setup",
        help="Setup mcwaiter to be used.",
    )
    add_global_arguments(setup)

    create = subparser.add_parser(
        "create", 
        help="Create a Minecraft Server.",
    )
    add_global_arguments(create)

    create.add_argument("name", type=str, help="Name of the Minecraft Server.")

    create.add_argument(
        "--version", 
        type=str,
        help="Minecraft version. (eg: 1.20.1)",
    )

    create.add_argument(
        "--loader",
        type=str,
        help="Loader in format 'loader@build'. (eg: fabric@0.20.1 or fabric@stable (gets latest stable version))",
    )

    delete = subparser.add_parser(
        "delete",
        help="Deletes a Minecraft Server"
    )
    add_global_arguments(delete)

    delete.add_argument(
        "name", 
        type=str
    )

    delete.add_argument(
        "--confirm-override",
        action="store_true",
        help="Overrides the question if you are sure you want to delete the server. Use at your own risk."
    )

    config = subparser.add_parser(
        "config", 
        help="Edit config file.",
    )
    add_global_arguments(config)

    config.add_argument(
        "editor",
        nargs="?",
        type=str,
    )
    
    args = parser.parse_args()

    if args.debug:
        C.DEBUG_ON = True

    return args

def add_global_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enables debug-mode.",
    )

class Build:
    def __init__(
            self, 
            id: int, 
            name: str, 
            versionId: str | None, 
            projectVersionId: str | None, 
            experimental: bool, 
            installation: list[list[dict[str, str | int]]]
        ):
        self.id: int = id
        self.name: str = name
        self.versionId: str | None = versionId
        self.projectVersionId: str | None = projectVersionId
        self.experimental: bool = experimental
        self.installation: list[
            dict[str, str | int]
        ] = Build.resolve_installation(installation)

    @staticmethod
    def resolve_installation(input: list[list[dict[str, str | int]]]):
        installation = []

        for pack in input:
            installation += pack

        return installation

def select_build(builds_request: Any) -> Build:
    if not builds_request.get("builds", []):
        raise RuntimeError("Response contains no 'builds' list (single-build response?).")

    first = True
    stable = None

    builds: list[Build] = []
    for build in builds_request.get("builds"):
        is_latest_stable = not stable and not build["experimental"]

        suffix = (" (latest-stable)" if is_latest_stable else "") + (" (latest)" if first else "")

        temp = Build(
            id = build["id"],
            name = 
                build["name"] 
                + suffix,
            versionId = build["versionId"],
            projectVersionId = build["projectVersionId"],
            experimental = build["experimental"],
            installation = build["installation"]
        )
        if is_latest_stable:
            stable = temp
        else:
            builds.append(temp)
        
        first = False

    builds = ([stable] if stable else []) + builds

    return builds[ask_build(builds)]

def ask_build(builds: list[Build]) -> int:
    options = [
        questionary.Choice(
            title=("[STBL] " if not build.experimental else "[BETA] ") + build.name,
            value=i,
        )
        for i, build in enumerate(builds)
    ]
    return ask(questionary.select, "Select loader version.", choices=options)

def ensure_data(args: argparse.Namespace, flags: int) -> argparse.Namespace:
    if flags:
        if flags & C.NAME_F and not args.name:
            args.name = ask(questionary.text, "Server name:")

        if flags & C.VERSION_F and not args.version:
            args.version = ask(questionary.text, "Minecraft Version:")

        if flags & C.LOADER_F and not args.loader:
            args.loader = ask(questionary.autocomplete, "Loader:", choices=get_loaders())

        if flags & C.EDITOR_F and not args.editor:
            if editor := C.config.get("DEFAULTS", "editor"):
                args.editor = editor
            else:
                args.editor = ask(questionary.text, "Editor:")
                C.config.set("DEFAULTS", "Editor", args.editor)

        if flags & C.CONFIRM_DELETION_F and not args.confirm_override:
            args.confirm_override = confirm_with_ctrl_message("Are you sure you want to DELETE. This action is not reversable.", random_str(6))
    
    return args

def confirm_with_ctrl_message(message: str, ctrl: str, **kwargs) -> bool:
    out = questionary.text(message + f"\nType {ctrl} to confirm.", **kwargs).ask()

    if out is None:
        raise UserCancelledError("Interrupted in User Input.")
    sucess = out.strip() == ctrl
    if not sucess: log.error("Incorrect.")
    return sucess

def ask(prompt_type: Callable, message: str, **kwargs) -> Any:
    while True:
        out = prompt_type(message, **kwargs).ask(kbi_msg="")
        if out is None:
            raise UserCancelledError("Interrupted in User Input.")

        if isinstance(out, str):
            if out := out.strip():
                return out
        else: return out

        log.warning("Invalid input, please try again or press CTRL-C to exit.")
