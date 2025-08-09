"""
Schemas Pydantic pour les données géographiques
"""
from pydantic import BaseModel, validator, Field
from typing import Optional, List, Tuple
from src.services.geo import Coordinates, RouteInfo, GeocodingResult


class CoordinatesRequest(BaseModel):
    """Schema pour les coordonnées en entrée"""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude (-90 à 90)")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude (-180 à 180)")


class GeocodingRequest(BaseModel):
    """Schema pour le géocodage d'une adresse"""
    address: str = Field(..., min_length=3, max_length=255, description="Adresse à géocoder")
    city: Optional[str] = Field(None, max_length=100, description="Ville (optionnel)")


class RouteCalculationRequest(BaseModel):
    """Schema pour calculer un itinéraire"""
    start_latitude: float = Field(..., ge=-90, le=90)
    start_longitude: float = Field(..., ge=-180, le=180)
    end_latitude: float = Field(..., ge=-90, le=90)
    end_longitude: float = Field(..., ge=-180, le=180)


class NearbySearchRequest(BaseModel):
    """Schema pour rechercher des points à proximité"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_km: float = Field(5.0, ge=0.1, le=100, description="Rayon de recherche en km")
    point_type: str = Field("city", description="Type de points recherchés")


# ================ RESPONSES ================

class CoordinatesResponse(BaseModel):
    """Schema de réponse pour les coordonnées"""
    latitude: float
    longitude: float
    
    @classmethod
    def from_coordinates(cls, coords: Coordinates):
        return cls(latitude=coords.latitude, longitude=coords.longitude)


class GeocodingResponse(BaseModel):
    """Schema de réponse pour le géocodage"""
    address: str
    coordinates: CoordinatesResponse
    city: Optional[str] = None
    country: Optional[str] = None
    
    @classmethod
    def from_geocoding_result(cls, result: GeocodingResult):
        return cls(
            address=result.address,
            coordinates=CoordinatesResponse.from_coordinates(result.coordinates),
            city=result.city,
            country=result.country
        )


class RouteResponse(BaseModel):
    """Schema de réponse pour un itinéraire"""
    distance_km: float
    duration_minutes: int
    coordinates: List[Tuple[float, float]]
    estimated_price: Optional[float] = None
    
    @classmethod
    def from_route_info(cls, route: RouteInfo, estimated_price: float = None):
        return cls(
            distance_km=route.distance_km,
            duration_minutes=route.duration_minutes,
            coordinates=route.coordinates,
            estimated_price=estimated_price
        )


class TripRouteResponse(BaseModel):
    """Schema complet pour l'itinéraire d'un trajet"""
    trip_id: Optional[int] = None
    departure_address: str
    departure_coordinates: CoordinatesResponse
    arrival_address: str
    arrival_coordinates: CoordinatesResponse
    route: RouteResponse
    map_center: CoordinatesResponse
    map_zoom: int = 12


class NearbyPointsResponse(BaseModel):
    """Schema de réponse pour les points à proximité"""
    center: CoordinatesResponse
    radius_km: float
    points: List[GeocodingResponse]
    total_found: int
    
    @classmethod
    def from_results(cls, center: Coordinates, radius: float, results: List[GeocodingResult]):
        return cls(
            center=CoordinatesResponse.from_coordinates(center),
            radius_km=radius,
            points=[GeocodingResponse.from_geocoding_result(r) for r in results],
            total_found=len(results)
        )


class DistanceCalculationResponse(BaseModel):
    """Schema de réponse pour le calcul de distance"""
    start: CoordinatesResponse
    end: CoordinatesResponse
    distance_km: float
    estimated_duration_minutes: int
    estimated_price: Optional[float] = None


class MapBoundsResponse(BaseModel):
    """Schema pour les limites d'une carte"""
    north: float
    south: float
    east: float
    west: float
    center: CoordinatesResponse
    
    @classmethod
    def from_coordinates_list(cls, coords_list: List[Coordinates]):
        if not coords_list:
            # Valeurs par défaut pour Abidjan
            return cls(
                north=5.4,
                south=5.2,
                east=-3.9,
                west=-4.1,
                center=CoordinatesResponse(latitude=5.3, longitude=-4.0)
            )
        
        lats = [c.latitude for c in coords_list]
        lngs = [c.longitude for c in coords_list]
        
        north = max(lats)
        south = min(lats)
        east = max(lngs)
        west = min(lngs)
        
        # Ajouter une marge de 10%
        lat_margin = (north - south) * 0.1
        lng_margin = (east - west) * 0.1
        
        return cls(
            north=north + lat_margin,
            south=south - lat_margin,
            east=east + lng_margin,
            west=west - lng_margin,
            center=CoordinatesResponse(
                latitude=(north + south) / 2,
                longitude=(east + west) / 2
            )
        )


class CitySearchResponse(BaseModel):
    """Schema de réponse pour la recherche de villes"""
    cities: List[str]
    coordinates: List[CoordinatesResponse]
    total_found: int


class TripMapDataResponse(BaseModel):
    """Schema pour afficher un trajet sur une carte"""
    trip_id: int
    departure_marker: CoordinatesResponse
    arrival_marker: CoordinatesResponse
    route_polyline: List[Tuple[float, float]]
    pickup_markers: Optional[List[CoordinatesResponse]] = None
    dropoff_markers: Optional[List[CoordinatesResponse]] = None
    map_bounds: MapBoundsResponse
    
    class Config:
        schema_extra = {
            "example": {
                "trip_id": 1,
                "departure_marker": {"latitude": 5.3472, "longitude": -4.0243},
                "arrival_marker": {"latitude": 5.3200, "longitude": -4.0100},
                "route_polyline": [[5.3472, -4.0243], [5.3350, -4.0180], [5.3200, -4.0100]],
                "map_bounds": {
                    "north": 5.36,
                    "south": 5.31,
                    "east": -4.00,
                    "west": -4.03,
                    "center": {"latitude": 5.335, "longitude": -4.015}
                }
            }
        }


class GeolocationValidationResponse(BaseModel):
    """Schema de validation de géolocalisation"""
    is_valid: bool
    is_in_ivory_coast: bool
    nearest_city: Optional[str] = None
    distance_to_center_km: Optional[float] = None
    message: str
