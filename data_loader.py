"""Load one complete snapshot from local files or a public Google Drive folder."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory


REQUIRED_FILES = (
    "03_claims_checked.json",
    "04_claims_with_drugs.json",
    "05_claims_enriched.json",
    "06_knowledge_base.json",
)


def read_json(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot read valid JSON from {Path(path).name}.") from exc
    if not isinstance(value, list) or not value:
        raise ValueError(f"{Path(path).name} must contain a nonempty JSON array.")
    if not all(isinstance(row, dict) for row in value):
        raise ValueError(f"{Path(path).name} must contain JSON objects.")
    return value


def load_datasets(local_dir, sources):
    """Use a complete local snapshot, or fetch all four files from Drive.

    Partial local files are never mixed with a different remote snapshot.
    """
    local_dir = Path(local_dir)
    if all((local_dir / name).is_file() for name in REQUIRED_FILES):
        return {name: read_json(local_dir / name) for name in REQUIRED_FILES}

    missing = sorted(set(REQUIRED_FILES) - set(sources))
    if missing:
        raise ValueError("Required Drive file IDs are missing: " + ", ".join(missing))

    import gdown

    with TemporaryDirectory(prefix="alz-kb-") as temp:
        datasets = {}
        for name in REQUIRED_FILES:
            path = Path(temp) / name
            downloaded = gdown.download(
                id=sources[name], output=str(path), quiet=True, use_cookies=False,
            )
            if not downloaded:
                raise RuntimeError(f"Google Drive could not download {name}.")
            datasets[name] = read_json(path)
        return datasets
