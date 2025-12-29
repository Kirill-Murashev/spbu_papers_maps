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


def load_bids() -> pd.DataFrame:
    bids_path = DATA_DIR / "bids_panel_final_ds.csv"
    df = pd.read_csv(bids_path)
    df["lat"] = pd.to_numeric(df["Широта"], errors="coerce")
    df["lon"] = pd.to_numeric(df["Долгота"], errors="coerce")
    df["price_per_sqm"] = pd.to_numeric(
        df["Цена за кв.м, руб."].astype(str).str.replace(" ", ""), errors="coerce"
    )
    return df.dropna(subset=["lat", "lon", "price_per_sqm"])


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
    bids = load_bids()
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

    # карта
    center_lat, center_lon = bbox_center(themed)
    fmap = folium.Map(location=[center_lat, center_lon], tiles="OpenStreetMap", zoom_start=13)

    # слой заливки медианы
    values = metrics["median"].dropna()
    colormap = linear.YlOrRd_09.scale(float(values.min()), float(values.max()))
    colormap.caption = "Сделки: медиана цены за кв.м"

    def style_function(feature):
        val = feature["properties"].get("median")
        if val is None:
            return {"fillColor": "#dddddd", "color": "#000000", "weight": 2, "fillOpacity": 0.1}
        return {"fillColor": colormap(val), "color": "#000000", "weight": 2, "fillOpacity": 0.65}

    deals_layer = folium.FeatureGroup(name="Сделки: медиана цены за кв.м", show=True)
    folium.GeoJson(
        themed,
        style_function=style_function,
        highlight_function=lambda _: {"weight": 3, "color": "black"},
        tooltip=folium.features.GeoJsonTooltip(
            fields=["cadnum", "median", "count"],
            aliases=["Кадастровый квартал", "Медиана цены за кв.м", "Сделок"],
            localize=True,
        ),
    ).add_to(deals_layer)
    deals_layer.add_to(fmap)
    colormap.add_to(fmap)

    # слой границ
    borders = folium.FeatureGroup(name="Границы кварталов", show=True)
    folium.GeoJson(
        gj,
        style_function=lambda _: {"color": "black", "weight": 3, "fillOpacity": 0},
        highlight_function=lambda _: {"weight": 4, "color": "black"},
    ).add_to(borders)
    borders.add_to(fmap)

    # слой предложений
    bid_values = bids["price_per_sqm"]
    bids_layer = folium.FeatureGroup(name="Предложения (точки)", show=True)
    for _, row in bids.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=6,
            color="black",
            fill=True,
            fill_color="black",
            fill_opacity=0.9,
            popup=(
                f"{row['Адрес']}<br>"
                f"Цена за кв.м: {row['price_per_sqm']:.0f} руб.<br>"
                f"Цена объекта: {row['Цена, руб']}"
            ),
        ).add_to(bids_layer)
    bids_layer.add_to(fmap)

    folium.LayerControl(collapsed=False).add_to(fmap)

    output.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(output)
    print(f"Saved map with bids to {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Карта медианных цен сделок и точек предложений")
    parser.add_argument(
        "--output",
        type=Path,
        default=MAPS_DIR / "deals_median_with_bids.html",
        help="Путь для сохранения HTML",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_map(args.output)


if __name__ == "__main__":
    main()
