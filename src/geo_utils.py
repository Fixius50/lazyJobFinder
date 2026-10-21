"""Utilidades matemáticas puras de geolocalización por radio y distancias para lazyJobFinder.

Sin listas hardcodeadas de ciudades: las coordenadas y nombres son proporcionados dinámicamente
por el mapa del frontend (OpenStreetMap / GPS / Nominatim).
"""

import math
from typing import Tuple


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula la distancia en kilómetros entre dos coordenadas GPS usando la fórmula de Haversine."""
    R = 6371.0  # Radio medio de la Tierra en km

    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    r_lat1 = math.radians(lat1)
    r_lat2 = math.radians(lat2)

    a = math.sin(d_lat / 2) ** 2 + math.cos(r_lat1) * math.cos(r_lat2) * math.sin(d_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def get_bounding_box(lat: float, lon: float, radius_km: float) -> Tuple[float, float, float, float]:
    """
    Calcula el cuadro delimitador (bounding box) para un radio dado en kilómetros.
    Devuelve (min_lat, max_lat, min_lon, max_lon).
    """
    R = 6371.0
    lat_delta = math.degrees(radius_km / R)
    lon_delta = math.degrees(radius_km / (R * math.cos(math.radians(lat))))
    return (lat - lat_delta, lat + lat_delta, lon - lon_delta, lon + lon_delta)
