"""CITATION.cff, .zenodo.json and codemeta.json describe the same software: one title, version,
licence, author list (names, affiliations, ORCIDs where given), repository, description and
keywords; the version is qrosetta_cli.__version__, and pyproject.toml names the same authors,
licence and repository."""

import json
import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
REPOSITORY = "https://github.com/SeQuSoS-Project/QRosetta"


def cli_version():
    found = re.findall(r'^__version__ = "([^"]+)"$', (REPO / "qrosetta_cli/__init__.py").read_text(), re.M)
    assert len(found) == 1
    return found[0]


def _orcid(value):
    return value.rstrip("/").rsplit("/", 1)[-1] if value else None


def citation():
    cff = yaml.safe_load((REPO / "CITATION.cff").read_text())
    return {
        "title": cff["title"],
        "version": str(cff.get("version")),
        "licence": cff["license"],
        "authors": [(a["family-names"], a["given-names"], a.get("affiliation"), _orcid(a.get("orcid")))
                    for a in cff["authors"]],
        "repository": cff["repository-code"],
        "description": cff["abstract"].strip(),
        "keywords": cff["keywords"],
    }


def zenodo():
    zen = json.loads((REPO / ".zenodo.json").read_text())
    authors = []
    for creator in zen["creators"]:
        family, given = (part.strip() for part in creator["name"].split(",", 1))
        authors.append((family, given, creator.get("affiliation"), _orcid(creator.get("orcid"))))
    repositories = [r["identifier"] for r in zen.get("related_identifiers", []) if r.get("scheme") == "url"]
    assert len(repositories) == 1, repositories
    return {
        "title": zen["title"],
        "version": zen.get("version"),
        "licence": zen["license"],
        "authors": authors,
        "repository": repositories[0],
        "description": zen["description"],
        "keywords": zen["keywords"],
    }


def codemeta():
    meta = json.loads((REPO / "codemeta.json").read_text())
    assert meta["@context"] == "https://w3id.org/codemeta/3.0"
    licence = meta["license"]
    assert licence.startswith("https://spdx.org/licenses/"), licence
    authors = [(a["familyName"], a["givenName"], (a.get("affiliation") or {}).get("name"), _orcid(a.get("id")))
               for a in meta["author"]]
    return {
        "title": meta["name"],
        "version": meta.get("version"),
        "licence": licence.rsplit("/", 1)[-1],
        "authors": authors,
        "repository": meta["codeRepository"],
        "description": meta["description"],
        "keywords": meta["keywords"],
    }


@pytest.mark.parametrize("field", ["title", "version", "licence", "authors", "repository", "description",
                                   "keywords"])
def test_citation_zenodo_and_codemeta_agree(field):
    values = {"CITATION.cff": citation()[field], ".zenodo.json": zenodo()[field], "codemeta.json": codemeta()[field]}
    if field == "licence":
        values = {name: value.lower() for name, value in values.items()}
    assert len({json.dumps(v) for v in values.values()}) == 1, f"{field} differs: {values}"


def test_metadata_version_is_the_package_version():
    assert codemeta()["version"] == cli_version()


def test_repository_is_the_public_one():
    assert citation()["repository"] == REPOSITORY


def test_pyproject_names_the_same_authors_licence_and_repository():
    tomllib = pytest.importorskip("tomllib")
    project = tomllib.loads((REPO / "pyproject.toml").read_text())["project"]
    assert [a["name"] for a in project["authors"]] == [f"{given} {family}" for family, given, _, _ in
                                                      citation()["authors"]]
    assert project["license"] == citation()["licence"]
    urls = project["urls"]
    assert urls["Source"] == REPOSITORY and urls["Homepage"] == REPOSITORY
    assert urls["Issues"] == f"{REPOSITORY}/issues"
    assert urls["Changelog"] == f"{REPOSITORY}/blob/main/CHANGELOG.md"
