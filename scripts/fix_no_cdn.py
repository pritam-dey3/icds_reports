"""Make a `flet publish --no-cdn` bundle work as an offline static site.

Flet 1.0.4 leaves four things broken for that:

1. `index.html` pins `flet.pyodideUrl="pyodide/pyodide.mjs"`, which the worker
   loads with `import()` - a bare specifier, so it throws
   `Failed to resolve module specifier`. A `./` prefix fixes it.
2. `flet publish` copies the bare runtime into `dist/pyodide`, so the wheels
   the app imports (pandas, numpy, ...) are missing. `pyodide-lock.json` names
   them; they are downloaded here.
3. `--no-cdn` points the font fallback at `assets/fonts/`, where Flet ships no
   fallback subsets. The ones this app needs are downloaded here.
4. Flet ships Flutter's stub worker (it unregisters itself on activate) and
   leaves the pure-Python packages for micropip to fetch from PyPI at runtime.
   Those go into `__pypackages__` inside `app.tar.gz`, which the worker already
   puts on `sys.path`, and a generated `sw.js` precaches the result.

`VERSION` is the commit this build came from, so each deploy installs into a
new cache and the previous one is dropped by the page that loads afterwards.

Run this after `flet publish --no-cdn`.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
import urllib.request
from pathlib import Path

import cyclopts
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

app = cyclopts.App(help=__doc__)

_CDN_WHEEL_URL = "https://cdn.jsdelivr.net/pyodide/v{version}/full/{filename}"
_GSTATIC_URL = "https://fonts.gstatic.com/s/{path}"

# flet imports repath, and micropip would fetch it from PyPI: it is not in the
# app's own dependency list.
_EXTRA_WHEELS = ["repath>=0.9.0"]
# uv writes these beside the packages it unpacks.
_WHEEL_JUNK = ["bin", ".lock"]

# Files the built page never requests: the dart2wasm renderer (this build is
# canvaskit) and Pyodide's native launchers. Leaving them out of the cache saves
# ~35 MB of install time and disk.
_UNUSED = {
    "main.dart.mjs",
    "main.dart.wasm",
    "pyodide/python",
    "pyodide/python.bat",
    "pyodide/python.exe",
    "pyodide/python_cli_entry.mjs",
    "pyodide/pyodide.js",
    "pyodide/pyodide.d.ts",
    "pyodide/ffi.d.ts",
}
# The two CanvasKit builds Flutter picks between at runtime: Chromium takes the
# `chromium` variant, every other engine the full one. Both are precached so an
# installed copy is offline whatever browser it was opened in. The skwasm,
# wimp and `experimental_webparagraph` variants are never selected here.
_CANVASKIT = {
    "canvaskit/canvaskit.js",
    "canvaskit/canvaskit.wasm",
    "canvaskit/chromium/canvaskit.js",
    "canvaskit/chromium/canvaskit.wasm",
}
_SKIP_SUFFIXES = {".map", ".symbols"}
# `VERSION` is the live release marker, and these two are never requested.
_NOT_CACHED = {"sw.js", "flutter_service_worker.js", "VERSION"}

# Noto subsets CanvasKit asks for when it meets a glyph Roboto and the icon font
# do not cover. Paths are relative to the fallback base, exactly as they are on
# Google's server. Add one here if the console reports a new unloadable font.
_FALLBACK_FONTS = [
    "notosanssymbols/v43/rP2up3q65FkAtHfwd-eIS2brbDN6gxP34F9jRRCe4W3gfQ8gb_VFRkzrbQ.woff2"
]


def _dependencies(pyproject: Path) -> list[Requirement]:
    """The project's dependencies, parsed."""
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    return [Requirement(dep) for dep in data["project"]["dependencies"]]


def _pyodide_closure(lock: dict, names: list[str]) -> set[str]:
    """Lock package names reachable from `names` through their dependencies."""
    seen: set[str] = set()
    pending = list(names)
    while pending:
        name = pending.pop()
        if name in seen or name not in lock["packages"]:
            continue
        seen.add(name)
        pending.extend(lock["packages"][name].get("depends", []))
    return seen


def _patch_index(index_html: Path, boot_js: str) -> None:
    """Make the page work from a static host, and load the offline boot script.

    Fixes `flet.pyodideUrl` (a bare specifier, which `import()` cannot resolve)
    and the font fallback base. Every substitution is a no-op once applied, so
    this also runs on a build that was already patched.
    """
    text = index_html.read_text(encoding="utf-8")
    text = re.sub(
        r'(flet\.pyodideUrl\s*=\s*")pyodide/pyodide\.mjs(")',
        r"\1./pyodide/pyodide.mjs\2",
        text,
    )
    text = re.sub(
        r'flet\.fontFallbackBaseUrl\s*=\s*"[^"]*"',
        'flet.fontFallbackBaseUrl="assets/fonts/"',
        text,
    )
    if f'<script src="{boot_js}"></script>' not in text:
        text = re.sub(
            r'<script src="python\.js"></script>',
            lambda match: f'{match.group(0)}\n  <script src="{boot_js}"></script>',
            text,
        )

    assert 'flet.pyodideUrl="./pyodide/pyodide.mjs"' in text
    assert 'flet.fontFallbackBaseUrl="assets/fonts/"' in text
    assert f'<script src="{boot_js}"></script>' in text
    index_html.write_text(text, encoding="utf-8")

    print("Patched index.html")


def _download(url: str, target: Path) -> None:
    """Fetch `url` to `target`, unless it is already there."""
    if target.exists():
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {target.name}")
    with urllib.request.urlopen(url) as response:
        target.write_bytes(response.read())


def _download_fallback_fonts(dist: Path) -> None:
    for path in _FALLBACK_FONTS:
        _download(_GSTATIC_URL.format(path=path), dist / "assets" / "fonts" / path)


def _download_wheels(dist: Path, pyproject: Path, lock: dict) -> None:
    """Fetch the lock's wheels for the app's dependencies into `dist/pyodide`."""
    runtime = dist / "pyodide"
    version = json.loads((runtime / "package.json").read_text(encoding="utf-8"))[
        "version"
    ]
    # `msgpack` carries submodule output back to the page; the worker loads it
    # with `loadPackage()` even when the app itself does not import it.
    names = [canonicalize_name(dep.name) for dep in _dependencies(pyproject)]
    for name in sorted(_pyodide_closure(lock, names) | {"msgpack"}):
        filename = lock["packages"][name]["file_name"]
        _download(
            _CDN_WHEEL_URL.format(version=version, filename=filename),
            runtime / filename,
        )


def _vendor(dist: Path, pyproject: Path, lock: dict) -> None:
    """Unpack the pure-Python wheels micropip would fetch from PyPI."""
    wanted = [
        str(dep)
        for dep in _dependencies(pyproject)
        if canonicalize_name(dep.name) not in lock["packages"]
    ] + _EXTRA_WHEELS

    archive = dist / "app.tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        packages, payload = root / "packages", root / "payload"
        subprocess.run(
            ["uv", "pip", "install", "--target", str(packages), "--no-deps", *wanted],
            check=True,
        )
        # The worker puts `__pypackages__` on `sys.path` before installing
        # `requirements.txt`, so micropip sees these as already satisfied and
        # resolves the rest (pandas, numpy, six) from the local runtime.
        shutil.unpack_archive(archive, payload, "gztar")
        shutil.copytree(
            packages,
            payload / "__pypackages__",
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(*_WHEEL_JUNK),
        )
        shutil.make_archive(str(archive)[: -len(".tar.gz")], "gztar", root_dir=payload)
    print(f"Bundled {len(wanted)} PyPI packages into {archive.name}")


def _precache(dist: Path) -> list[str]:
    """Every URL the built app can request, relative to the worker scope."""
    files = [
        path.relative_to(dist).as_posix() for path in dist.rglob("*") if path.is_file()
    ]
    return sorted(
        name
        for name in files
        if name not in _UNUSED
        and name not in _NOT_CACHED
        and Path(name).suffix not in _SKIP_SUFFIXES
        and (not name.startswith("canvaskit/") or name in _CANVASKIT)
    )


def _patch_flutter_bootstrap(bootstrap_js: Path) -> None:
    """Stop Flutter registering its stub worker, and revealing the page early.

    Flet drops the loading overlay at the first frame, which paints before
    Python has started; `boot.js` drops it instead, once the app is up.
    """
    text = bootstrap_js.read_text(encoding="utf-8")
    # The literal version is what `flet publish` writes; the minified loader
    # above it only ever has `serviceWorkerVersion:r`.
    if not re.search(r'serviceWorkerVersion:\s*"', text):
        return
    text = re.sub(r"\n\s*serviceWorkerSettings:\s*\{[^}]*\},", "", text)
    text = re.sub(
        r"\s*window\.addEventListener\('flutter-first-frame', \(\) => \{\s*"
        r"document\.getElementById\('loading'\)\?\.remove\(\);\s*\}, "
        r"\{ once: true \}\);",
        "",
        text,
    )
    bootstrap_js.write_text(text, encoding="utf-8")
    print("Disabled Flutter's stub service worker")


def _release() -> str:
    """The cache's release id: the commit this build came from.

    `RELEASE_ID` overrides it, for a build from an archive with no `.git`.
    """
    if override := os.environ.get("RELEASE_ID"):
        return override[:12]
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout.strip()
    except OSError, subprocess.CalledProcessError:
        # CI exports a SHA too, for checkouts without a .git directory.
        return os.environ.get("GITHUB_SHA", "")[:12] or "dev"


@app.default
def main(
    dist: Path, pyproject: Path = Path("pyproject.toml"), assets: Path = Path("scripts")
) -> None:
    """Repair the built site in `dist` for no-CDN, offline hosting.

    Args:
        dist: Output directory of `flet publish --no-cdn`.
        pyproject: Project file whose dependencies decide which wheels ship.
        assets: Directory holding the `sw.js` and `boot.js` templates.
    """
    version = _release()

    _download_fallback_fonts(dist)

    lock = json.loads((dist / "pyodide" / "pyodide-lock.json").read_text("utf-8"))
    _download_wheels(dist, pyproject, lock)
    _vendor(dist, pyproject, lock)

    boot = assets / "boot.js"
    (dist / boot.name).write_text(
        boot.read_text(encoding="utf-8").replace("__VERSION__", version),
        encoding="utf-8",
    )
    _patch_index(dist / "index.html", boot.name)
    _patch_flutter_bootstrap(dist / "flutter_bootstrap.js")
    (dist / "flutter_service_worker.js").unlink(missing_ok=True)

    precache = _precache(dist)
    (dist / "sw.js").write_text(
        (assets / "sw.js")
        .read_text(encoding="utf-8")
        .replace("__VERSION__", json.dumps(version))
        .replace("__PRECACHE__", json.dumps(precache, indent=2)),
        encoding="utf-8",
    )
    (dist / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    print(f"Wrote sw.js with {len(precache)} URLs (release {version})")


if __name__ == "__main__":
    app()
