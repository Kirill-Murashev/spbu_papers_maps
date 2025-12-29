#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List

import folium
import numpy as np
import pandas as pd
from branca.colormap import linear

from spbu_maps.paths import DATA_DIR, GEOJSON_DIR, PROJECT_ROOT


MAPS_DIR = PROJECT_ROOT / "maps"


def geometric_mean(series: pd.Series) -> float:
    positive = series[series > 0].dropna()
    if positive.empty:
        return float("nan")
    return float(np.exp(np.log(positive).mean()))


def load_deals(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, sep=";")
    df["quarter_cad_number"] = df["quarter_cad_number"].astype(str)
    df["price_per_sqm"] = pd.to_numeric(df["price_per_sqm"], errors="coerce")
    df = df[df["price_per_sqm"] > 0]

    grouped = df.groupby("quarter_cad_number")["price_per_sqm"]
    stats = grouped.agg(arith_mean="mean", median="median", count="count")
    stats["geom_mean"] = grouped.apply(geometric_mean)
    return stats.reset_index()


def load_bids(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["lat"] = pd.to_numeric(df["Широта"], errors="coerce")
    df["lon"] = pd.to_numeric(df["Долгота"], errors="coerce")
    df["price_per_sqm"] = pd.to_numeric(
        df["Цена за кв.м, руб."].astype(str).str.replace(" ", ""), errors="coerce"
    )
    df = df.dropna(subset=["lat", "lon", "price_per_sqm"])
    return df


def filter_geojson(geojson_path: Path, allowed_ids: Iterable[str]) -> Dict:
    allowed_set = {str(x) for x in allowed_ids}
    with open(geojson_path, encoding="utf-8") as f:
        gj = json.load(f)

    filtered_features: List[Dict] = []
    for feat in gj.get("features", []):
        props = feat.get("properties", {}) or {}
        cadnum = props.get("externalKey") or props.get("label")
        options = props.get("options") or {}
        if not cadnum and isinstance(options, dict):
            cadnum = options.get("cad_num")

        if cadnum and str(cadnum) in allowed_set:
            feat["properties"]["cadnum"] = str(cadnum)
            filtered_features.append(feat)

    return {**gj, "features": filtered_features}


def add_metric_layer(
    fmap: folium.Map, geojson: Dict, metrics: pd.DataFrame, metric_col: str, name: str, show: bool
) -> None:
    values = metrics[metric_col].dropna()
    vmin, vmax = float(values.min()), float(values.max())
    colormap = linear.YlOrRd_09.scale(vmin, vmax)
    colormap.caption = name
    metric_map = metrics.set_index("quarter_cad_number")[[metric_col, "count"]].to_dict("index")

    features = []
    for feat in geojson.get("features", []):
        props = (feat.get("properties") or {}).copy()
        cadnum = props.get("cadnum")
        stats = metric_map.get(cadnum)
        props[metric_col] = stats.get(metric_col) if stats else None
        props["count"] = stats.get("count") if stats else None
        features.append({"type": feat.get("type"), "geometry": feat.get("geometry"), "properties": props})

    themed_geojson = {"type": "FeatureCollection", "features": features}

    def style_function(feature: Dict) -> Dict:
        value = feature["properties"].get(metric_col)
        color = colormap(value) if value is not None else "#dddddd"
        return {"fillColor": color, "color": "#555", "weight": 0.6, "fillOpacity": 0.7 if value is not None else 0.2}

    layer = folium.FeatureGroup(name=name, show=show)
    gj = folium.GeoJson(
        themed_geojson,
        style_function=style_function,
        highlight_function=lambda _: {"weight": 1.5, "color": "black"},
        tooltip=folium.features.GeoJsonTooltip(
            fields=["cadnum", metric_col, "count"],
            aliases=["Кадастровый квартал", name, "Число сделок"],
            localize=True,
        ),
    )
    gj.add_to(layer)

    colormap.add_to(layer)
    layer.add_to(fmap)


def add_bids_layer(fmap: folium.Map, bids: pd.DataFrame) -> None:
    values = bids["price_per_sqm"]
    colormap = linear.Blues_09.scale(float(values.min()), float(values.max()))
    colormap.caption = "Предложения: цена за кв.м"

    layer = folium.FeatureGroup(name="Предложения (точки)", show=True)
    for _, row in bids.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=4,
            color=colormap(row["price_per_sqm"]),
            fill=True,
            fill_opacity=0.8,
            popup=f"{row['Адрес']}<br>Цена за кв.м: {row['price_per_sqm']:.0f} руб.",
        ).add_to(layer)

    colormap.add_to(layer)
    layer.add_to(fmap)


def build_map(output_path: Path) -> None:
    deals_path = DATA_DIR / "deals_panel_final_ds.csv"
    bids_path = DATA_DIR / "bids_panel_final_ds.csv"
    geojson_path = GEOJSON_DIR / "78.geojson"

    metrics = load_deals(deals_path)
    geojson = filter_geojson(geojson_path, metrics["quarter_cad_number"])
    bids = load_bids(bids_path)

    center_lat = bids["lat"].mean()
    center_lon = bids["lon"].mean()

    fmap = folium.Map(location=[center_lat, center_lon], tiles="OpenStreetMap", zoom_start=11)

    add_metric_layer(fmap, geojson, metrics, "arith_mean", "Среднее арифм. цены сделок", show=True)
    add_metric_layer(fmap, geojson, metrics, "geom_mean", "Среднее геом. цены сделок", show=False)
    add_metric_layer(fmap, geojson, metrics, "median", "Медиана цены сделок", show=False)
    add_bids_layer(fmap, bids)

    folium.LayerControl(collapsed=False).add_to(fmap)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(output_path)
    print(f"Saved map to {output_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Построить тепловую карту сделок и предложений")
    parser.add_argument(
        "--output",
        type=Path,
        default=MAPS_DIR / "deals_bids_heatmap.html",
        help="Путь для сохранения HTML карты",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_map(args.output)


if __name__ == "__main__":
    main()
