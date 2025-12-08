from spbu_maps import paths


def test_directories_exist():
    assert paths.DATA_DIR.exists()
    assert paths.GEOJSON_DIR.exists()
    assert paths.RAW_DATA_DIR.exists()
