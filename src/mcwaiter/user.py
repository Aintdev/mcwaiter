
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
    return bool(
        isinstance(username, str)
        and _USERNAME_PATTERN.fullmatch(username)
    )

def user_exists(username: str) -> bool:
    try:
        pwd.getpwnam(username)
        return True
    except KeyError:
        return False

def group_exists(groupname: str) -> bool:
    try:
        grp.getgrnam(groupname)
        return True
    except KeyError:
        return False

def get_user(username: str) -> UserInfo:
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

def create_group(groupname: str) -> None:
    if not validate_username(groupname):
        raise ValueError(f"Invalid group name: {groupname}")

    if group_exists(groupname):
        raise FileExistsError(f"Group already exists: {groupname}")

    subprocess.run(
        ["groupadd", "--system", groupname],
        check=True,
    )

def create_user(username: str) -> None:
    if not validate_username(username):
        raise ValueError(f"Invalid username: {username}")

    if user_exists(username):
        raise FileExistsError(f"User already exists: {username}")

    subprocess.run(
        [
            "useradd",
            "--system",
            "--user-group",
            "--no-create-home",
            "--home-dir", "/nonexistent",
            "--shell", "/usr/sbin/nologin",
            username,
        ],
        check=True,
    )

def ensure_user(username: str) -> UserInfo:
    if not validate_username(username):
        raise ValueError(f"Invalid username: {username}")

    if not user_exists(username):
        create_user(username)

    return get_user(username)
