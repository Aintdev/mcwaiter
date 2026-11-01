
import os
from pathlib import Path
import pwd
import grp
import re
import subprocess
from dataclasses import dataclass

_USERNAME_PATTERN = re.compile(r"^[a-z_][a-z0-9_-]{0,31}\$?$")

@dataclass(frozen=True, slots=True)
class UserInfo:
    username: str
    uid: int
    gid: int
    home: str
    shell: str
    primary_group: str

def validate_username(username: str) -> bool:
    username = username.lower()
    return bool(
        isinstance(username, str)
        and _USERNAME_PATTERN.fullmatch(username)
    )

def user_own(user: UserInfo, path: Path) -> None:
    os.chown(path, user.uid, user.gid, follow_symlinks=False)
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            os.chown(os.path.join(root, name), user.uid, user.gid, follow_symlinks=False)

def sudo_permissions_fix(path: Path) -> None:
    if (sudo_user := os.environ.get("SUDO_USER")) and os.geteuid() == 0:
        user_own(get_user(sudo_user), path)

def user_exists(username: str) -> bool:
    username = username.lower()
    try:
        pwd.getpwnam(username)
        return True
    except KeyError:
        return False

def get_user(username: str) -> UserInfo:
    username = username.lower()
    try:
        entry = pwd.getpwnam(username)
    except KeyError:
        raise LookupError(f"User does not exist: {username}") from None

    try:
        primary_group = grp.getgrgid(entry.pw_gid).gr_name
    except KeyError:
        primary_group = str(entry.pw_gid)

    return UserInfo(
        username=entry.pw_name,
        uid=entry.pw_uid,
        gid=entry.pw_gid,
        home=entry.pw_dir,
        shell=entry.pw_shell,
        primary_group=primary_group,
    )

def create_user(username: str, homedir: Path) -> None:
    username = username.lower()
    if not validate_username(username):
        raise ValueError(f"Invalid username: {username}")

    if user_exists(username):
        raise FileExistsError(f"User already exists: {username}")

    command = [
    "useradd",
    "--system",
    "--user-group",
    ]

    if homedir:
        command.extend(["--create-home", "--home-dir", str(homedir)])
    else:
        command.extend(["--no-create-home", "--home-dir", "/nonexistent"])

    command.extend([
        "--shell", "/usr/sbin/nologin",
        username,
    ])

    subprocess.run(command, check=True)

def delete_user(username: str, *, remove_home: bool = False) -> None:
    username = username.lower()
    if not validate_username(username):
        raise ValueError(f"Invalid username: {username}")

    try:
        entry = pwd.getpwnam(username)
    except KeyError:
        raise LookupError(f"User does not exist: {username}") from None

    command = ["userdel"]

    if remove_home:
        command.append("--remove")

    command.append(entry.pw_name)

    subprocess.run(command, check=True)

def ensure_user(username: str) -> UserInfo:
    username = username.lower()
    if not validate_username(username):
        raise ValueError(f"Invalid username: {username}")

    if not user_exists(username):
        create_user(username)

    return get_user(username)
