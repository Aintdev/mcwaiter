import random
import string

def random_str(N: int) -> str:
    # Source - https://stackoverflow.com/a/2257449
    # Posted by Ignacio Vazquez-Abrams, modified by community. See post 'Timeline' for change history
    # Retrieved 2026-10-24, License - CC BY-SA 4.0

    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=N))

def parse_loader(arg: str) -> tuple[str, str | None]:
    if "@" in arg:
        name, ver = arg.split("@", 1)
        return (name, ver)

    return (arg, None)