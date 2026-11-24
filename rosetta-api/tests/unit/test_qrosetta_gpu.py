"""GPU passthrough (qrosetta_cli/stack/gpu.py): CDI specification detection, the generated compose
override, the readiness wait without a GPU, and the compose label against config.py."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from qrosetta_cli.stack import gpu  # noqa: E402
from qrosetta_cli.stack.project import Service, Stack  # noqa: E402

NVIDIA_YAML = "---\ncdiVersion: 0.5.0\nkind: nvidia.com/gpu\ndevices:\n- name: all\n"


def _stack(gpu_label=True):
    labels = {"org.qrosetta.id": "cuquantum", "org.qrosetta.kind": "runner"}
    if gpu_label:
        labels[gpu.GPU_LABEL] = "nvidia"
    services = {
        "cuquantum_runner": Service("cuquantum_runner", "cuquantum-runner", "img", labels=labels),
        "pytket_qiskit_runner": Service(
            "pytket_qiskit_runner", "pytket-qiskit-runner", "img", labels={"org.qrosetta.id": "qiskit"}
        ),
    }
    return Stack(name="qsimulators", project_dir="/p", services=services, volume_names={})


def _env(tmp_path):
    return {"XDG_STATE_HOME": str(tmp_path / "state"), "HOME": str(tmp_path)}


def test_a_yaml_specification_of_kind_nvidia_gpu_is_found(tmp_path):
    (tmp_path / "other.yaml").write_text("kind: example.com/fpga\n")
    (tmp_path / "nvidia.yaml").write_text(NVIDIA_YAML)
    assert gpu.nvidia_spec([str(tmp_path / "missing"), str(tmp_path)]) == str(tmp_path / "nvidia.yaml")


def test_a_json_specification_is_read_as_json(tmp_path):
    (tmp_path / "nvidia.json").write_text(json.dumps({"cdiVersion": "0.5.0", "kind": "nvidia.com/gpu"}))
    assert gpu.nvidia_spec([str(tmp_path)]) == str(tmp_path / "nvidia.json")


def test_no_specification_of_that_kind_is_none(tmp_path):
    (tmp_path / "a.yaml").write_text("kind: example.com/fpga\n# kind: nvidia.com/gpu\n")
    (tmp_path / "b.json").write_text("not json")
    (tmp_path / "c.txt").write_text(NVIDIA_YAML)
    assert gpu.nvidia_spec([str(tmp_path)]) is None


def test_podman_reads_the_fixed_directories_and_docker_those_its_info_lists():
    assert gpu.spec_dirs(SimpleNamespace(name="podman", info={})) == gpu.PODMAN_SPEC_DIRS
    assert gpu.spec_dirs(SimpleNamespace(name="docker", info={"CDISpecDirs": ["/etc/cdi"]})) == ("/etc/cdi",)
    assert gpu.spec_dirs(SimpleNamespace(name="docker", info={})) == ()


def test_with_a_specification_the_override_gives_the_gpu_service_the_device(tmp_path):
    engine = SimpleNamespace(name="podman", info={}, files=["/p/docker-compose.yml"])
    stack = _stack()
    sha = gpu.apply(engine, stack, _env(tmp_path), find=lambda dirs: "/etc/cdi/nvidia.yaml")
    path = gpu.override_path(_env(tmp_path))
    assert engine.files == ["/p/docker-compose.yml", path]
    data = yaml.safe_load(Path(path).read_text())
    assert data == {"services": {"cuquantum_runner": {"devices": [gpu.DEVICE]}}}
    assert stack.gpu_spec == "/etc/cdi/nvidia.yaml" and stack.gpu_services == ["cuquantum"]
    assert sha and gpu.apply(engine, stack, _env(tmp_path), find=lambda dirs: "/etc/cdi/nvidia.yaml") == sha
    assert engine.files.count(path) == 1


def test_without_a_specification_compose_gets_no_override(tmp_path):
    engine = SimpleNamespace(name="podman", info={}, files=["/p/docker-compose.yml"])
    stack = _stack()
    assert gpu.apply(engine, stack, _env(tmp_path), find=lambda dirs: None) is None
    assert engine.files == ["/p/docker-compose.yml"]
    assert stack.gpu_spec is None and stack.gpu_services == ["cuquantum"]


def test_without_a_gpu_service_the_host_is_not_searched(tmp_path):
    engine = SimpleNamespace(name="podman", info={}, files=[])

    def find(dirs):
        raise AssertionError("searched")

    stack = _stack(gpu_label=False)
    assert gpu.apply(engine, stack, _env(tmp_path), find=find) is None
    assert stack.gpu_services == []


def test_start_does_not_wait_for_a_gpu_service_without_a_gpu(monkeypatch, capsys):
    from qrosetta_cli.stack import serve

    stack = _stack()
    stack.gpu_services = ["cuquantum"]
    monkeypatch.setattr(serve, "stack_url", lambda engine, stack: None)
    monkeypatch.setattr(stack, "kind_of", lambda s: "runner")
    assert serve.wait_ready(SimpleNamespace(), None, stack, ["cuquantum_runner"]) == []
    assert "cuquantum: no CDI specification for an NVIDIA GPU" in capsys.readouterr().err


@pytest.mark.skipif(not (_REPO / "docker-compose.yml").exists(), reason="repository layout not available")
def test_the_gpu_label_marks_exactly_the_runners_config_says_need_a_gpu():
    from config import settings

    compose = yaml.safe_load((_REPO / "docker-compose.yml").read_text())["services"]
    labelled = {
        (svc.get("labels") or {}).get("org.qrosetta.id")
        for svc in compose.values()
        if (svc.get("labels") or {}).get(gpu.GPU_LABEL) == "nvidia"
    }
    needs = {key for key, svc in settings.get_runner_services().items() if svc.get("requires_gpu")}
    assert labelled == needs == {"cuquantum"}
