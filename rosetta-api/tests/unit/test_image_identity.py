"""Each runner and compiler result carries the identity of the image it ran from, read by the
serving process from a file baked at build, and whether the image's architecture differs from
the host's; the timed child's environment is unchanged."""
import asyncio
import hashlib
import os
import platform
import re
from pathlib import Path

import pytest

from qrosetta_commons import image_identity
from qrosetta_commons.helpers import ExecutionSlots
from tests.unit import _isolated_fixture as fx

REPO = Path(__file__).resolve().parents[3]
IMAGE_DIRS = sorted(p.parent for p in [*REPO.glob("runners/*/Dockerfile"), *REPO.glob("compilers/*/Dockerfile")])


@pytest.fixture
def baked(tmp_path, monkeypatch):
    """An image filesystem: the identity file and two build files."""
    identity = tmp_path / "identity"
    identity.write_text("source=built_locally\nrelease=\ngit_sha=abc1234\n")
    build = tmp_path / "build"
    build.mkdir()
    (build / "Dockerfile").write_bytes(b"FROM x\n")
    (build / "requirements.lock").write_bytes(b"qiskit==1.0\n")
    monkeypatch.setattr(image_identity, "IDENTITY_FILE", identity)
    monkeypatch.setattr(image_identity, "BUILD_FILES_DIR", build)
    monkeypatch.setattr(image_identity, "_CONTAINERENV", tmp_path / "absent")
    monkeypatch.setattr(image_identity, "_DOCKERENV", tmp_path / "absent")
    monkeypatch.delenv("APPTAINER_CONTAINER", raising=False)
    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
    for var in image_identity.HOST_ENV_VARS.values():
        monkeypatch.delenv(var, raising=False)
    image_identity._identity.cache_clear()
    image_identity.build_file_hashes.cache_clear()
    image_identity.take_host_environment.cache_clear()
    yield tmp_path
    image_identity._identity.cache_clear()
    image_identity.build_file_hashes.cache_clear()
    image_identity.take_host_environment.cache_clear()


def test_baked_identity_values(baked):
    assert image_identity.baked_identity() == {
        "source": "built_locally", "release": None, "git_sha": "abc1234", "identity_file": "present"}
    (baked / "identity").write_text("source=release\nrelease=1.2.0\ngit_sha=abc1234\n")
    assert image_identity.baked_identity()["source"] == "release"
    assert image_identity.baked_identity()["release"] == "1.2.0"
    (baked / "identity").write_text("source=unknown\nrelease=\ngit_sha=unknown\n")
    assert image_identity.baked_identity()["source"] == "not recorded"
    (baked / "identity").unlink()
    absent = image_identity.baked_identity()
    assert absent["source"] == "not recorded" and absent["identity_file"].startswith("absent")


def test_container_view(baked, monkeypatch):
    assert image_identity.container_view() == {"engine": "not recorded"}
    env = baked / "containerenv"
    env.write_text('engine="podman-5.8.2"\nname="qiskit"\nimage="localhost/q:latest"\nimageid="7f7c"\n')
    monkeypatch.setattr(image_identity, "_CONTAINERENV", env)
    assert image_identity.container_view() == {"engine": "podman-5.8.2", "image": "localhost/q:latest",
                                               "image_id": "7f7c", "container_name": "qiskit"}
    monkeypatch.setenv("APPTAINER_CONTAINER", "/scratch/q.sif")
    monkeypatch.setenv("QROSETTA_IMAGE_SHA256", "ff" * 32)
    assert image_identity.container_view() == {"engine": "apptainer", "image": "/scratch/q.sif",
                                               "image_sha256": "ff" * 32}


def test_hypervisor_flag(tmp_path, monkeypatch):
    cpuinfo = tmp_path / "cpuinfo"
    monkeypatch.setattr(image_identity, "_CPUINFO", cpuinfo)
    cpuinfo.write_text("model name\t: X\nflags\t\t: fpu sse2 hypervisor avx\n")
    assert image_identity.hypervisor_cpu_flag() is True
    cpuinfo.write_text("flags\t\t: fpu sse2 avx\n")
    assert image_identity.hypervisor_cpu_flag() is False
    cpuinfo.write_text("processor : 0\n")
    assert image_identity.hypervisor_cpu_flag() is None


def _elf(machine, elf_class=2, data=1):
    order = "little" if data == 1 else "big"
    return (b"\x7fELF" + bytes([elf_class, data, 1]) + bytes(9) + (2).to_bytes(2, order)
            + machine.to_bytes(2, order) + bytes(44))


@pytest.mark.parametrize("header,arch", [
    (_elf(62), "x86_64"),
    (_elf(183), "aarch64"),
    (_elf(21), "ppc64le"),
    (_elf(21, data=2), "ppc64"),
    (_elf(22, data=2), "s390x"),
    (_elf(243), "riscv64"),
    (_elf(3, elf_class=1), None),
    (_elf(40, elf_class=1), None),
    (_elf(9999), None),
    (b"#!/bin/sh\n", None),
])
def test_image_architecture_from_the_elf_header(tmp_path, header, arch):
    exe = tmp_path / "python"
    exe.write_bytes(header)
    assert image_identity.image_architecture(str(exe)) == arch


def test_image_architecture_of_this_interpreter_and_a_missing_file(tmp_path):
    assert image_identity.image_architecture() == image_identity.normalise_arch(platform.machine())
    assert image_identity.image_architecture(str(tmp_path / "absent")) is None


def test_normalise_arch():
    assert image_identity.normalise_arch("arm64") == "aarch64"
    assert image_identity.normalise_arch("AMD64") == "x86_64"
    assert image_identity.normalise_arch(" x86_64 ") == "x86_64"
    assert image_identity.normalise_arch("aarch64") == "aarch64"
    assert image_identity.normalise_arch("") is None and image_identity.normalise_arch(None) is None


def test_emulation_compares_the_image_with_the_host(monkeypatch):
    emulated = image_identity.emulation({"os": "Darwin", "arch": "arm64"}, "x86_64")
    assert emulated["emulated"] is True
    assert (emulated["image_arch"], emulated["host_arch"], emulated["host_os"]) == ("x86_64", "aarch64", "Darwin")
    native = image_identity.emulation({"os": "Linux", "arch": "x86_64"}, "x86_64")
    assert native["emulated"] is False and native["method"].startswith("image interpreter ELF")
    unknown_host = image_identity.emulation({"os": None, "arch": None}, "x86_64")
    assert unknown_host["emulated"] is None and unknown_host["host_arch"] is None
    assert unknown_host["method"].startswith("not compared")
    monkeypatch.setattr(image_identity, "image_architecture", lambda: None)
    with_host_only = image_identity.emulation({"os": "Linux", "arch": "x86_64"})
    assert with_host_only["emulated"] is None and with_host_only["method"].startswith("not compared")


def test_host_environment_is_taken_once_and_removed(baked, monkeypatch):
    monkeypatch.setenv("QROSETTA_HOST_OS", "Linux")
    monkeypatch.setenv("QROSETTA_HOST_ARCH", "x86_64")
    assert image_identity.take_host_environment() == {"os": "Linux", "arch": "x86_64"}
    assert "QROSETTA_HOST_OS" not in os.environ and "QROSETTA_HOST_ARCH" not in os.environ
    assert image_identity.take_host_environment() == {"os": "Linux", "arch": "x86_64"}
    image_identity.take_host_environment.cache_clear()
    monkeypatch.setenv("QROSETTA_HOST_OS", "")
    monkeypatch.setenv("QROSETTA_HOST_ARCH", "")
    assert image_identity.take_host_environment() == {"os": None, "arch": None}
    assert "QROSETTA_HOST_OS" not in os.environ and "QROSETTA_HOST_ARCH" not in os.environ


@pytest.mark.parametrize("measured", [True, False])
def test_host_environment_is_removed_before_the_child_is_spawned(baked, monkeypatch, measured):
    without = dict(os.environ)
    monkeypatch.setenv("QROSETTA_HOST_OS", "Darwin")
    monkeypatch.setenv("QROSETTA_HOST_ARCH", "arm64")
    image_identity.load()
    assert dict(os.environ) == without

    async def main():
        return await ExecutionSlots(1).run(fx.reports_environment, {"hard_timeout_seconds": 60},
                                           measured=measured)

    result = asyncio.run(main())
    assert result["environ"] == without
    emulation = result["image_identity"]["emulation"]
    image = image_identity.image_architecture()
    assert emulation["image_arch"] == image and emulation["host_arch"] == "aarch64"
    assert emulation["host_os"] == "Darwin" and emulation["emulated"] is (image != "aarch64")


def test_without_qrosetta_start_the_host_is_not_recorded(baked):
    image_identity.load()
    emulation = image_identity.image_identity()["emulation"]
    assert emulation["emulated"] is None and emulation["host_arch"] is None and emulation["host_os"] is None


@pytest.mark.parametrize("measured", [True, False])
def test_result_carries_identity_and_child_environment_is_unchanged(baked, measured):
    image_identity.load()
    parent_env = dict(os.environ)

    async def main():
        return await ExecutionSlots(1).run(fx.reports_environment, {"hard_timeout_seconds": 60},
                                           measured=measured)

    result = asyncio.run(main())
    child = result
    assert child["environ"] == parent_env
    assert child["identity_read"] == 0 and child["build_files_read"] == 0
    assert result["image_identity"]["source"] == "built_locally"
    assert result["image_identity"]["git_sha"] == "abc1234"
    assert result["build_files"] == {
        "Dockerfile": hashlib.sha256(b"FROM x\n").hexdigest(),
        "requirements.lock": hashlib.sha256(b"qiskit==1.0\n").hexdigest()}


def test_a_queue_timeout_carries_identity_too(baked):
    async def main():
        slots = ExecutionSlots(1)
        first = asyncio.create_task(slots.run(fx.slow, {"sleep": 2, "hard_timeout_seconds": 10}))
        await asyncio.sleep(0.2)
        second = await slots.run(fx.fast, {"x": 1, "max_queue_wait_seconds": 0.1})
        first.cancel()
        try:
            await first
        except asyncio.CancelledError:
            pass
        return second

    result = asyncio.run(main())
    assert result["never_started"] is True
    assert result["image_identity"]["source"] == "built_locally"


@pytest.mark.parametrize("image_dir", IMAGE_DIRS, ids=lambda p: p.name)
def test_every_image_writes_its_identity_file_without_new_environment(image_dir):
    text = (image_dir / "Dockerfile").read_text()
    assert "ARG QROSETTA_IMAGE_SOURCE=unknown" in text and "ARG QROSETTA_RELEASE=" in text
    assert "/usr/local/share/qrosetta-image/identity" in text
    assert not re.search(r"^ENV[^\n]*(QROSETTA_IMAGE_SOURCE|QROSETTA_RELEASE)", text, re.M)
    rel = image_dir.relative_to(REPO)
    assert re.search(rf"^COPY {rel}/Dockerfile {rel}/requirements.lock[^\n]* /usr/local/share/qrosetta-build/",
                     text, re.M)
    identity_at = text.index("/usr/local/share/qrosetta-image/identity")
    assert identity_at < text.rindex("USER appuser")


def test_compose_bakes_the_image_source_for_every_runner_and_compiler():
    compose = (REPO / "docker-compose.yml").read_text()
    blocks = re.split(r"\n  (?=[a-z_]+:\n)", compose)
    images = [b for b in blocks if re.search(r"dockerfile: \./(runners|compilers)/", b)]
    assert len(images) == len(IMAGE_DIRS)
    for block in images:
        assert "QROSETTA_IMAGE_SOURCE=${QROSETTA_IMAGE_SOURCE:-built_locally}" in block
        assert "QROSETTA_RELEASE=${QROSETTA_RELEASE:-}" in block


def test_compose_passes_the_host_os_and_machine_to_every_runner_and_compiler():
    compose = (REPO / "docker-compose.yml").read_text()
    blocks = re.split(r"\n  (?=[a-z_]+:\n)", compose)
    images = [b for b in blocks if re.search(r"dockerfile: \./(runners|compilers)/", b)]
    assert len(images) == len(IMAGE_DIRS)
    for block in images:
        assert "- QROSETTA_HOST_OS=${QROSETTA_HOST_OS:-}" in block
        assert "- QROSETTA_HOST_ARCH=${QROSETTA_HOST_ARCH:-}" in block


def test_one_job_entrypoints_take_the_host_environment_before_running():
    for rel in ("shared/qrosetta_commons/helpers.py", "shared/qrosetta_commons/compile_service.py"):
        text = (REPO / rel).read_text()
        parsed = text.index("args = parser.parse_args()")
        taken = text.index("_image_identity.take_host_environment()", parsed)
        assert taken < text.index("if args.self_test", parsed), rel
