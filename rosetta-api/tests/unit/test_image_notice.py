"""scripts/release/image_notice.py: the source notice of a release image lists every Debian source
package at its installed version with its snapshot.debian.org address (Alpine: aports commit), tells
the base image's archive date from the one the Dockerfile installed from, names the final stage's
base image, reads an image only through a created container that it removes and never starts, and
the release workflow writes one notice per published image."""

import importlib.util
import json
import stat
import sys

import pytest
import yaml

from tests.unit._qrosetta_fake import REPO

_spec = importlib.util.spec_from_file_location("image_notice", REPO / "scripts" / "release" / "image_notice.py")
notice_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(notice_mod)

_mm_spec = importlib.util.spec_from_file_location("make_manifest_n", REPO / "scripts" / "release" / "make_manifest.py")
make_manifest = importlib.util.module_from_spec(_mm_spec)
_mm_spec.loader.exec_module(make_manifest)

DPKG_STATUS = """Package: libc6
Status: install ok installed
Architecture: amd64
Source: glibc
Version: 2.41-12+deb13u4
Description: GNU C Library
 continuation line with Source: not-a-field

Package: login.defs
Status: install ok installed
Source: shadow (1:4.17.4-2)
Version: 1:4.17.4-2+b1

Package: bash
Status: install ok installed
Version: 5.2.37-2+b5

Package: removed-thing
Status: deinstall ok config-files
Version: 1.0

Package: libc-bin
Status: install ok installed
Source: glibc
Version: 2.41-12+deb13u4
"""

DEBIAN_SOURCES_BASE = """Types: deb
# http://snapshot.debian.org/archive/debian/20260316T000000Z
URIs: http://deb.debian.org/debian
Suites: trixie trixie-updates
Components: main
"""

APK_DB = """C:Q1abc=
P:busybox
V:1.37.0-r30
o:busybox
c:1e823a60eb85606954b3a5af5f8e5bbd1ea680cf
L:GPL-2.0-only

P:busybox-binsh
V:1.37.0-r30
o:busybox
c:1e823a60eb85606954b3a5af5f8e5bbd1ea680cf
L:GPL-2.0-only

P:nginx
V:1.31.1-r1
o:nginx
L:2-clause BSD-like license
U:https://nginx.org/
m:NGINX Packaging <nginx-packaging@f5.com>
"""

DOCKERFILE = "FROM python:3.11-slim@sha256:" + "a" * 64 + "\nRUN true\n"


def _debian_root(tmp_path, sources=DEBIAN_SOURCES_BASE):
    root = tmp_path / "root"
    (root / "var/lib/dpkg").mkdir(parents=True)
    (root / "var/lib/dpkg/status").write_text(DPKG_STATUS)
    (root / "usr/lib").mkdir(parents=True)
    (root / "usr/lib/os-release").write_text('PRETTY_NAME="Debian GNU/Linux 13 (trixie)"\nID=debian\n')
    (root / "etc/apt/sources.list.d").mkdir(parents=True)
    (root / "etc/apt/sources.list.d/debian.sources").write_text(sources)
    return root


def _notice(root, **kw):
    args = dict(image="ghcr.io/o/qrosetta-x:2.0.0", image_id="sha256:" + "b" * 64, dockerfile="runners/x/Dockerfile",
                dockerfile_text=DOCKERFILE, notices_url="https://example.org/THIRD_PARTY_NOTICES.md")
    args.update(kw)
    return notice_mod.notice(root, **args)


def test_dpkg_status_gives_installed_packages_with_their_source_and_source_version():
    pkgs = {p["package"]: p for p in notice_mod.parse_dpkg_status(DPKG_STATUS)}
    assert set(pkgs) == {"libc6", "login.defs", "bash", "libc-bin"}
    assert (pkgs["libc6"]["source"], pkgs["libc6"]["source_version"]) == ("glibc", "2.41-12+deb13u4")
    assert (pkgs["login.defs"]["source"], pkgs["login.defs"]["source_version"]) == ("shadow", "1:4.17.4-2")
    assert pkgs["login.defs"]["version"] == "1:4.17.4-2+b1"
    assert (pkgs["bash"]["source"], pkgs["bash"]["source_version"]) == ("bash", "5.2.37-2+b5")


def test_debian_notice_lists_each_source_package_once_with_its_snapshot_address(tmp_path):
    text = _notice(_debian_root(tmp_path))
    assert "4 Debian binary packages built from 3 source packages" in text
    assert "glibc 2.41-12+deb13u4\n    https://snapshot.debian.org/package/glibc/2.41-12%2Bdeb13u4/\n" in text
    assert "    binary packages: libc-bin, libc6\n" in text
    assert "https://snapshot.debian.org/package/shadow/1%3A4.17.4-2/" in text
    assert "removed-thing" not in text
    assert "Operating system: Debian GNU/Linux 13 (trixie)." in text
    assert "Base image of its final stage: python:3.11-slim@sha256:" + "a" * 64 + "." in text
    assert "/usr/share/doc/<package>/copyright" in text
    assert text.rstrip().endswith("https://example.org/THIRD_PARTY_NOTICES.md")
    assert "(sha256:" + "b" * 64 + ")" in text.splitlines()[0]


def test_the_base_image_date_comes_from_the_comment_and_no_install_date_is_claimed(tmp_path):
    text = _notice(_debian_root(tmp_path))
    assert "The base image's Debian packages are those of the Debian archive as of 20260316T000000Z" in text
    assert "installed from deb.debian.org when the image was built; the image records no archive date" in text


def test_an_active_snapshot_source_is_the_install_date(tmp_path):
    sources = DEBIAN_SOURCES_BASE.replace(
        "URIs: http://deb.debian.org/debian", "URIs: https://snapshot.debian.org/archive/debian/20261020T000000Z")
    text = _notice(_debian_root(tmp_path, sources))
    assert "as of 20260316T000000Z" in text
    assert "Packages the Dockerfile adds were installed from the Debian archive as of 20261020T000000Z" in text
    one_line = "deb [check-valid-until=no] https://snapshot.debian.org/archive/debian/20261021T000000Z trixie main\n"
    root = _debian_root(tmp_path / "b", "")
    (root / "etc/apt/sources.list").write_text(one_line)
    assert "as of 20261021T000000Z" in _notice(root)


def test_snapshot_option_names_the_install_date(tmp_path):
    text = _notice(_debian_root(tmp_path), snapshot="20261101T000000Z")
    assert "installed from the Debian archive as of 20261101T000000Z" in text
    with pytest.raises(SystemExit):
        notice_mod.main(["--root", str(tmp_path), "--dockerfile", str(REPO / "nginx" / "Dockerfile"),
                         "--snapshot", "2026-11-01"])


def test_alpine_notice_groups_by_origin_and_names_the_aports_commit(tmp_path):
    root = tmp_path / "root"
    (root / "lib/apk/db").mkdir(parents=True)
    (root / "lib/apk/db/installed").write_text(APK_DB)
    text = _notice(root, dockerfile_text="FROM nginx:alpine@sha256:" + "c" * 64 + "\n")
    assert "3 Alpine packages built from 2 source packages" in text
    assert "busybox 1.37.0-r30 (GPL-2.0-only)\n    https://gitlab.alpinelinux.org/alpine/aports/-/tree/1e823a60" in text
    assert "binary packages: busybox, busybox-binsh" in text
    assert "not built from aports; packaged by NGINX Packaging <nginx-packaging@f5.com>, project https://nginx.org/" in text


def test_an_image_without_a_package_database_is_refused(tmp_path):
    (tmp_path / "root").mkdir()
    with pytest.raises(SystemExit, match="neither a dpkg status file nor an apk database"):
        _notice(tmp_path / "root")


@pytest.mark.parametrize("dockerfile,expected", [
    ("FROM a:1 AS build\nRUN make\nFROM b:2@sha256:x\nCOPY --from=build /x /x\n", "b:2@sha256:x"),
    ("FROM --platform=linux/amd64 a:1 AS base\nFROM base AS final\n", "a:1"),
    ("from a:1\n", "a:1"),
])
def test_final_base_is_the_last_stage_followed_through_stage_names(dockerfile, expected):
    assert notice_mod.final_base(dockerfile) == expected


def test_every_release_image_has_a_final_stage_pinned_by_digest():
    for record in make_manifest.release_images(make_manifest.services()):
        base = notice_mod.final_base((REPO / record["dockerfile"]).read_text())
        assert base and "@sha256:" in base, record["id"]


def test_an_image_is_read_through_a_created_container_that_is_removed_and_never_started(tmp_path):
    root = _debian_root(tmp_path)
    log = tmp_path / "calls.jsonl"
    engine = tmp_path / "engine"
    engine.write_text(
        f"#!{sys.executable}\n"
        "import json, shutil, sys, pathlib\n"
        f"log = pathlib.Path({str(log)!r}); root = pathlib.Path({str(root)!r})\n"
        "args = sys.argv[1:]\n"
        "with log.open('a') as fh: fh.write(json.dumps(args) + '\\n')\n"
        "if args[0] == 'create': print('cid123')\n"
        "elif args[0] == 'cp':\n"
        "    src = root / args[1].split(':/', 1)[1]; dst = pathlib.Path(args[2])\n"
        "    if src.is_dir(): shutil.copytree(src, dst)\n"
        "    elif src.is_file(): shutil.copy(src, dst)\n"
        "    else: sys.exit(1)\n"
    )
    engine.chmod(engine.stat().st_mode | stat.S_IXUSR)
    out = tmp_path / "notice.txt"
    with out.open("w") as fh:
        saved, sys.stdout = sys.stdout, fh
        try:
            notice_mod.main(["--image", "img:1", "--engine", str(engine), "--dockerfile",
                             str(REPO / "runners" / "qrisp-runner" / "Dockerfile")])
        finally:
            sys.stdout = saved
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert calls[0] == ["create", "img:1", "true"]
    assert calls[-1] == ["rm", "cid123"]
    assert {c[0] for c in calls} == {"create", "cp", "rm"}
    assert "glibc 2.41-12+deb13u4" in out.read_text()


def test_the_release_workflow_writes_a_notice_per_published_image():
    wf = yaml.safe_load((REPO / ".github" / "workflows" / "release-images.yml").read_text())
    steps = wf["jobs"]["publish-images"]["steps"]
    names = [s.get("name") for s in steps]
    step = steps[names.index("Source notice")]
    assert names.index("Self-test by digest") < names.index("Source notice")
    assert 'image_notice.py --image "$REPOSITORY@$DIGEST"' in step["run"]
    assert '> "notices/NOTICE-$ID.txt"' in step["run"]
    assert "THIRD_PARTY_NOTICES.md" in step["run"]
    upload = steps[names.index("Source notice") + 1]
    assert upload["uses"].startswith("actions/upload-artifact@")
    assert upload["with"]["name"] == "notice-${{ matrix.id }}"
    assert upload["with"]["if-no-files-found"] == "error"
    dry_run = "\n".join(s.get("run", "") for s in wf["jobs"]["images"]["steps"])
    assert 'image_notice.py --image "$IMAGE"' in dry_run
