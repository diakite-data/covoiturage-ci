"""
Service géographique
Géocodage, calculs de distance et gestion des cartes
"""
import math
import requests
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from fastapi import HTTPException, status


@dataclass
class Coordinates:
    """Coordonnées géographiques"""
    latitude: float
    longitude: float
    
    def __str__(self):
        return f"{self.latitude}, {self.longitude}"


@dataclass
class RouteInfo:
    """Informations d'un itinéraire"""
    distance_km: float
    duration_minutes: int
    coordinates: List[Tuple[float, float]]
    polyline: Optional[str] = None


@dataclass
class GeocodingResult:
    """Résultat de géocodage"""
    address: str
    coordinates: Coordinates
    city: Optional[str] = None
    country: Optional[str] = None


class GeoService:
    """Service de géolocalisation et cartographie"""
    
    def __init__(self):
        self.nominatim_base_url = "https://nominatim.openstreetmap.org"
        self.overpass_base_url = "https://router.project-osrm.org"
    
    def calculate_distance(self, coord1: Coordinates, coord2: Coordinates) -> float:
        """
        Calcule la distance entre deux coordonnées (formule haversine)
        Retourne la distance en kilomètres
        """
        # Rayon de la Terre en km
        R = 6371.0
        
        # Conversion en radians
        lat1_rad = math.radians(coord1.latitude)
        lon1_rad = math.radians(coord1.longitude)
        lat2_rad = math.radians(coord2.latitude)
        lon2_rad = math.radians(coord2.longitude)
        
        # Différences
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        # Formule haversine
        a = (math.sin(dlat / 2)**2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(dlon / 2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        distance = R * c
        return round(distance, 2)
    
    def geocode_address(self, address: str, city: str = None) -> Optional[GeocodingResult]:
        """
        Géocode une adresse en coordonnées
        Utilise Nominatim (OpenStreetMap)
        """
        try:
            # Construire la requête
            search_query = address
            if city:
                search_query += f", {city}"
            search_query += ", Côte d'Ivoire"
            
            params = {
                "q": search_query,
                "format": "json",
                "limit": 1,
                "countrycodes": "ci",  # Limiter à la Côte d'Ivoire
                "addressdetails": 1
            }
            
            headers = {
                "User-Agent": "CovoiturageCI/1.0"  # Obligatoire pour Nominatim
            }
            
            response = requests.get(
                f"{self.nominatim_base_url}/search",
                params=params,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                results = response.json()
                if results:
                    result = results[0]
                    return GeocodingResult(
                        address=result.get("display_name", address),
                        coordinates=Coordinates(
                            latitude=float(result["lat"]),
                            longitude=float(result["lon"])
                        ),
                        city=result.get("address", {}).get("city"),
                        country=result.get("address", {}).get("country")
                    )
            
            return None
            
        except Exception as e:
            print(f"Erreur géocodage: {e}")
            return None
    
    def reverse_geocode(self, coordinates: Coordinates) -> Optional[str]:
        """
        Géocodage inverse : coordonnées → adresse
        """
        try:
            params = {
                "lat": coordinates.latitude,
                "lon": coordinates.longitude,
                "format": "json",
                "addressdetails": 1
            }
            
            headers = {
                "User-Agent": "CovoiturageCI/1.0"
            }
            
            response = requests.get(
                f"{self.nominatim_base_url}/reverse",
                params=params,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("display_name")
            
            return None
            
        except Exception as e:
            print(f"Erreur géocodage inverse: {e}")
            return None
    
    def calculate_route(self, start: Coordinates, end: Coordinates) -> Optional[RouteInfo]:
        """
        Calcule un itinéraire entre deux points
        Utilise OSRM (Open Source Routing Machine)
        """
        try:
            # URL OSRM
            url = f"{self.overpass_base_url}/route/v1/driving/{start.longitude},{start.latitude};{end.longitude},{end.latitude}"
            
            params = {
                "overview": "full",
                "geometries": "geojson",
                "annotations": "true"
            }
            
            response = requests.get(url, params=params, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("routes"):
                    route = data["routes"][0]
                    
                    # Extraire les coordonnées de la géométrie
                    coordinates = []
                    if route.get("geometry", {}).get("coordinates"):
                        coordinates = [
                            (lat, lng) for lng, lat in route["geometry"]["coordinates"]
                        ]
                    
                    return RouteInfo(
                        distance_km=round(route["distance"] / 1000, 2),
                        duration_minutes=round(route["duration"] / 60),
                        coordinates=coordinates
                    )
            
            # Fallback : calcul distance directe si pas de route
            distance = self.calculate_distance(start, end)
            estimated_duration = int(distance * 1.5)  # ~40 km/h moyenne
            
            return RouteInfo(
                distance_km=distance,
                duration_minutes=estimated_duration,
                coordinates=[(start.latitude, start.longitude), (end.latitude, end.longitude)]
            )
            
        except Exception as e:
            print(f"Erreur calcul route: {e}")
            
            # Fallback en cas d'erreur
            distance = self.calculate_distance(start, end)
            estimated_duration = int(distance * 1.5)
            
            return RouteInfo(
                distance_km=distance,
                duration_minutes=estimated_duration,
                coordinates=[(start.latitude, start.longitude), (end.latitude, end.longitude)]
            )
    
    def find_nearby_points(self, center: Coordinates, radius_km: float, point_type: str = "city") -> List[GeocodingResult]:
        """
        Trouve des points d'intérêt à proximité
        """
        try:
            # Conversion approximative : 1 degré ≈ 111 km
            lat_range = radius_km / 111.0
            lon_range = lat_range / math.cos(math.radians(center.latitude))
            
            bbox = f"{center.longitude - lon_range},{center.latitude - lat_range},{center.longitude + lon_range},{center.latitude + lat_range}"
            
            params = {
                "q": point_type,
                "format": "json",
                "limit": 10,
                "viewbox": bbox,
                "bounded": 1,
                "countrycodes": "ci"
            }
            
            headers = {
                "User-Agent": "CovoiturageCI/1.0"
            }
            
            response = requests.get(
                f"{self.nominatim_base_url}/search",
                params=params,
                headers=headers,
                timeout=10
            )
            
            results = []
            if response.status_code == 200:
                data = response.json()
                for item in data:
                    results.append(GeocodingResult(
                        address=item.get("display_name", ""),
                        coordinates=Coordinates(
                            latitude=float(item["lat"]),
                            longitude=float(item["lon"])
                        ),
                        city=item.get("address", {}).get("city")
                    ))
            
            return results
            
        except Exception as e:
            print(f"Erreur recherche proximité: {e}")
            return []
    
    def is_valid_coordinates(self, coordinates: Coordinates) -> bool:
        """Vérifie si les coordonnées sont valides pour la Côte d'Ivoire"""
        # Bounding box approximatif de la Côte d'Ivoire
        CI_LAT_MIN, CI_LAT_MAX = 4.0, 11.0
        CI_LNG_MIN, CI_LNG_MAX = -9.0, -2.0
        
        return (CI_LAT_MIN <= coordinates.latitude <= CI_LAT_MAX and
                CI_LNG_MIN <= coordinates.longitude <= CI_LNG_MAX)
    
    def estimate_trip_price(self, distance_km: float, base_price_per_km: float = 100) -> float:
        """
        Estime le prix d'un trajet basé sur la distance
        Prix de base : 100 FCFA/km (ajustable)
        """
        if distance_km <= 0:
            return 0
        
        # Prix de base + ajustements
        base_price = distance_km * base_price_per_km
        
        # Ajustements selon la distance
        if distance_km < 10:  # Trajets courts
            return max(base_price, 500)  # Minimum 500 FCFA
        elif distance_km > 100:  # Trajets longs
            return base_price * 0.9  # Réduction pour longs trajets
        
        return round(base_price, -1)  # Arrondir à 10 FCFA près


# Instance globale du service
geo_service = GeoService()
