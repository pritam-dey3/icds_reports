"""Make a `flet publish --no-cdn` bundle work when served as a static site.

Flet 1.0.4 gets two things wrong in that mode:

1. `index.html` pins `flet.pyodideUrl="pyodide/pyodide.mjs"`. The Python worker
   loads that URL with a dynamic `import()`, so a bare specifier is read as a
   package name and the browser throws
   `Failed to resolve module specifier 'pyodide/pyodide.mjs'`. Prefixing it
   with `./` resolves it against the worker's own URL instead.

2. Pyodide fetches its packages from the local runtime directory, but
   `flet publish` only copies the bare runtime into `dist/pyodide`. Any
   package the app imports (pandas, numpy, ...) plus its dependencies is
   therefore missing and micropip fails with `Failed to fetch`. They are
   downloaded here at build time and dropped next to the runtime.

Run this after `flet publish --no-cdn`.
"""

from __future__ import annotations

import json
import re
import shutil
import urllib.request
from pathlib import Path

import cyclopts
import tomllib

app = cyclopts.App(help=__doc__)

_CDN_WHEEL_URL = "https://cdn.jsdelivr.net/pyodide/v{version}/full/{filename}"


def _requirement_names(pyproject: Path) -> list[str]:
    """Top-level project dependency names, without extras or version specs."""
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    deps = data.get("project", {}).get("dependencies", [])
    return [re.split(r"[<>=!~\[; ]", dep, maxsplit=1)[0].strip() for dep in deps]


def _pyodide_closure(lock: dict, names: list[str]) -> set[str]:
    """Lock package names reachable from `names` through their dependencies."""
    seen: set[str] = set()
    pending = list(names)
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        package = lock["packages"].get(name)
        if package is None:
            continue
        seen.add(name)
        pending.extend(package.get("depends", []))
    return seen


def _fix_pyodide_url(index_html: Path) -> None:
    text = index_html.read_text(encoding="utf-8")
    fixed, count = re.subn(
        r'(flet\.pyodideUrl\s*=\s*")pyodide/pyodide\.mjs(")',
        r"\1./pyodide/pyodide.mjs\2",
        text,
    )
    if count == 0 and 'flet.pyodideUrl="./pyodide/pyodide.mjs"' not in text:
        raise RuntimeError("flet.pyodideUrl not found in index.html")
    if count:
        index_html.write_text(fixed, encoding="utf-8")
        print("Fixed flet.pyodideUrl specifier")


def _download_wheels(dist: Path, pyproject: Path) -> None:
    runtime = dist / "pyodide"
    version = json.loads((runtime / "package.json").read_text(encoding="utf-8"))[
        "version"
    ]
    lock = json.loads((runtime / "pyodide-lock.json").read_text(encoding="utf-8"))

    packages = lock["packages"]
    # `msgpack` carries submodule output back to the page; the worker loads it
    # with `loadPackage()` even when the app itself does not import it.
    wanted = _pyodide_closure(lock, _requirement_names(pyproject)) | {"msgpack"}

    for name in sorted(wanted):
        filename = packages[name]["file_name"]
        target = runtime / filename
        if target.exists():
            continue
        url = _CDN_WHEEL_URL.format(version=version, filename=filename)
        print(f"Downloading {filename}")
        with urllib.request.urlopen(url) as response, target.open("wb") as f:
            shutil.copyfileobj(response, f)


@app.default
def main(dist: Path, pyproject: Path = Path("pyproject.toml")) -> None:
    """Repair the built site in `dist` for no-CDN hosting.

    Args:
        dist: Output directory of `flet publish --no-cdn`.
        pyproject: Project file whose dependencies decide which wheels ship.
    """
    _fix_pyodide_url(dist / "index.html")
    _download_wheels(dist, pyproject)


if __name__ == "__main__":
    app()
