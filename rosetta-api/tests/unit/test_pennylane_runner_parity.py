"""The two PennyLane runners must differ only in which device they instantiate.

They are deliberately separate files: main.tex presents them as separate backends and
promises each backend's accommodation stays visible in its own module, so they are not
merged behind a shared factory. But nothing otherwise stops their transform pipelines or
preprocessing notes from drifting apart, which would make the pair incomparable while
still looking like a controlled comparison. This test is that guard.
"""
import re
from pathlib import Path

import pytest

_RUNNERS = Path(__file__).resolve().parents[3] / "runners"
_DEFAULT = _RUNNERS / "pennylane-default-runner" / "main.py"
_LIGHTNING = _RUNNERS / "pennylane-lightning-runner" / "main.py"

# The declarations that are allowed to differ, and what each file must declare.
_EXPECTED = {
    "_DEVICE": ('"default.qubit"', '"lightning.qubit"'),
    "_SIMULATOR": ('"pennylane-default"', '"pennylane-lightning"'),
}

pytestmark = pytest.mark.skipif(
    not (_DEFAULT.exists() and _LIGHTNING.exists()),
    reason="runner sources not present in this checkout",
)


def _normalize(text: str) -> str:
    """Blank out the identity strings so only behavioural differences remain."""
    for token in ("default.qubit", "lightning.qubit", "pennylane-default",
                  "pennylane-lightning", "Pennylane Default", "Pennylane Lightning",
                  "Pennylane-Default", "Pennylane-Lightning"):
        text = text.replace(token, "<ID>")
    return text


def test_declared_devices_are_the_expected_pair():
    for name, (expected_default, expected_lightning) in _EXPECTED.items():
        for path, expected in ((_DEFAULT, expected_default), (_LIGHTNING, expected_lightning)):
            match = re.search(rf"^{name} = (.+)$", path.read_text(), re.MULTILINE)
            assert match, f"{path.name} does not declare {name}"
            assert match.group(1).strip() == expected


def test_the_two_runners_are_otherwise_identical():
    default = _normalize(_DEFAULT.read_text())
    lightning = _normalize(_LIGHTNING.read_text())
    assert default == lightning, (
        "The PennyLane runners have diverged beyond their device declaration. If the change "
        "is intentional for one backend only, say so here; otherwise mirror it into both, or "
        "the pair stops being a controlled comparison."
    )
