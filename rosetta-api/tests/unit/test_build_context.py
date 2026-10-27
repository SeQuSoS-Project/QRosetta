"""The image build context leaves out npm's node_modules: the nginx and API images copy
rosetta-api/static, and whatever it holds is served as files."""
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]


def test_node_modules_are_outside_the_build_context():
    patterns = [line.strip() for line in (_ROOT / ".dockerignore").read_text().splitlines()]
    assert "**/node_modules" in patterns
