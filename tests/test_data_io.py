import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

from spbu_maps import data_io


def test_load_table_missing(tmp_path):
    missing = tmp_path / "nope.csv"
    try:
        data_io.load_table(missing)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("Expected FileNotFoundError for missing file")


def test_merge_geo_with_table():
    geo = gpd.GeoDataFrame({"id": [1, 2]}, geometry=[Point(0, 0), Point(1, 1)], crs="EPSG:4326").set_index("id")
    table = pd.DataFrame({"id": [1], "val": [10]})
    merged = data_io.merge_geo_with_table(geo, table, on="id")
    assert "val" in merged.columns
    assert merged.loc[1, "val"] == 10
    assert merged.loc[2, "val"] != merged.loc[2, "val"] or pd.isna(merged.loc[2, "val"])
