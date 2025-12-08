from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import geopandas as gpd
import pandas as pd

from .paths import DATA_DIR, GEOJSON_DIR, require_path

SUPPORTED_TABLE_SUFFIXES = {".csv", ".tsv", ".xls", ".xlsx", ".ods", ".parquet"}
SUPPORTED_GEO_SUFFIXES = {".geojson", ".json"}


def _resolve(base_dir: Path, filename: str | Path) -> Path:
    path = Path(filename)
    return path if path.is_absolute() else base_dir / path


def list_tables() -> List[str]:
    return sorted(p.name for p in DATA_DIR.glob("*") if p.suffix.lower() in SUPPORTED_TABLE_SUFFIXES)


def list_geojsons() -> List[str]:
    return sorted(p.name for p in GEOJSON_DIR.glob("*") if p.suffix.lower() in SUPPORTED_GEO_SUFFIXES)


def load_table(filename: str | Path, **kwargs) -> pd.DataFrame:
    """Загрузить табличный датасет из `data/`.

    Поддерживаемые форматы: csv/tsv/xls/xlsx/ods/parquet.
    Дополнительные аргументы передаются в `pandas.read_*`.
    """

    path = require_path(_resolve(DATA_DIR, filename))
    suffix = path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(path, **kwargs)
    if suffix == ".tsv":
        return pd.read_csv(path, sep="\t", **kwargs)
    if suffix in {".xls", ".xlsx"}:
        return pd.read_excel(path, **kwargs)
    if suffix == ".ods":
        return pd.read_excel(path, engine="odf", **kwargs)
    if suffix == ".parquet":
        return pd.read_parquet(path, **kwargs)

    raise ValueError(f"Unsupported table format: {suffix}")


def load_geojson(filename: str | Path, id_column: str | None = None, **kwargs) -> gpd.GeoDataFrame:
    """Загрузить геометрию из `geojsons/` с опциональным индексом."""

    path = require_path(_resolve(GEOJSON_DIR, filename))
    gdf = gpd.read_file(path, **kwargs)
    if id_column:
        if id_column not in gdf.columns:
            raise KeyError(f"Column '{id_column}' not found in {path}")
        gdf = gdf.set_index(id_column, drop=False)
    return gdf


def merge_geo_with_table(
    geo: gpd.GeoDataFrame,
    table: pd.DataFrame,
    on: str,
    how: str = "left",
    suffixes: tuple[str, str] = ("", "_other"),
) -> gpd.GeoDataFrame:
    """Удобное объединение таблицы с геометрией.

    Делает копию GeoDataFrame, чтобы избежать SettingWithCopy и побочных эффектов.
    """

    return geo.copy().merge(table, on=on, how=how, suffixes=suffixes)


def save_table(df: pd.DataFrame, path: str | Path, *, mkdir: bool = True, **kwargs) -> Path:
    """Сохранить таблицу в csv. Создает директорию при необходимости."""

    output_path = Path(path)
    if mkdir:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, **kwargs)
    return output_path


def save_geojson(gdf: gpd.GeoDataFrame, path: str | Path, *, mkdir: bool = True, **kwargs) -> Path:
    """Сохранить GeoDataFrame в GeoJSON."""

    output_path = Path(path)
    if mkdir:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(output_path, driver="GeoJSON", **kwargs)
    return output_path
