"""Every exact pin in a service's requirements.txt has the same version in its requirements.lock,
which the Dockerfile installs. Dependabot updates requirements.txt only; this fails such a pull
request until the lock is regenerated from a rebuilt image."""

import re

import pytest

from tests.unit._qrosetta_fake import REPO

PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)(\[[^\]]*\])?\s*==\s*([^\s;#]+)")
SERVICE_DIRS = sorted([REPO / "rosetta-api", *REPO.glob("runners/*-runner"), *REPO.glob("compilers/*-compiler")])


def _pins(path):
    found = {}
    for line in path.read_text().splitlines():
        match = PIN.match(line.strip())
        if match:
            found[re.sub(r"[-_.]+", "-", match.group(1)).lower()] = match.group(3)
    return found


@pytest.mark.parametrize("directory", SERVICE_DIRS, ids=lambda d: d.relative_to(REPO).as_posix())
def test_requirements_pins_equal_the_lock(directory):
    wanted = _pins(directory / "requirements.txt")
    locked = _pins(directory / "requirements.lock")
    assert wanted
    differ = {name: (version, locked.get(name)) for name, version in wanted.items() if locked.get(name) != version}
    assert not differ, f"{directory.name}: requirements.txt pin != requirements.lock: {differ}"
