from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
GEOJSON_DIR = PROJECT_ROOT / "geojsons"
RAW_DATA_DIR = PROJECT_ROOT / "raw_data"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"


def ensure_outputs_dir() -> Path:
    """Return path to `outputs/`, creating it if missing."""
    OUTPUTS_DIR.mkdir(exist_ok=True)
    return OUTPUTS_DIR


def require_path(path: Path) -> Path:
    """Validate that a path exists and return it.

    Raises a clear error early in a pipeline instead of failing deeper inside
    pandas/geopandas IO routines.
    """

    if not path.exists():
        raise FileNotFoundError(path)
    return path
