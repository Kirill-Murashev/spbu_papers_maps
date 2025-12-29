#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Dict, Tuple

import folium
import pandas as pd
from branca.colormap import linear

from spbu_maps.paths import DATA_DIR, GEOJSON_DIR, PROJECT_ROOT


MAPS_DIR = PROJECT_ROOT / "maps"


def compute_metrics_from_deals(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";")
    df["quarter_cad_number"] = df["quarter_cad_number"].astype(str)
    df["price_per_sqm"] = pd.to_numeric(df["price_per_sqm"], errors="coerce")
    df = df[df["price_per_sqm"] > 0]
    grouped = df.groupby("quarter_cad_number")["price_per_sqm"]
    metrics = grouped.agg(median="median", count="count")
    return metrics.reset_index()


def load_metrics() -> pd.DataFrame:
    metrics_path = DATA_DIR / "deals_quarter_metrics.csv"
    if metrics_path.exists():
        df = pd.read_csv(metrics_path)
    else:
        deals_path = DATA_DIR / "deals_panel_final_ds.csv"
        df = compute_metrics_from_deals(deals_path)

    # оставляем только медиану и count
    keep_cols = ["quarter_cad_number", "median", "count"]
    df = df[[c for c in keep_cols if c in df.columns]]

    for col in ["median", "count"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["quarter_cad_number"] = df["quarter_cad_number"].astype(str)
    return df


def load_filtered_geojson() -> Dict:
    path = GEOJSON_DIR / "78_filtered.geojson"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def bbox_center(gj: Dict) -> Tuple[float, float]:
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


def add_metric_layer(fmap: folium.Map, gj: Dict, metrics: pd.DataFrame, metric: str, name: str, show: bool):
    values = metrics[metric].dropna()
    if values.empty:
        return
    colormap = linear.YlOrRd_09.scale(float(values.min()), float(values.max()))
    colormap.caption = name

    metric_map = metrics.set_index("quarter_cad_number")[[metric, "count"]].to_dict("index")

    features = []
    for feat in gj.get("features", []):
        props = dict(feat.get("properties") or {})
        cadnum = props.get("cadnum")
        stats = metric_map.get(cadnum, {})
        props[metric] = stats.get(metric)
        props["count"] = stats.get("count")
        features.append({"type": feat.get("type"), "geometry": feat.get("geometry"), "properties": props})
    themed = {"type": "FeatureCollection", "features": features}

    def style_function(feature):
        val = feature["properties"].get(metric)
        if val is None or (isinstance(val, float) and math.isnan(val)):
            color = "#dddddd"
            opacity = 0.1
        else:
            color = colormap(val)
            opacity = 0.65
        return {"fillColor": color, "color": "#000000", "weight": 2.5, "fillOpacity": opacity}

    layer = folium.FeatureGroup(name=name, show=show)
    folium.GeoJson(
        themed,
        style_function=style_function,
        highlight_function=lambda _: {"weight": 3.5, "color": "black"},
        tooltip=folium.features.GeoJsonTooltip(
            fields=["cadnum", metric, "count"],
            aliases=["Кадастровый квартал", name, "Сделок"],
            localize=True,
        ),
    ).add_to(layer)
    colormap.add_to(layer)
    layer.add_to(fmap)


def build_map(output: Path) -> None:
    metrics = load_metrics()
    gj = load_filtered_geojson()

    center_lat, center_lon = bbox_center(gj)
    fmap = folium.Map(location=[center_lat, center_lon], tiles="OpenStreetMap", zoom_start=13)

    add_metric_layer(fmap, gj, metrics, metric="median", name="Сделки: медиана цены за кв.м", show=True)

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
    print(f"Saved median map to {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Карта медианных цен сделок по кварталам")
    parser.add_argument(
        "--output",
        type=Path,
        default=MAPS_DIR / "deals_median_map.html",
        help="Путь для сохранения HTML",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_map(args.output)


if __name__ == "__main__":
    main()
