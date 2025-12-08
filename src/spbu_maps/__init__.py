"""Утилиты для загрузки данных и построения карт для исследовательских проектов."""

from importlib import metadata

__all__ = ["__version__"]

try:
    __version__ = metadata.version("spbu-maps")
except metadata.PackageNotFoundError:  # pragma: no cover - не установлен как пакет
    __version__ = "0.0.0"
