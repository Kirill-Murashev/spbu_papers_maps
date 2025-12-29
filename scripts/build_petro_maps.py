#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, Tuple

import folium
import pandas as pd
from branca.colormap import linear

from spbu_maps.paths import GEOJSON_DIR, MAPS_DIR, PROJECT_ROOT

DATA_DIR = PROJECT_ROOT / "data"


def load_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";", encoding="cp1251")
    df["quarter_cad_number"] = df["quarter_cad_number"].astype(str)
    df["price_per_sqm"] = pd.to_numeric(df["price_per_sqm"], errors="coerce")
    return df.dropna(subset=["price_per_sqm"])


def compute_metrics(df: pd.DataFrame) -> pd.DataFrame:
    grouped = df.groupby("quarter_cad_number")["price_per_sqm"]
    metrics = grouped.agg(median="median", count="count").reset_index()
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
            feat["properties"] = props
            filtered.append(feat)

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
    """Approximate centroid from polygon coordinates (lon/lat mean)."""
    coords = feature.get("geometry", {}).get("coordinates")
    if not coords:
        return (0.0, 0.0)

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


def add_heat_layer(
    fmap: folium.Map,
    gj: Dict,
    metrics: pd.DataFrame,
    *,
    colormap,
) -> None:
    metric_map = (
        metrics.assign(median_round=metrics["median"].round(0).astype("Int64"))
        .set_index("quarter_cad_number")[["median", "median_round", "count"]]
        .to_dict("index")
    )

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


def add_borders_layer(fmap: folium.Map, gj: Dict) -> None:
    borders = folium.FeatureGroup(name="Границы кварталов", show=True)
    folium.GeoJson(
        gj,
        style_function=lambda _: {"color": "black", "weight": 2, "fillOpacity": 0},
        highlight_function=lambda _: {"weight": 3, "color": "black"},
    ).add_to(borders)
    borders.add_to(fmap)


def add_labels_layer(fmap: folium.Map, gj: Dict, metrics: pd.DataFrame) -> None:
    """Нанести подписи cadnum + медиана + count по данным metrics."""
    metric_map = (
        metrics.assign(median_round=metrics["median"].round(0).astype("Int64"))
        .set_index("quarter_cad_number")[["median", "median_round", "count"]]
        .to_dict("index")
    )
    labels = folium.FeatureGroup(name="Подписи", show=True)
    for feat in gj.get("features", []):
        props = feat.get("properties") or {}
        cadnum = props.get("cadnum")
        stats = metric_map.get(cadnum, {}) if cadnum else {}
        median = stats.get("median_round") if "median_round" in stats else stats.get("median")
        count = stats.get("count")
        median_str = "—"
        if median is not None and not (isinstance(median, float) and pd.isna(median)):
            try:
                median_str = f"{int(round(float(median)))}"
            except Exception:
                median_str = f"{median}"
        count_str = count if count is not None else "—"
        lat, lon = feature_centroid(feat)
        html = (
            "<div style='font-size:10px; font-weight:bold; color:black; text-shadow:1px 1px 2px white;'>"
            f"{cadnum}<br>мед: {median_str}<br>n={count_str}</div>"
        )
        folium.Marker(
            location=[lat, lon],
            icon=folium.DivIcon(html=html),
        ).add_to(labels)
    labels.add_to(fmap)


def build_maps(
    file_a: Path,
    file_b: Path,
    geo_path: Path,
    output_a: Path,
    output_b: Path,
) -> None:
    df_a = load_dataset(file_a)
    df_b = load_dataset(file_b)

    metrics_a = compute_metrics(df_a)
    metrics_b = compute_metrics(df_b)

    quarters_union = set(metrics_a["quarter_cad_number"]).union(metrics_b["quarter_cad_number"])
    gj_filtered = filter_geojson(geo_path, quarters_union)

    # карта A
    center_lat, center_lon = bbox_center(gj_filtered)
    fmap_a = folium.Map(location=[center_lat, center_lon], tiles="OpenStreetMap", zoom_start=13)
    colormap_a = linear.YlOrRd_09.scale(float(metrics_a["median"].min()), float(metrics_a["median"].max()))
    colormap_a.caption = "Медиана цены за кв.м (1703-1969)"
    add_heat_layer(fmap_a, gj_filtered, metrics_a, colormap=colormap_a)
    colormap_a.add_to(fmap_a)
    add_borders_layer(fmap_a, gj_filtered)
    add_labels_layer(fmap_a, gj_filtered, metrics_a)
    folium.LayerControl(collapsed=False).add_to(fmap_a)
    output_a.parent.mkdir(parents=True, exist_ok=True)
    fmap_a.save(output_a)
    print(f"Saved {output_a}")

    # карта B
    fmap_b = folium.Map(location=[center_lat, center_lon], tiles="OpenStreetMap", zoom_start=13)
    colormap_b = linear.YlOrRd_09.scale(float(metrics_b["median"].min()), float(metrics_b["median"].max()))
    colormap_b.caption = "Медиана цены за кв.м (1970-2025)"
    add_heat_layer(fmap_b, gj_filtered, metrics_b, colormap=colormap_b)
    colormap_b.add_to(fmap_b)
    add_borders_layer(fmap_b, gj_filtered)
    add_labels_layer(fmap_b, gj_filtered, metrics_b)
    folium.LayerControl(collapsed=False).add_to(fmap_b)
    fmap_b.save(output_b)
    print(f"Saved {output_b}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Тепловые карты по медиане цены за кв.м для двух периодов")
    parser.add_argument(
        "--file-a",
        type=Path,
        default=DATA_DIR / "petrogradskiy_1703-1969.csv",
        help="Файл данных для первой карты",
    )
    parser.add_argument(
        "--file-b",
        type=Path,
        default=DATA_DIR / "petrogradskiy_1970-2025.csv",
        help="Файл данных для второй карты",
    )
    parser.add_argument(
        "--geojson",
        type=Path,
        default=GEOJSON_DIR / "78.geojson",
        help="GeoJSON с кварталами",
    )
    parser.add_argument(
        "--out-a",
        type=Path,
        default=MAPS_DIR / "petro_prices_1703_1969.html",
        help="Куда сохранить карту для периода 1703-1969",
    )
    parser.add_argument(
        "--out-b",
        type=Path,
        default=MAPS_DIR / "petro_prices_1970_2025.html",
        help="Куда сохранить карту для периода 1970-2025",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_maps(args.file_a, args.file_b, args.geojson, args.out_a, args.out_b)


if __name__ == "__main__":
    main()
