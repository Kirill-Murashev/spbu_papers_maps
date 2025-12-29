#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

import folium
import pandas as pd
from branca.colormap import linear

from spbu_maps.paths import DATA_DIR, GEOJSON_DIR, PROJECT_ROOT

MAPS_DIR = PROJECT_ROOT / "maps"


def load_metrics() -> pd.DataFrame:
    path = DATA_DIR / "deals_quarter_metrics.csv"
    if not path.exists():
        raise SystemExit("Нет deals_quarter_metrics.csv — пересчитайте метрики.")
    df = pd.read_csv(path)
    df["quarter_cad_number"] = df["quarter_cad_number"].astype(str)
    df["median"] = pd.to_numeric(df["median"], errors="coerce")
    df["count"] = pd.to_numeric(df["count"], errors="coerce")
    return df


def load_geojson() -> dict:
    with (GEOJSON_DIR / "78_filtered.geojson").open(encoding="utf-8") as f:
        return json.load(f)


def bbox_center(gj: dict) -> tuple[float, float]:
    min_lat = min_lon = 1e9
    max_lat = max_lon = -1e9

    def walk(obj):
        nonlocal min_lat, min_lon, max_lat, max_lon
        if isinstance(obj[0], (float, int)):
            lon, lat = obj
            min_lat = min(min_lat, lat)
            max_lat = max(max_lat, lat)
            min_lon = min(min_lon, lon)
            max_lon = max(max_lon, lon)
        else:
            for item in obj:
                walk(item)

    for feat in gj.get("features", []):
        geom = feat.get("geometry") or {}
        coords = geom.get("coordinates")
        if coords:
            walk(coords)

    return (min_lat + max_lat) / 2, (min_lon + max_lon) / 2


def build_map(output: Path) -> None:
    metrics = load_metrics()
    gj = load_geojson()

    metric_map = metrics.set_index("quarter_cad_number")[["median", "count"]].to_dict("index")
    features = []
    for feat in gj.get("features", []):
        props = dict(feat.get("properties") or {})
        cadnum = props.get("cadnum")
        stats = metric_map.get(cadnum, {})
        props["median"] = stats.get("median")
        props["count"] = stats.get("count")
        features.append({"type": feat.get("type"), "geometry": feat.get("geometry"), "properties": props})
    themed = {"type": "FeatureCollection", "features": features}

    values = metrics["median"].dropna()
    colormap = linear.YlOrRd_09.scale(float(values.min()), float(values.max()))
    colormap.caption = "Сделки: медиана цены за кв.м"

    def style_function(feature):
        val = feature["properties"].get("median")
        if val is None:
            return {"fillColor": "#dddddd", "color": "#000000", "weight": 2, "fillOpacity": 0.1}
        return {"fillColor": colormap(val), "color": "#000000", "weight": 2, "fillOpacity": 0.65}

    center_lat, center_lon = bbox_center(themed)
    fmap = folium.Map(location=[center_lat, center_lon], tiles="OpenStreetMap", zoom_start=13)

    folium.GeoJson(
        themed,
        style_function=style_function,
        highlight_function=lambda _: {"weight": 3, "color": "black"},
        tooltip=folium.features.GeoJsonTooltip(
            fields=["cadnum", "median", "count"],
            aliases=["Кадастровый квартал", "Медиана цены за кв.м", "Сделок"],
            localize=True,
        ),
        name="Сделки: медиана цены за кв.м",
    ).add_to(fmap)

    colormap.add_to(fmap)

    borders = folium.FeatureGroup(name="Границы кварталов", show=True)
    folium.GeoJson(
        gj,
        style_function=lambda _: {"color": "black", "weight": 3, "fillOpacity": 0},
        highlight_function=lambda _: {"weight": 4, "color": "black"},
    ).add_to(borders)
    borders.add_to(fmap)

    folium.LayerControl(collapsed=False).add_to(fmap)

    output.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(output)
    print(f"Saved median-only map to {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Карта медианных цен сделок по кварталам")
    parser.add_argument(
        "--output",
        type=Path,
        default=MAPS_DIR / "deals_median_only.html",
        help="Путь для сохранения HTML",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_map(args.output)


if __name__ == "__main__":
    main()
