# Releasing Quantum Rosetta

The release workflow (`.github/workflows/release-images.yml`, described step by step in
`CONTRIBUTING.md`, "A release") builds, tests, publishes and attaches everything once a tag is
pushed. This file gives the order a maintainer follows around it, the files a version bump
touches, and the checks on a clean machine afterwards. Commands assume the public repository is
the git remote `public` (`SeQuSoS-Project/QRosetta`) and the version is `X.Y.Z`.

## Facts that fix the order

- PyPI never accepts a file name twice, even after the file or the whole release is deleted
  (https://pypi.org/help/#file-name-reuse). A wheel with a mistake costs a version number: fix
  forward with `X.Y.Z.post1` for a packaging-only fix, else `X.Y.(Z+1)`. The same holds on
  TestPyPI, so a failed release candidate is followed by `rc2`.
- A package that `publish-images` creates is linked to this public repository and takes its
  visibility: the rc2 images (2026-11-03) were public at once, pullable without a login, and
  nothing had to be switched per package. A public package cannot be made private again
  (https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility),
  so whatever a release-candidate tag pushes is published.
- With immutable releases on, a published release accepts no new asset
  (https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/immutable-releases).
  The workflow therefore drafts the release, attaches every file, checks the attached copies and
  only then publishes.
- Zenodo archives a GitHub release when it is published, and only if the repository was enabled
  in Zenodo before. When both `.zenodo.json` and `CITATION.cff` exist, Zenodo reads only
  `.zenodo.json` (https://help.zenodo.org/docs/github/describe-software/). The GitHub
  integration cannot reserve a DOI in advance
  (https://support.zenodo.org/help/en-gb/24-github-integration/73-can-i-pre-reserved-a-doi-before-a-github-release),
  so the DOI exists only after publication. A failed archive shows its error on Zenodo and is
  fixed only by a new release. How Zenodo treats GitHub pre-releases was not verified, so the
  workflow makes no GitHub release for a pre-release tag.
- The workflow refuses a tag that is not `v` followed by `qrosetta_cli.__version__` spelled as
  canonical PEP 440 (`v2.0.0rc1`, never `v2.0.0-rc1`).

## Release-blocking items known on 2026-11-02

The Trivy gate passes on every release image, and every fixable HIGH finding outside an SDK pin is
gone (DESIGN_DECISIONS.md, "Dependency bumps in the published runner and compiler images", both
rounds). What a scan without `.trivyignore` still reports, all fixed only by another measured SDK
version:

| Finding | Images | In `.trivyignore` |
|---|---|---|
| qiskit CVE-2025-2000 (CRITICAL, QPY) | qiskit, PennyLane ×2, Qrisp, TorchQuantum | accepted by the owner until 2027-05-01 |
| torch CVE-2025-32434 (CRITICAL, `torch.load`) | TorchQuantum | accepted by the owner until 2027-05-01 |
| qiskit CVE-2025-1403 (HIGH, QPY) | the same five | accepted by the owner until 2027-05-01 |
| protobuf CVE-2026-0994 (HIGH; cirq-google 1.4.1 requires < 5) | Cirq, qsim | accepted by the owner until 2027-05-01 |
| thrift CVE-2026-41608, CVE-2026-43871 (HIGH; myQLM's `qat-comm` pins 0.21.0) | myQLM (never published) | no |

1. If the published nginx base changes, rescan: the 2026-10-19 build of
   `nginx-unprivileged:1.31.7-alpine3.24` carries brotli-libs 1.2.0-r1 (CRITICAL), which the image
   removes with the modules that need it.
2. `CHANGELOG.md` has no `[2.0.0]` section yet. The `plan` job stops a final tag until it has a
   dated one.

## One-time setup (owner)

- PyPI and TestPyPI trusted publishers for `qrosetta`: repository `SeQuSoS-Project/QRosetta`,
  workflow `release-images.yml`, environments `pypi` and `testpypi`; both GitHub environments
  with the owner as required reviewer and tag rule `v*` (done 2026-10-27). Until the first upload
  the PyPI project does not exist and the publisher is a pending one, which reserves no name
  (https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/): before the first
  final tag, check that https://pypi.org/manage/account/publishing/ still lists it.
- Zenodo: log in with GitHub and switch on `SeQuSoS-Project/QRosetta` before the first final
  tag.
- GHCR: allow public packages for the organisation (an organisation owner; done); set the
  repository variable `QROSETTA_PUBLISH_IMAGES` to `true` (done).
- Both GitHub environments need a deployment rule of type **tag** `v*`; a **branch** rule `v*`
  refuses every tag (`testpypi` had one until 2026-11-03).
- Repository settings: immutable releases on (Settings, General, Releases); a ruleset on
  `refs/tags/v*` that forbids update and deletion; private vulnerability reporting on.
- A GPG or SSH signing key registered on the GitHub account, and git set to use it
  (`git config user.signingkey ...`; for SSH also `git config gpg.format ssh`).
- Labels the generated notes sort by (`.github/release.yml`): `measurement`, `analysis`,
  `sealed-image`, `enhancement`, `bug`, `security`, `documentation`, `dependencies`,
  `skip-changelog`. GitHub creates `bug`, `enhancement` and `documentation` in a new repository;
  create the rest.

## Files a version bump touches

| File | Field | Checked by |
|---|---|---|
| `qrosetta_cli/__init__.py` | `__version__` (the package version; `pyproject.toml` reads it) | `test_release_version.py` |
| `rosetta-api/config.py` | `PLATFORM_VERSION` default | `test_release_version.py` |
| `rosetta-api/Dockerfile` | `ARG QROSETTA_VERSION` | `test_release_version.py` |
| `CITATION.cff` | `version`; `date-released: YYYY-MM-DD` for a final version | `test_citation_metadata.py` (version) |
| `.zenodo.json` | `version` | `test_citation_metadata.py` |
| `codemeta.json` | `version`; `datePublished` for a final version | `test_citation_metadata.py` |
| `CHANGELOG.md` | `## [Unreleased]` becomes `## [X.Y.Z] - YYYY-MM-DD` above a new empty `## [Unreleased]`; the compare links at the bottom | `release_assets.py notes --check` in the `plan` job (final tags) |

`git grep -n "<old version>"` afterwards should list only text that records history: the
migration baseline's docstring (`rosetta-api/migrations/versions/0001_baseline.py`), the
verification documents in `docs/verification/`, and the v1.0.0 example crate in `examples/`.

## A release candidate (rehearsal, no GitHub release)

1. On `main`, bump to `X.Y.Zrc1` in the first six files above (`CHANGELOG.md` keeps
   `[Unreleased]`; leave the two date fields out). Run the unit suite and
   `./scripts/check_frontend_types.sh`. On a local stack built from the commit, export a
   statevector job, a measured job with a compile-only service, a playlist and a supplied report,
   and check them with `scripts/verify/validate_crates.sh <zip> ...` (Process Run Crate 0.5,
   REQUIRED level). Commit, and `git push public main`.
2. Tag the commit and push the tag:

   ```bash
   git tag -s vX.Y.Zrc1 -m "Quantum Rosetta X.Y.Zrc1"
   git tag -v vX.Y.Zrc1          # expect: Good signature from ...
   git push public vX.Y.Zrc1
   ```

3. The run builds, self-tests and scans every image, pushes them to GHCR as `:X.Y.Zrc1`, signs and
   attests them, and puts the wheel on TestPyPI once the `testpypi` environment is approved.
   `release-assets` runs too: the run page then holds the artifact `release-assets` with exactly
   the files the release page would carry. No GitHub release is made, so Zenodo sees nothing.
4. Check the image list, notices and SBOMs in the artifact, and run the clean-machine checks below with `pipx install --index-url https://test.pypi.org/simple/
   qrosetta==X.Y.Zrc1` in place of the PyPI install, the files of the `release-assets` artifact
   in place of the release page, and steps 11 and 12 left out.

## The release

1. Release pull request on `main`: bump every file in the table to `X.Y.Z` (dates included),
   rename the CHANGELOG section, run the unit suite, merge, then `git push public main`.
2. Signed annotated tag on the merged commit:

   ```bash
   git tag -s vX.Y.Z -m "Quantum Rosetta X.Y.Z"
   git tag -v vX.Y.Z             # expect: Good signature from ...
   git push public vX.Y.Z
   ```

3. Follow the run: `plan` (tag equals `__version__`, CHANGELOG section present and dated),
   `openapi`, `images` (build, self-test, scan), `publish-images`, `wheel`, `publish-pypi` (approve
   the `pypi` environment), `release-assets`, `publish-release`.
4. `publish-release` drafts the release with the files, the CHANGELOG section and GitHub's
   generated notes, downloads the attached files and checks them against `SHA256SUMS`, then
   publishes. If it fails before publishing, the draft stays: re-run the job, which deletes a
   draft of the same tag and starts again. It stops if the release is already published.
5. Zenodo creates the record a few minutes after publication. Check that the record shows version
   `X.Y.Z`, the three authors and Apache-2.0, taken from `.zenodo.json`. Note the version DOI and
   the concept DOI (the concept DOI always resolves to the newest version). Add them to
   `README.md` ("Citing") and as `doi` / `identifiers` in `CITATION.cff` in a follow-up commit;
   they reach the archive with the next release.
6. Software Heritage: submit the repository at https://archive.softwareheritage.org/save/
   (origin type git, URL `https://github.com/SeQuSoS-Project/QRosetta`), or

   ```bash
   curl -X POST "https://archive.softwareheritage.org/api/1/origin/save/git/url/https://github.com/SeQuSoS-Project/QRosetta/"
   ```

   When the visit has finished, open the release `vX.Y.Z` in the archive and copy its SWHID with
   the origin and visit qualifiers from the Permalinks tab. The revision SWHID is
   `swh:1:rev:` followed by the tagged commit's hash (`git rev-parse vX.Y.Z^{commit}`); cite the
   release SWHID (`swh:1:rel:...`) as the archive shows it.
7. After the release: bump to `X.Y.(Z+1).dev0` in the first six files of the table and add an
   empty `## [Unreleased]` with its compare link.

The workflow is the normal path. If it cannot publish the release, the same sequence by hand
uses the `release-assets` artifact of the run:

```bash
gh run download <run id> -R SeQuSoS-Project/QRosetta -n release-assets -D assets
(cd assets && sha256sum -c SHA256SUMS)
python3 scripts/release/release_assets.py notes --version X.Y.Z --out notes.md
gh release create vX.Y.Z -R SeQuSoS-Project/QRosetta --draft --verify-tag \
  --title "Quantum Rosetta X.Y.Z" --notes-file notes.md --generate-notes assets/*
gh release download vX.Y.Z -R SeQuSoS-Project/QRosetta -D attached
(cd attached && sha256sum -c ../assets/SHA256SUMS)
gh release edit vX.Y.Z -R SeQuSoS-Project/QRosetta --draft=false --latest
```

## What the release page carries

| File | What it is | How to check it |
|---|---|---|
| `qrosetta-X.Y.Z-py3-none-any.whl`, `qrosetta-X.Y.Z.tar.gz` | the files PyPI received | `cmp` with the PyPI download; `gh attestation verify` |
| `qrosetta-X.Y.Z-images.txt` | every published image by digest and image id, the never-published images with the reason, and per image the three verify commands | its own commands |
| `sbom-<id>.spdx.json` | SPDX SBOM of each published image (syft), the same document as its SBOM attestation | `gh attestation verify oci://... --predicate-type https://spdx.dev/Document/v2.3` |
| `NOTICE-<id>.txt` | each image's operating-system source packages at their installed versions, with source addresses | |
| `openapi-X.Y.Z.json` | the API description, written from the tagged code | |
| `SHA256SUMS` | sha256 of every file above | `sha256sum -c SHA256SUMS` |
| `qrosetta-X.Y.Z.intoto.jsonl` | Sigstore bundle of one build-provenance attestation whose subjects are the files in `SHA256SUMS` | `gh attestation verify FILE --bundle qrosetta-X.Y.Z.intoto.jsonl -R SeQuSoS-Project/QRosetta` |

OpenSSF Scorecard's Signed-Releases check reads only release assets; the `.intoto.jsonl` file is
what it counts as provenance.

## Clean-machine checks

On a fresh virtual machine (Fedora or RHEL with rootless podman 4.7 or later, or Ubuntu LTS with
Docker Engine), not logged in to `ghcr.io`, with Docker Compose v2 as the compose provider and the
host set up as README.md "Setting up the host" says (on RHEL, `qrosetta doctor` names the Compose
step), Python 3.11 or later, pipx, cosign 3 and the GitHub CLI (`gh auth login` done). `docker` below may be `podman` throughout. Each command is
followed by what it should print.

1. Install from PyPI.

   ```bash
   pipx install qrosetta==X.Y.Z
   ```

   `installed package qrosetta X.Y.Z, installed using Python 3.N.N`, then `These apps are now
   globally available` and `- qrosetta`.

2. `qrosetta version` prints `qrosetta X.Y.Z (Python 3.N.N, installed mode)` and
   `Release manifest: release X.Y.Z (images published)`.

3. The release files are the attested ones, and PyPI has the same wheel.

   ```bash
   gh release download vX.Y.Z -R SeQuSoS-Project/QRosetta -D release
   (cd release && sha256sum -c SHA256SUMS)
   gh attestation verify release/qrosetta-X.Y.Z-py3-none-any.whl -R SeQuSoS-Project/QRosetta
   pip download --no-deps qrosetta==X.Y.Z -d pypi
   cmp pypi/qrosetta-X.Y.Z-py3-none-any.whl release/qrosetta-X.Y.Z-py3-none-any.whl
   ```

   One `OK` line per file; `✓ Verification succeeded!`; `cmp` prints nothing and exits 0.

4. Every published image can be pulled anonymously, which shows its GHCR package is public.

   ```bash
   docker logout ghcr.io
   grep -oE 'ghcr\.io/[^ ]+@sha256:[0-9a-f]{64}' release/qrosetta-X.Y.Z-images.txt | sort -u | xargs -n1 docker pull
   ```

   Every pull completes. `unauthorized` or `denied` means that package is still private.

5. Signature, for each image (the commands are in `qrosetta-X.Y.Z-images.txt`):

   ```bash
   cosign verify --certificate-identity 'https://github.com/SeQuSoS-Project/QRosetta/.github/workflows/release-images.yml@refs/tags/vX.Y.Z' \
     --certificate-oidc-issuer 'https://token.actions.githubusercontent.com' REF
   ```

   `Verification for REF --` followed by the checks performed (cosign claims validated,
   transparency-log entry verified, certificate verified against the trusted authority), then the
   signature JSON; exit 0.

6. Provenance and SBOM attestations, for each image:

   ```bash
   gh attestation verify oci://REF -R SeQuSoS-Project/QRosetta
   gh attestation verify oci://REF -R SeQuSoS-Project/QRosetta --predicate-type https://spdx.dev/Document/v2.3
   ```

   `✓ Verification succeeded!` for both. gh reads the image from the registry with the local
   docker or podman login, and the GitHub CLI documentation says a login is required for `oci://`.

7. `qrosetta pull --profile minimal --require-signature` prints, per image, `<id> (n/5): REF` and
   `pulled, <size>, <seconds> s; <signature detail>` (or `already present` after step 4), and ends
   with `5 images of Quantum Rosetta X.Y.Z present (...); `qrosetta start -d` starts them.`;
   exit 0.

8. `qrosetta images verify --require-signature` exits 0.

9. `qrosetta start -d --profile minimal` returns once the API is ready and the runners answer;
   `qrosetta status` lists the five services as running.

10. `qrosetta selftest` prints no `FAIL` line and ends with `PASS. Results: ...` (a virtual
    machine adds one hypervisor warning per probed runner and one for the job, e.g.
    `PASS (4 warnings). Results: ...` for the minimal profile); exit 0.

11. The DOI resolves:

    ```bash
    curl -sI https://doi.org/<version DOI> | grep -i '^location'
    ```

    A `location:` header pointing at the Zenodo record, whose page names version `X.Y.Z`.

12. The SWHID resolves: `https://archive.softwareheritage.org/<release SWHID>` shows the
    archived tag `vX.Y.Z`, and `https://archive.softwareheritage.org/swh:1:rev:<commit>` the
    commit it points to.

13. Clean up: `qrosetta remove --all --confirm qsimulators` and `pipx uninstall qrosetta`.

Image archives for a Zenodo upload (`qrosetta images save`) are written with an installed
`qrosetta` after `qrosetta pull`: in installed mode `images load` accepts only published images,
while a checkout that built myQLM, cuQuantum or BQSKit would also save those, and their licences
forbid distributing them.
