#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, Tuple

import folium
import pandas as pd
from branca.colormap import linear

from spbu_maps.paths import DATA_DIR, GEOJSON_DIR, MAPS_DIR


def load_data(path: Path) -> pd.DataFrame:
    # попытка прочитать utf-8 с запятой, затем ; cp1251, затем ; utf-8
    for params in ({}, {"sep": ";", "encoding": "cp1251"}, {"sep": ";"}):
        try:
            df = pd.read_csv(path, **params)
            if "price_per_sqm" in df.columns:
                break
        except Exception:
            continue
    if "price_per_sqm" not in df.columns:
        raise SystemExit(f"Не найден столбец price_per_sqm в {path}")
    df = df[df["price_per_sqm"] > 0].copy()
    df["quarter_cad_number"] = df["quarter_cad_number"].astype(str)
    return df


def compute_median(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby("quarter_cad_number")["price_per_sqm"]
    metrics = grouped.agg(median="median", count="count").reset_index()
    metrics["median_round"] = metrics["median"].round(0).astype(int)
    return metrics


def filter_geojson(geo_path: Path, allowed: Iterable[str]) -> Dict:
    allowed_set = set(allowed)
    with geo_path.open(encoding="utf-8") as f:
        gj = json.load(f)
    filtered = []
    for feat in gj.get("features", []):
        props = feat.get("properties") or {}
        opts = props.get("options") or {}
        cadnum = props.get("externalKey") or props.get("label") or opts.get("cad_num")
        if cadnum and cadnum in allowed_set and feat.get("geometry"):
            props["cadnum"] = cadnum
            filtered.append({"type": feat.get("type"), "geometry": feat.get("geometry"), "properties": props})
    return {"type": "FeatureCollection", "features": filtered}


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


def feature_centroid(feature: Dict) -> Tuple[float, float]:
    coords = feature.get("geometry", {}).get("coordinates")
    points = []

    def walk(obj):
        if isinstance(obj[0], (float, int)):
            lon, lat = obj
            points.append((lon, lat))
        else:
            for item in obj:
                walk(item)

    walk(coords)
    if not points:
        return (0.0, 0.0)
    lon_sum = sum(p[0] for p in points)
    lat_sum = sum(p[1] for p in points)
    n = len(points)
    return (lat_sum / n, lon_sum / n)


def add_layers(fmap: folium.Map, gj: Dict, metrics: pd.DataFrame, colormap) -> None:
    metric_map = metrics.set_index("quarter_cad_number")[["median", "median_round", "count"]].to_dict("index")

    features = []
    for feat in gj.get("features", []):
        props = dict(feat.get("properties") or {})
        cadnum = props.get("cadnum")
        stats = metric_map.get(cadnum, {})
        props["median"] = stats.get("median")
        props["median_round"] = stats.get("median_round")
        props["count"] = stats.get("count")
        features.append({"type": feat.get("type"), "geometry": feat.get("geometry"), "properties": props})
    themed = {"type": "FeatureCollection", "features": features}

    def style_function(feature):
        val = feature["properties"].get("median")
        if val is None or pd.isna(val):
            return {"fillColor": "#dddddd", "color": "#000000", "weight": 1.5, "fillOpacity": 0.1}
        return {"fillColor": colormap(val), "color": "#000000", "weight": 1.5, "fillOpacity": 0.65}

    folium.GeoJson(
        themed,
        style_function=style_function,
        highlight_function=lambda _: {"weight": 2.5, "color": "black"},
        tooltip=folium.features.GeoJsonTooltip(
            fields=["cadnum", "median_round", "count"],
            aliases=["Кадастровый квартал", "Медиана цены за кв.м", "Количество"],
            localize=True,
        ),
        name="Медиана цены за кв.м",
    ).add_to(fmap)

    # labels: last part of cadnum + median + count
    labels = folium.FeatureGroup(name="Подписи", show=True)
    for feat in themed["features"]:
        props = feat.get("properties") or {}
        cadnum = props.get("cadnum", "")
        suffix = cadnum.split(":")[-1] if cadnum else ""
        median = props.get("median_round")
        count = props.get("count")
        median_str = "—" if pd.isna(median) else f"{int(median)}"
        count_str = "—" if count is None or pd.isna(count) else f"{int(count)}"
        lat, lon = feature_centroid(feat)
        html = (
            "<div style='font-size:10px; font-weight:bold; color:black; "
            "text-shadow:1px 1px 2px white;'>"
            f"{suffix}<br>мед: {median_str}<br>n={count_str}</div>"
        )
        folium.Marker(location=[lat, lon], icon=folium.DivIcon(html=html)).add_to(labels)
    labels.add_to(fmap)

    borders = folium.FeatureGroup(name="Границы", show=True)
    folium.GeoJson(
        themed,
        style_function=lambda _: {"color": "black", "weight": 2, "fillOpacity": 0},
        highlight_function=lambda _: {"weight": 3, "color": "black"},
    ).add_to(borders)
    borders.add_to(fmap)


def build_map(input_file: Path, geo_path: Path, output_file: Path) -> None:
    df = load_data(input_file)
    metrics = compute_median(df)
    gj = filter_geojson(geo_path, metrics["quarter_cad_number"])

    center_lat, center_lon = bbox_center(gj)
    fmap = folium.Map(location=[center_lat, center_lon], tiles="OpenStreetMap", zoom_start=13)

    values = metrics["median"].dropna()
    colormap = linear.YlOrRd_09.scale(float(values.min()), float(values.max()))
    colormap.caption = "Медиана цены за кв.м"

    add_layers(fmap, gj, metrics, colormap)
    colormap.add_to(fmap)
    folium.LayerControl(collapsed=False).add_to(fmap)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(output_file)
    print(f"Saved map to {output_file}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Тепловая карта медианы цен за кв.м по кирпичным сделкам")
    parser.add_argument(
        "--input",
        type=Path,
        default=DATA_DIR / "brick_deal_clean.csv",
        help="CSV с ценами сделок (price_per_sqm)",
    )
    parser.add_argument(
        "--geojson",
        type=Path,
        default=GEOJSON_DIR / "78.geojson",
        help="GeoJSON с кварталами",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=MAPS_DIR / "brick_deal_median_map.html",
        help="Куда сохранить HTML карту",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_map(args.input, args.geojson, args.output)


if __name__ == "__main__":
    main()
