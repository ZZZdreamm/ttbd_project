from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_marimo_requires_a_token():
    dockerfile = (ROOT / "lab/Dockerfile").read_text()
    compose = (ROOT / "lab/docker-compose.yml").read_text()
    assert "--no-token" not in dockerfile
    assert "--token-password" in dockerfile and "LAB_TOKEN" in compose


def test_lab_task_prints_tokenised_url():
    mise = (ROOT / "mise.toml").read_text()
    lab = mise[mise.index("[tasks.lab]"):mise.index('[tasks."lab:down"]')]
    assert ".secrets/lab_token" in lab and "access_token=" in lab


def test_notebooks_run_manually():
    import tomllib

    runtime = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["marimo"]["runtime"]
    assert runtime == {"auto_instantiate": False, "on_cell_change": "lazy"}
