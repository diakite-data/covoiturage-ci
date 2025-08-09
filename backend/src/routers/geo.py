"""
Routes pour les services géographiques et cartographiques
Géocodage, calculs de route, recherche par proximité
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from src.database import get_db
from src.schemas.geo import (
    GeocodingRequest, RouteCalculationRequest, NearbySearchRequest,
    GeocodingResponse, RouteResponse, NearbyPointsResponse,
    DistanceCalculationResponse, CoordinatesRequest
)
from src.services.geo import geo_service, Coordinates
from src.models.user import User
from src.routers.auth import get_current_user

# Création du router
router = APIRouter(prefix="/api/v1/geo", tags=["Géolocalisation & Cartes"])


@router.post("/geocode", response_model=GeocodingResponse)
async def geocode_address(request: GeocodingRequest):
    """Géocoder une adresse en coordonnées GPS"""
    try:
        result = geo_service.geocode_address(request.address, request.city)
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Adresse non trouvée : {request.address}"
            )
        
        return GeocodingResponse.from_geocoding_result(result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du géocodage : {str(e)}"
        )


@router.post("/calculate-route", response_model=RouteResponse)
async def calculate_route(request: RouteCalculationRequest):
    """Calculer un itinéraire entre deux points"""
    try:
        start = Coordinates(request.start_latitude, request.start_longitude)
        end = Coordinates(request.end_latitude, request.end_longitude)
        
        route = geo_service.calculate_route(start, end)
        
        if not route:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Impossible de calculer l'itinéraire"
            )
        
        estimated_price = geo_service.estimate_trip_price(route.distance_km)
        
        return RouteResponse.from_route_info(route, estimated_price)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du calcul d'itinéraire : {str(e)}"
        )


@router.get("/cities/search")
async def search_cities(
    q: str = Query(..., min_length=2, description="Terme de recherche"),
    limit: int = Query(10, ge=1, le=50, description="Nombre max de résultats")
):
    """Rechercher des villes en Côte d'Ivoire"""
    try:
        cities = [
            "Abidjan", "Bouaké", "Yamoussoukro", "Korhogo", "San-Pédro",
            "Daloa", "Man", "Gagnoa", "Divo", "Anyama", "Abengourou",
            "Agboville", "Grand-Bassam", "Sassandra", "Bondoukou",
            "Cocody", "Yopougon", "Marcory", "Koumassi", "Bingerville",
            "Plateau", "Adjamé", "Treichville", "Port-Bouët", "Abobo"
        ]
        
        filtered_cities = [
            city for city in cities 
            if q.lower() in city.lower()
        ][:limit]
        
        return {
            "cities": filtered_cities,
            "total_found": len(filtered_cities),
            "query": q
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche : {str(e)}"
        )


@router.get("/distance")
async def calculate_distance(
    lat1: float = Query(..., ge=-90, le=90),
    lng1: float = Query(..., ge=-180, le=180),
    lat2: float = Query(..., ge=-90, le=90),
    lng2: float = Query(..., ge=-180, le=180)
):
    """Calculer la distance entre deux points"""
    try:
        coord1 = Coordinates(lat1, lng1)
        coord2 = Coordinates(lat2, lng2)
        
        distance = geo_service.calculate_distance(coord1, coord2)
        estimated_duration = int(distance * 1.5)
        estimated_price = geo_service.estimate_trip_price(distance)
        
        return {
            "start": {"latitude": lat1, "longitude": lng1},
            "end": {"latitude": lat2, "longitude": lng2},
            "distance_km": distance,
            "estimated_duration_minutes": estimated_duration,
            "estimated_price": estimated_price
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du calcul : {str(e)}"
        )


@router.get("/ivory-coast/bounds")
async def get_ivory_coast_bounds():
    """Récupérer les limites géographiques de la Côte d'Ivoire"""
    return {
        "country": "Côte d'Ivoire",
        "bounds": {
            "north": 10.7,
            "south": 4.3,
            "east": -2.5,
            "west": -8.6
        },
        "center": {
            "latitude": 7.5,
            "longitude": -5.5
        },
        "default_zoom": 7,
        "major_cities": [
            {"name": "Abidjan", "lat": 5.3364, "lng": -4.0267},
            {"name": "Bouaké", "lat": 7.6927, "lng": -5.0298},
            {"name": "Yamoussoukro", "lat": 6.8205, "lng": -5.2893}
        ]
    }