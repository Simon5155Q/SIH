import math

def calculate_haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates distance in meters between two lat/lon coordinates."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def is_within_geofence(officer_lat: float, officer_lon: float, shop_lat: float, shop_lon: float, radius_meters: float = 200.0) -> bool:
    """Verifies if an inspection officer is within the allowed physical perimeter."""
    dist = calculate_haversine_distance(officer_lat, officer_lon, shop_lat, shop_lon)
    return dist <= radius_meters
