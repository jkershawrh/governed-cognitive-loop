from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_process_local_safety_state_uses_one_worker_and_one_replica():
    containerfile = (ROOT / "Containerfile").read_text(encoding="utf-8")
    assert '"--workers", "1"' in containerfile

    documents = list(
        yaml.safe_load_all(
            (ROOT / "deploy" / "deployment.yaml").read_text(encoding="utf-8")
        )
    )
    deployment = next(
        document
        for document in documents
        if document and document.get("kind") == "Deployment"
        and document["metadata"]["name"] == "gcl-app"
    )
    assert deployment["spec"]["replicas"] == 1
