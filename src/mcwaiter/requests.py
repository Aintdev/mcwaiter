from pathlib import Path
from typing import Any
import requests
from tqdm import tqdm
import mcwaiter.constants as C
from mcwaiter.logger import logger as log
from mcwaiter.errors import DownloadError
from mcwaiter.user import sudo_permissions_fix
from time import sleep
import json
from datetime import datetime

_session = requests.Session()
_session.headers.update({
    "User-Agent": f"Aintdev/mcwaiter/{C.APP_VERSION}"
})

_TRY_AGAIN_SECONDS = 3

def _req(method: str, *args, **kwargs) -> requests.Response:
    response = _session.request(method, *args, **kwargs)

    response.raise_for_status()

    if C.DEBUG_ON:
        timestamp = datetime.now().astimezone().isoformat()
        apilogs_dir = C.CONFIG_DIR / ".debug" / "api"
        apilogs_dir.mkdir(parents=True, exist_ok=True)

        filename = (str(timestamp) + str(args[0][str(args[0]).find("api") + 4::]).lower()).replace("/", "-").replace(":", "-") + ".json"
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
        sudo_permissions_fix(apilogs_dir)

    return response

def _req_get(*args, **kwargs) -> requests.Response:
    return _req("GET", *args, **kwargs)

def _req_post(*args, **kwargs) -> requests.Response:
    return _req("POST", *args, **kwargs)

def get_java_version(minecraft_version: str) -> int:
    manifest = _req_get(
        "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
    ).json()

    version = next(
        v for v in manifest["versions"]
        if v["id"] == minecraft_version
    )

    version_data = requests.get(version["url"]).json()

    log.debug("Required java version: " + str(version_data["javaVersion"]["majorVersion"]))
    return version_data["javaVersion"]["majorVersion"]

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
            "type": str(loader),
            "versionId": str(mcversion),
            "projectVersionId": str(version)
        }
    
        response = _req_post(C.API + "v2/build", timeout=10, json=params)
    else:
        response = _req_get(C.API + f"v2/builds/{str(loader).upper()}/{str(mcversion)}", timeout=10)

    result = response.json()

    if not result.get("success"):
        raise RuntimeError("Failed to fetch builds.")
    
    result: dict
    return result, not bool(result.get("build")) 

def download(
        url: str, 
        filepath: Path, 
        show_progressbar: bool = True,
        expected_filesize: int = None,
        _attempt: int = 0
    ):
    try:
        directory = filepath.parent
        final_filename = filepath.name
        temp_filename = final_filename + ".part"
        temp_file = directory / temp_filename

        try:
            with _session.get(
                url, stream=True, timeout=(10, 10)
            ) as response:
                response.raise_for_status()

                total_size = int(
                    response.headers.get("content-length", 0)
                )

                if total_size != expected_filesize:
                    log.debug("Header filesize is not the same as the api given filesize. Continuing anyway.")

                log.info(f"Starting download of {final_filename}.")

                with tqdm(
                    total=total_size,
                    unit="B",
                    unit_scale=True,
                    disable=not show_progressbar,
                ) as progress_bar:
                    with temp_file.open("wb") as file:
                        for data in response.iter_content(64 * 1024):

                            if not data:
                                continue

                            file.write(data)
                            progress_bar.update(len(data))

            downloaded_size = temp_file.stat().st_size
            if total_size and downloaded_size != total_size:
                raise RuntimeError(
                    f"Incomplete download: expected {total_size} bytes, "
                    f"got {downloaded_size}"
                )

            temp_file.rename(filepath)
            return True
        
        finally:
            try:
                temp_file.unlink(missing_ok=True)
            except OSError as error:
                log.warning(
                    f"Could not remove temporary file {temp_filename}: {error}"
                )
    except KeyboardInterrupt:
        log.info("Download cancelled by user.")
        raise
    except Exception as error:
        log.error(
            f"Download failed for {filepath.name}: {error}"
        )

        if _attempt >= 2:
            raise DownloadError("Something went wrong during the download (3 tries).")

        log.info(f"Trying again in {_TRY_AGAIN_SECONDS} seconds.")
        sleep(_TRY_AGAIN_SECONDS)

        return download(
            url = url,
            filepath = filepath,
            show_progressbar = show_progressbar,
            expected_filesize = expected_filesize,
            _attempt=_attempt + 1,
        )