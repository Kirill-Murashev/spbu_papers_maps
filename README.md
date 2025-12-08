# SPbU Maps Toolkit

Небольшой набор утилит для подготовки карт и визуализаций для статей и исследовательских проектов. Репозиторий хранит готовые данные (`data/` и `geojsons/`) и код для их загрузки и отрисовки. Сырые выгрузки (`raw_data/`) исключены из Git.

## Структура
- `data/` — чистые табличные датасеты, которые используются в сценариях.
- `geojsons/` — геометрия (районы, кварталы и т.п.) в формате GeoJSON.
- `raw_data/` — сырые выгрузки и промежуточные файлы; **не коммитим**.
- `src/spbu_maps/` — пакет с утилитами для загрузки данных и построения карт.
- `scripts/` — готовые CLI/примерные сценарии.
- `tests/` — базовые тесты (по умолчанию минимальны).

## Установка
Рекомендуемый Python ≥3.10.

```bash
# создание и активация окружения (пример)
python -m venv .venv
source .venv/bin/activate

# установка зависимостей и пакета в editable-режиме
pip install --upgrade pip
pip install -e .[dev]
```

Основные зависимости: `pandas`, `geopandas`, `shapely`, `pyproj`, `matplotlib`, `folium`, `tqdm`. Dev-набор: `pytest`, `ruff`, `black`.

## Быстрый старт
Пример: загрузить таблицу и построить простую веб-карту в `outputs/quick_map.html`.

```bash
python scripts/quick_map.py --table bids_panel_final_ds.csv --geometry 47.geojson --id-col area_id --lat-col lat --lon-col lon
```

Более общий пример работы из Python:

```python
from spbu_maps import data_io, mapping

df = data_io.load_table("deals_panel_final_ds.csv")
geo = data_io.load_geojson("47.geojson", id_column="area_id")

# объединение и отрисовка
merged = geo.merge(df, on="area_id", how="left")
map_ = mapping.make_folium_map(merged, value_column="price", tiles="cartodbpositron")
map_.save("outputs/deals_map.html")
```

## Политика данных
- `data/` и `geojsons/` храним в Git (позволяет воспроизводить карты).
- `raw_data/` добавлен в `.gitignore`: локальные выгрузки, черновики и закрытые файлы остаются только на машине.

## Проверки
```
ruff check src tests
black --check src tests
pytest
```

## Идеи для расширения
- Отдельные пайплайны подготовки `raw_data -> data` (например, через `pandas` или `pydantic` для валидации).
- Шаблоны карт (матplotlib/folium) с оформлением под журнальные требования.
- Документация в `docs/` или Jupyter-ноутбуки с воспроизводимыми примерами.
