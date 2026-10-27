from typing import Any
import requests
import mcwaiter.constants as C
from mcwaiter.logger import logger as log
import json
from datetime import datetime

def _req_get(*args, **kwargs) -> requests.Response:
    response = requests.get(*args, **kwargs)

    response.raise_for_status()

    if C.DEBUG_ON:
        timestamp = datetime.now().astimezone().isoformat()
        apilogs_dir = C.CONFIG_DIR / ".debug" / "api"
        apilogs_dir.mkdir(parents=True, exist_ok=True)

        filename = (str(timestamp) + str(args[0][str(args[0]).find("api") + 4::]).lower()).replace("/", "-").replace(":", "-") + ".json"
        log.debug(filename)
        file = apilogs_dir / filename
        log.debug("Created debug-log of API request at " + str(file))
        with open(file, "w") as f:
            data = response.json()
            data = {
                "_mcwaiter_timestamp": timestamp,
                "_mcwaiter_filename": filename,
                "_mcwaiter_args": {
                    "kwargs": kwargs,
                    "args": args,
                },
                "response": data,
            }

            json.dump(data, f, indent=4)
    return response

def get_loaders() -> dict:
    response = _req_get(C.API + "v2/types", timeout=10)
    data = response.json()

    if not data.get("success"):
        raise RuntimeError("Failed to fetch server types")

    loaders = data["types"]["recommended"]
    for cat, catloaders in data["types"].items():
        loaders = loaders | catloaders
    return loaders

def get_builds(mcversion: str, loader: str, version: str | None = None) -> tuple[Any, bool]:
    """Returns build[s] and a bool whether or not it has multiple builds."""
    if version:
        params = {
            "versionId": str(mcversion),
            "type": str(loader),
            "projectVersionId": str(version),
        }
    
        response = _req_get(C.API + "v2/build", timeout=10, params=params)
    else:
        response = _req_get(C.API + f"v2/builds/{str(loader).upper()}/{str(mcversion)}", timeout=10)

    result = response.json()

    if not result.get("success"):
        raise RuntimeError("Failed to fetch builds.")
    
    result: dict
    return result, bool(result.get("builds"))

def download(url: str, filepath: str, size: int):
    pass # wip