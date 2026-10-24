import requests
import mcwaiter.constants as C
from mcwaiter.logger import logger as log

def get_loaders() -> dict:
    response = requests.get(C.API + "v2/types", timeout=10)
    response.raise_for_status()

    data = response.json()

    if not data.get("success"):
        raise RuntimeError("Failed to fetch server types")

    log.debug(data["types"])

    loaders = data["types"]["recommended"]
    for cat, catloaders in data["types"].items():
        loaders = loaders | catloaders
    return loaders