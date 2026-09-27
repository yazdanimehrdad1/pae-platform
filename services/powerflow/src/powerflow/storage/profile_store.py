"""ProfileStore: the load/PV profile scenarios, kept as CSV files (for now).

```
<root>/load/<scenario>.csv
<root>/pv/<scenario>.csv
```
Writes are atomic (temp file in the same folder, then os.replace). Names must match the
scenario pattern and resolve inside their folder, with an exact (case-sensitive) name match.
Content validation is the caller's job (SiteLibrary).
"""

import os
import tempfile
import threading
from enum import StrEnum
from pathlib import Path

from powerflow.errors import InvalidNameError, NotFoundError
from powerflow.storage.names import SCENARIO_NAME_PATTERN, check_name


class ProfileFolder(StrEnum):
    LOAD = "load"
    PV = "pv"


class ProfileStore:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._write_lock = threading.Lock()

    @property
    def root(self) -> Path:
        return self._root

    def list_profiles(self, folder: ProfileFolder) -> list[str]:
        directory = self._root / folder
        if not directory.is_dir():
            return []
        return sorted(path.stem for path in directory.glob("*.csv") if path.is_file())

    def profile_path(self, folder: ProfileFolder, scenario: str) -> Path:
        path = self._path(folder, scenario)
        if not (path.is_file() and f"{scenario}.csv" in _names(path.parent)):
            raise NotFoundError(f"no {folder} profile {scenario!r}")
        return path

    def read_profile_text(self, folder: ProfileFolder, scenario: str) -> str:
        return self.profile_path(folder, scenario).read_text(encoding="utf-8")

    def write_profile_text(self, folder: ProfileFolder, scenario: str, text: str) -> None:
        path = self._path(folder, scenario)
        text = text if text.endswith("\n") else text + "\n"
        with self._write_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".csv")
            try:
                with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as temp_file:
                    temp_file.write(text)
                os.replace(temp_name, path)
            except BaseException:
                Path(temp_name).unlink(missing_ok=True)
                raise

    def delete_profile(self, folder: ProfileFolder, scenario: str) -> None:
        path = self.profile_path(folder, scenario)
        with self._write_lock:
            path.unlink()

    def _path(self, folder: ProfileFolder, scenario: str) -> Path:
        check_name(scenario, SCENARIO_NAME_PATTERN, f"{folder} profile")
        directory = (self._root / folder).resolve()
        path = (directory / f"{scenario}.csv").resolve()
        if path.parent != directory:
            raise InvalidNameError(f"invalid {folder} profile name {scenario!r}")
        return path


def _names(folder: Path) -> set[str]:
    return {entry.name for entry in folder.iterdir()}
