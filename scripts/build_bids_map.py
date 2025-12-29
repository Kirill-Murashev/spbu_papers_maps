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


def load_bids(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["lat"] = pd.to_numeric(df["Широта"], errors="coerce")
    df["lon"] = pd.to_numeric(df["Долгота"], errors="coerce")
    df["price_per_sqm"] = pd.to_numeric(
        df["Цена за кв.м, руб."].astype(str).str.replace(" ", ""), errors="coerce"
    )
    df = df.dropna(subset=["lat", "lon", "price_per_sqm"])
    return df


def load_deal_metrics(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"quarter_cad_number", "arith_mean", "geom_mean", "median", "count"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Нет колонок {missing} в {path}")
    df["quarter_cad_number"] = df["quarter_cad_number"].astype(str)
    return df


def add_metric_layer(
    fmap: folium.Map,
    gj: dict,
    metrics: pd.DataFrame,
    metric_col: str,
    name: str,
    show: bool,
) -> None:
    values = metrics[metric_col].dropna()
    if values.empty:
        return
    colormap = linear.YlOrRd_09.scale(float(values.min()), float(values.max()))
    colormap.caption = name

    metric_map = metrics.set_index("quarter_cad_number")[["count", metric_col]].to_dict("index")

    features = []
    for feat in gj.get("features", []):
        props = dict(feat.get("properties") or {})
        cadnum = props.get("cadnum")
        stats = metric_map.get(cadnum, {})
        props[metric_col] = stats.get(metric_col)
        props["count"] = stats.get("count")
        features.append({"type": feat.get("type"), "geometry": feat.get("geometry"), "properties": props})

    themed = {"type": "FeatureCollection", "features": features}

    def style_function(feature):
        value = feature["properties"].get(metric_col)
        color = colormap(value) if value is not None else "#dddddd"
        return {
            "fillColor": color,
            "color": "#222222",
            "weight": 2.5,
            "fillOpacity": 0.6 if value is not None else 0.1,
        }

    layer = folium.FeatureGroup(name=name, show=show)
    folium.GeoJson(
        themed,
        style_function=style_function,
        highlight_function=lambda _: {"weight": 3, "color": "black"},
        tooltip=folium.features.GeoJsonTooltip(
            fields=["cadnum", metric_col, "count"],
            aliases=["Кадастровый квартал", name, "Сделок"],
            localize=True,
        ),
    ).add_to(layer)
    colormap.add_to(layer)
    layer.add_to(fmap)


def build_map(output: Path) -> None:
    bids = load_bids(DATA_DIR / "bids_panel_final_ds.csv")
    if bids.empty:
        raise SystemExit("Файл с предложениями пуст или не содержит корректных координат.")

    center_lat = bids["lat"].mean()
    center_lon = bids["lon"].mean()

    fmap = folium.Map(location=[center_lat, center_lon], tiles="OpenStreetMap", zoom_start=12)

    values = bids["price_per_sqm"]
    colormap = linear.YlOrRd_09.scale(float(values.min()), float(values.max()))
    colormap.caption = "Предложения: цена за кв.м (яркая шкала)"

    bids_layer = folium.FeatureGroup(name="Предложения (точки)", show=True)
    for _, row in bids.iterrows():
        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=5,
            color=colormap(row["price_per_sqm"]),
            fill=True,
            fill_opacity=0.9,
            popup=(
                f"{row['Адрес']}<br>"
                f"Цена за кв.м: {row['price_per_sqm']:.0f} руб.<br>"
                f"Цена объекта: {row['Цена, руб']}"
            ),
        ).add_to(bids_layer)

    bids_layer.add_to(fmap)
    colormap.add_to(fmap)

    # Границы кадастровых кварталов и заливка метрик сделок
    filtered_geojson = GEOJSON_DIR / "78_filtered.geojson"
    deals_path = DATA_DIR / "deals_panel_final_ds.csv"
    metrics_path = DATA_DIR / "deals_quarter_metrics.csv"
    metrics = load_deal_metrics(metrics_path) if metrics_path.exists() else None

    if filtered_geojson.exists():
        with filtered_geojson.open(encoding="utf-8") as f:
            gj = json.load(f)

        borders_layer = folium.FeatureGroup(name="Границы кварталов", show=True)
        folium.GeoJson(
            gj,
            style_function=lambda _: {"color": "black", "weight": 3, "fillOpacity": 0},
            highlight_function=lambda _: {"weight": 4, "color": "black"},
        ).add_to(borders_layer)
        borders_layer.add_to(fmap)

        if metrics is not None and not metrics.empty:
            add_metric_layer(
                fmap,
                gj,
                metrics,
                metric_col="median",
                name="Сделки: медиана цены за кв.м",
                show=True,
            )
            add_metric_layer(
                fmap,
                gj,
                metrics,
                metric_col="arith_mean",
                name="Сделки: среднее арифм. цены за кв.м",
                show=False,
            )
            add_metric_layer(
                fmap,
                gj,
                metrics,
                metric_col="geom_mean",
                name="Сделки: среднее геом. цены за кв.м",
                show=False,
            )

    folium.LayerControl(collapsed=False).add_to(fmap)

    output.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(output)
    print(f"Saved bids map to {output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Построить карту предложений по координатам")
    parser.add_argument(
        "--output",
        type=Path,
        default=MAPS_DIR / "bids_map.html",
        help="Куда сохранить HTML карту",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_map(args.output)


if __name__ == "__main__":
    main()
