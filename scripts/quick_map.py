#!/usr/bin/env python
from __future__ import annotations

import argparse
from pathlib import Path

from spbu_maps import data_io, mapping
from spbu_maps.paths import ensure_outputs_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Собрать простую интерактивную карту из таблицы и GeoJSON")
    parser.add_argument("--table", required=True, help="Имя файла в data/ или абсолютный путь")
    parser.add_argument("--geometry", required=True, help="Имя файла в geojsons/ или абсолютный путь")
    parser.add_argument("--id-col", required=True, help="Имя столбца для объединения таблицы и геометрии")
    parser.add_argument("--value-col", help="Столбец с показателем для окраски")
    parser.add_argument(
        "--tooltip-cols",
        nargs="*",
        help="Столбцы, которые показывать во всплывающей подсказке",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ensure_outputs_dir() / "quick_map.html",
        help="Путь для сохранения html-карты",
    )
    parser.add_argument(
        "--tiles",
        default=mapping.DEFAULT_TILES,
        help="Слой подложки folium (например, cartodbpositron, openstreetmap)",
    )
    parser.add_argument(
        "--zoom-start",
        type=int,
        default=10,
        help="Начальный zoom для карты",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    table = data_io.load_table(args.table)
    geo = data_io.load_geojson(args.geometry, id_column=args.id_col)

    merged = data_io.merge_geo_with_table(geo, table, on=args.id_col)
    fmap = mapping.make_folium_map(
        merged,
        value_column=args.value_col,
        tiles=args.tiles,
        tooltip_columns=args.tooltip_cols,
        legend_name=args.value_col,
        zoom_start=args.zoom_start,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(args.output)
    print(f"Saved map to {args.output}")


if __name__ == "__main__":
    main()
