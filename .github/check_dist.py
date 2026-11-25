"""Check that the built wheel and source archive are this project as
``pyproject.toml`` describes it, with its packages and no other, and with the
license texts. Print ``version=...`` for the workflow.

Usage: check_dist.py <directory with the built files>
"""

import sys
import tarfile
import zipfile
from pathlib import Path

import tomllib

dist = Path(sys.argv[1])
project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
name, version = project["name"], project["version"]
wheels, archives = list(dist.glob("*.whl")), list(dist.glob("*.tar.gz"))
if len(wheels) != 1 or len(archives) != 1:
    sys.exit(f"Expected one wheel and one source archive in {dist}")
problems = []

with zipfile.ZipFile(wheels[0]) as wheel:
    names = wheel.namelist()
    info = f"{name}-{version}.dist-info"
    expected = {name, f"{name}_cli", f"{name}_data", f"{name}_scripts", info}
    top = {path.split("/")[0] for path in names}
    if top != expected:
        problems.append(f"the wheel has {sorted(top)}, expected {sorted(expected)}")
    metadata = wheel.read(f"{info}/METADATA").decode().splitlines()
    problems.extend(
        f"the metadata of the wheel lacks {line!r}"
        for line in (
            f"Name: {name}",
            f"Version: {version}",
            "License-Expression: BSD-3-Clause",
        )
        if line not in metadata
    )
    problems.extend(
        f"the wheel lacks {text}"
        for text in ("LICENSE", "NOTICE")
        if not any(
            path.startswith(info) and path.endswith("/" + text) for path in names
        )
    )
    # Nothing of this package may import the package that it is a copy of.
    for path in names:
        if path.endswith(".py"):
            lines = wheel.read(path).decode().splitlines()
            problems.extend(
                f"{path}:{number} imports dateparser"
                for number, line in enumerate(lines, 1)
                if line.strip().startswith(("import dateparser", "from dateparser"))
            )

with tarfile.open(archives[0]) as archive:
    members = {m.name.split("/", 1)[1] for m in archive.getmembers() if "/" in m.name}
    problems.extend(
        f"the source archive lacks {needed}"
        for needed in ("LICENSE", "NOTICE", "README.md", f"{name}/__init__.py")
        if needed not in members
    )

if problems:
    sys.exit("\n".join(problems))
print(f"version={version}")
