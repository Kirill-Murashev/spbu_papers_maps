from __future__ import annotations

from typing import Iterable, Optional

import folium
import geopandas as gpd
import matplotlib.pyplot as plt

DEFAULT_TILES = "cartodbpositron"


def make_folium_map(
    geo: gpd.GeoDataFrame,
    value_column: Optional[str] = None,
    *,
    tiles: str = DEFAULT_TILES,
    tooltip_columns: Optional[Iterable[str]] = None,
    legend_name: Optional[str] = None,
    zoom_start: int = 10,
) -> folium.Map:
    """Создать интерактивную карту на folium с опциональной хлороплетой."""

    if geo.empty:
        raise ValueError("GeoDataFrame is empty; nothing to plot")

    center = geo.to_crs(4326).geometry.unary_union.centroid
    fmap = folium.Map(location=[center.y, center.x], zoom_start=zoom_start, tiles=tiles)

    if value_column:
        folium.Choropleth(
            geo_data=geo.to_json(),
            data=geo,
            columns=[geo.index.name or "id", value_column],
            key_on=f"feature.properties.{geo.index.name or 'id'}",
            fill_color="YlGnBu",
            fill_opacity=0.7,
            line_opacity=0.2,
            legend_name=legend_name or value_column,
        ).add_to(fmap)

    if tooltip_columns:
        folium.GeoJson(
            geo,
            tooltip=folium.features.GeoJsonTooltip(fields=list(tooltip_columns)),
        ).add_to(fmap)
    else:
        folium.GeoJson(geo).add_to(fmap)

    return fmap


def plot_static_map(
    geo: gpd.GeoDataFrame,
    *,
    column: Optional[str] = None,
    cmap: str = "viridis",
    figsize: tuple[int, int] = (8, 8),
    edgecolor: str = "white",
    linewidth: float = 0.5,
    legend: bool = True,
):
    """Построить статичную карту (matplotlib)."""

    if geo.empty:
        raise ValueError("GeoDataFrame is empty; nothing to plot")

    fig, ax = plt.subplots(figsize=figsize)
    geo.plot(
        ax=ax,
        column=column,
        cmap=cmap,
        edgecolor=edgecolor,
        linewidth=linewidth,
        legend=legend if column else False,
    )
    ax.set_axis_off()
    return fig, ax
