import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import subprocess
import mcwaiter.helpers as h
from mcwaiter.logger import logger as log
import mcwaiter.constants as C
from mcwaiter.errors import NoVersionFoundError, UserCancelledError
from mcwaiter.requests import get_loaders
from mcwaiter.config import save_config
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
        metavar='{command}',
    )

    shell = subparser.add_parser(
        "shell",
        help="Opens shell as that servers user."
    )
    add_global_arguments(shell)
    shell.add_argument("name", type=str, help="Name of the Minecraft Server.")

    edit = subparser.add_parser(
        "edit",
        help="Edit a file in a server."
    )

    edit.add_argument("name", type=str, help="Name of the Minecraft Server.")
    edit.add_argument("relpath", type=str, help="Path to file relative to server root.")
    add_global_arguments(edit)

    chown = subparser.add_parser(
        "chown",
        help="Fixes ownership of all Minecraft server files.",
    )
    
    chown.add_argument("name", type=str, help="Name of the Minecraft Server.")
    add_global_arguments(chown)

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
    delete.add_argument("name", type=str, help="Name of the Minecraft Server.")
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
        "-e",
        "--editor",
        nargs="?",
        type=str,
    )

    config.add_argument("-n", "--name", type=str, help="Name of the Minecraft Server.", default=None)

    start = subparser.add_parser("start", help="Start a server")
    add_global_arguments(start)
    start.add_argument("name", type=str, help="Name of the Minecraft Server.")

    stop = subparser.add_parser("stop", help="Stop a server")
    add_global_arguments(stop)
    stop.add_argument("name", type=str, help="Name of the Minecraft Server.")

    status = subparser.add_parser("status", help="Get status of Server.")
    add_global_arguments(status)
    status.add_argument("name", type=str, help="Name of the Minecraft Server.")

    ls = subparser.add_parser("ls", help="See all installed Servers")
    add_global_arguments(ls)

    autostart = subparser.add_parser("autostart", description="Start all servers that have auto_start enabled in alphabetic order.")
    
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

def make_jvm_args(args, directory: Path) -> None:
    with open(directory / "user_jvm_args.txt", "w", encoding="utf-8") as f:
        f.write(
"""# ============================================================
#  user_jvm_args.txt - JVM arguments for the Minecraft server
# ============================================================
#  Loaded by the start script via `java @user_jvm_args.txt ...`
#  Lines starting with # are comments. One argument per line.
#  Best to put comments on their own lines, not after an argument.
# ============================================================

# --- RAM -----------------------------------------------------
# -Xms = initial heap, -Xmx = maximum heap.
# For servers, set both to the same value so the JVM doesn't have
# to resize the heap at runtime (fewer stutters).
# Don't allocate all of the system RAM: leave about 2 GB for the
# operating system and off-heap memory.
-Xms6G
-Xmx6G

# --- Garbage collector (Aikar flags, for heaps up to ~12 GB) -
# G1 is the default GC and works well for Minecraft.
-XX:+UseG1GC
-XX:+ParallelRefProcEnabled
-XX:MaxGCPauseMillis=200
-XX:+UnlockExperimentalVMOptions
-XX:+DisableExplicitGC
-XX:+AlwaysPreTouch
-XX:G1NewSizePercent=30
-XX:G1MaxNewSizePercent=40
-XX:G1HeapRegionSize=8M
-XX:G1ReservePercent=20
-XX:G1HeapWastePercent=5
-XX:G1MixedGCCountTarget=4
-XX:InitiatingHeapOccupancyPercent=15
-XX:G1MixedGCLiveThresholdPercent=90
-XX:G1RSetUpdatingPauseTimePercent=5
-XX:SurvivorRatio=32
-XX:+PerfDisableSharedMem
-XX:MaxTenuringThreshold=1

# --- Misc ----------------------------------------------------
# Consistent character encoding, avoids problems with special
# characters.
-Dfile.encoding=UTF-8

# Write a heap dump on OutOfMemoryError (useful for debugging).
# Comment these out if the files get too big.
-XX:+HeapDumpOnOutOfMemoryError
-XX:HeapDumpPath=./crash-reports

# --- Optional: GC log ----------------------------------------
# Only enable this if you want to analyze lag spikes.
# -Xlog:gc*:file=logs/gc.log:time,uptime:filecount=5,filesize=10M
""")
    confirm = ask(questionary.confirm, "Do you want to edit the jvm args?")
    if confirm:
        h.edit_file(directory / "user_jvm_args.txt")

@dataclass(frozen=True)
class JavaVersion:
    display_name: str = field(compare=False)
    main_version_id: int | None  = field(compare=True)
    path: Path | None = field(compare=False)
    new_flag: bool = field(default=False, compare=False)

def get_java_path(req_version: int) -> JavaVersion:
    java_version_auto = JavaVersion("Symlink", -1, C.config.get("JAVA", "auto"), new_flag=False)

    java_versions: set[JavaVersion] = set()
    java_versions.add(JavaVersion("Manually enter path", None, None, False))
    java_versions.add(java_version_auto)

    for jdk_name, jdk_path in C.config.items("JAVA"):
        if jdk_name == "auto":
            continue

        main_version: int = int(jdk_name.split("-")[1])
        if main_version < req_version:
            continue

        ver = JavaVersion(
            display_name= f"{jdk_name}", 
            main_version_id= main_version,
            path= Path(jdk_path)
        )

        if req_version == ver.main_version_id:
            return ver
        java_versions.add(ver)
        

    new: set[JavaVersion] = h.find_javas()
    diff = new - java_versions
    added = False
    for java in diff:
        C.config.set("JAVA", java.display_name, str(java.path))
        added = True

    if added:
        save_config()

    for java in new.copy():
        if java.main_version_id < req_version or java in java_versions:
            new.remove(java)
        if java.main_version_id == req_version:
            return java

    java_versions |= new

    log.error("Didn't automatically find avaialble Java version.")

    if java_versions:
        answer: JavaVersion = ask_java_version(java_versions, req_version)
        if answer.display_name == "Manually enter path":
            java = Path(ask(questionary.path, f"Please enter path to your Java {req_version} binary."))

            try:
                result = subprocess.run(
                    [str(java), "--version"],
                    capture_output=True,
                    text=True,
                    check=True,
                    cwd="/",
                )
            except Exception as e:
                raise NoVersionFoundError("Given path is not useable: " + str(e))
                
            version = result.stdout.split()[1]
            java_version = int(version.split(".")[0])

            if java_version >= req_version:
                return JavaVersion(
                    display_name=java.parent.parent.name,
                    main_version_id=java_version,
                    path=java
                )
        elif answer: return answer
    raise NoVersionFoundError("Java version " + str(req_version) + " not found.")

def ask_java_version(versions: set[JavaVersion], req_version) -> JavaVersion:
    options = [
        questionary.Choice(
            title=("[NEW] " if version.new_flag else "") + version.display_name,
            value=version,
        )
        for version in versions if version.display_name not in ("Manually enter path", "Symlink") 
    ]

    options[:0] = [questionary.Choice(title=v.display_name, value=v) for v in versions if v.display_name in ("Manually enter path", "Symlink") ]
    return ask(questionary.select, f"Select java version. Server expects java {req_version}", choices=options)

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
            args.confirm_override = confirm_with_ctrl_message("Are you sure you want to DELETE. This action is not reversable.", h.random_str(6))
    
    return args

def confirm_with_ctrl_message(message: str, ctrl: str, **kwargs) -> bool:
    out = questionary.text(message + f"\nType {ctrl} to confirm.", **kwargs).ask()

    if out is None:
        raise UserCancelledError("Interrupted in User Input.")
    sucess = out.strip() == ctrl
    if not sucess: log.error("Incorrect.")
    return sucess

def ask(prompt_type: Callable, message: str, can_cancel=False, **kwargs) -> Any:
    while True:
        out = prompt_type(message, **kwargs).ask(kbi_msg="")
        if out is None:
            if not can_cancel:
                raise UserCancelledError("Interrupted in User Input.")
            return False if prompt_type == questionary.confirm else None
        if isinstance(out, str):
            if out := out.strip():
                return out
        else: return out

        log.warning("Invalid input, please try again or press CTRL-C to exit.")
