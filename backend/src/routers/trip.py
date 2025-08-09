"""
Routes pour la gestion des trajets
Endpoints CRUD pour les trajets de covoiturage
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional, List
import math

from src.database import get_db
from src.schemas.trip import (
    TripCreateRequest, TripUpdateRequest, TripSearchFilters,
    TripResponse, TripListResponse, TripCreateResponse,
    TripStatsResponse, MyTripsResponse, TripCancelRequest
)
from src.schemas.auth import MessageResponse
from src.services.trip import TripService
from src.models.user import User
from src.routers.auth import get_current_user, get_current_driver

# Création du router
router = APIRouter(prefix="/api/v1/trips", tags=["Trajets"])


@router.post("/", response_model=TripCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_trip(
    trip_data: TripCreateRequest,
    db: Session = Depends(get_db),
    current_driver: User = Depends(get_current_driver)
):
    """
    Créer un nouveau trajet (conducteurs uniquement)
    
    - **departure_address**: Adresse de départ complète
    - **departure_city**: Ville de départ
    - **arrival_address**: Adresse d'arrivée complète  
    - **arrival_city**: Ville d'arrivée
    - **departure_datetime**: Date et heure de départ
    - **available_seats**: Nombre de places disponibles (1-8)
    - **price_per_seat**: Prix par place en FCFA (100-50000)
    - **trip_type**: Type de trajet (ONE_TIME, DAILY, WEEKLY)
    - **accepts_pets**: Accepte les animaux
    - **accepts_smoking**: Accepte les fumeurs
    - **description**: Description optionnelle
    
    Nécessite d'être un conducteur vérifié.
    """
    try:
        # Convertir en dictionnaire
        trip_dict = trip_data.dict()
        
        # Créer le trajet
        new_trip = TripService.create_trip(db, trip_dict, current_driver)
        
        return TripCreateResponse(
            message=f"Trajet créé avec succès ! {new_trip.route_summary}",
            trip=TripResponse.from_orm(new_trip)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création du trajet: {str(e)}"
        )


@router.get("/", response_model=TripListResponse)
async def search_trips(
    departure_city: Optional[str] = Query(None, description="Ville de départ"),
    arrival_city: Optional[str] = Query(None, description="Ville d'arrivée"),
    departure_date: Optional[str] = Query(None, description="Date de départ (YYYY-MM-DD)"),
    min_seats: Optional[int] = Query(None, description="Nombre minimum de places", ge=1, le=8),
    max_price: Optional[float] = Query(None, description="Prix maximum par place", ge=100),
    accepts_pets: Optional[bool] = Query(None, description="Accepte les animaux"),
    latitude: Optional[float] = Query(None, description="Latitude pour recherche géographique"),
    longitude: Optional[float] = Query(None, description="Longitude pour recherche géographique"),
    radius_km: Optional[float] = Query(10, description="Rayon de recherche en km", ge=1, le=100),
    page: int = Query(1, description="Numéro de page", ge=1),
    per_page: int = Query(20, description="Trajets par page", ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Rechercher des trajets
    
    Permet de filtrer les trajets selon différents critères :
    - Villes de départ et d'arrivée
    - Date de départ
    - Nombre de places minimum
    - Prix maximum
    - Préférences (animaux acceptés)
    - Localisation géographique
    
    Retourne une liste paginée des trajets correspondants.
    """
    try:
        # Créer les filtres
        filters = TripSearchFilters(
            departure_city=departure_city,
            arrival_city=arrival_city,
            departure_date=departure_date,
            min_seats=min_seats,
            max_price=max_price,
            accepts_pets=accepts_pets,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
            page=page,
            per_page=per_page
        )
        
        # Rechercher les trajets
        trips, total_count = TripService.search_trips(db, filters, current_user)
        
        # Calculs de pagination
        total_pages = math.ceil(total_count / per_page)
        has_next = page < total_pages
        has_prev = page > 1
        
        return TripListResponse(
            trips=[TripResponse.from_orm(trip) for trip in trips],
            total_count=total_count,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche: {str(e)}"
        )


@router.get("/my", response_model=MyTripsResponse)
async def get_my_trips(
    db: Session = Depends(get_db),
    current_driver: User = Depends(get_current_driver)
):
    """
    Récupérer mes trajets (conducteur uniquement)
    
    Retourne tous les trajets du conducteur connecté :
    - Trajets actifs (en cours de réservation)
    - Trajets terminés (historique)
    - Trajets annulés
    
    Inclut des statistiques globales.
    """
    try:
        # Récupérer les trajets
        trips_data = TripService.get_my_trips(db, current_driver)
        
        # Calculer les statistiques
        total_trips = (
            len(trips_data["active_trips"]) + 
            len(trips_data["completed_trips"]) + 
            len(trips_data["cancelled_trips"])
        )
        
        total_earnings = sum(trip.driver_earnings for trip in trips_data["completed_trips"])
        
        # Calculer le nombre total de passagers transportés
        total_passengers = sum(
            (trip.total_seats - trip.available_seats) 
            for trip in trips_data["completed_trips"]
        )
        
        return MyTripsResponse(
            active_trips=[TripResponse.from_orm(trip) for trip in trips_data["active_trips"]],
            completed_trips=[TripResponse.from_orm(trip) for trip in trips_data["completed_trips"]],
            cancelled_trips=[TripResponse.from_orm(trip) for trip in trips_data["cancelled_trips"]],
            total_trips=total_trips,
            total_earnings=total_earnings,
            total_passengers=total_passengers,
            average_rating=current_driver.rating_average
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


@router.get("/{trip_id}", response_model=TripResponse)
async def get_trip_details(
    trip_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user)
):
    """
    Récupérer les détails d'un trajet
    
    - **trip_id**: ID du trajet
    
    Accessible à tous les utilisateurs connectés.
    Affiche toutes les informations du trajet et du conducteur.
    """
    try:
        trip = TripService.get_trip_by_id(db, trip_id, current_user)
        return TripResponse.from_orm(trip)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


@router.put("/{trip_id}", response_model=TripResponse)
async def update_trip(
    trip_id: int,
    update_data: TripUpdateRequest,
    db: Session = Depends(get_db),
    current_driver: User = Depends(get_current_driver)
):
    """
    Modifier un trajet (conducteur propriétaire uniquement)
    
    - **trip_id**: ID du trajet à modifier
    
    Champs modifiables :
    - Date et heure de départ
    - Nombre de places disponibles
    - Prix par place
    - Préférences (animaux, fumeurs, etc.)
    - Description et instructions
    
    Restrictions :
    - Impossible de modifier moins de 2h avant le départ
    - Seul le conducteur propriétaire peut modifier
    """
    try:
        # Convertir en dictionnaire (exclure les None)
        update_dict = update_data.dict(exclude_unset=True)
        
        # Mettre à jour le trajet
        updated_trip = TripService.update_trip(db, trip_id, update_dict, current_driver)
        
        return TripResponse.from_orm(updated_trip)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la modification: {str(e)}"
        )


@router.delete("/{trip_id}", response_model=MessageResponse)
async def cancel_trip(
    trip_id: int,
    cancel_data: TripCancelRequest,
    db: Session = Depends(get_db),
    current_driver: User = Depends(get_current_driver)
):
    """
    Annuler un trajet (conducteur propriétaire uniquement)
    
    - **trip_id**: ID du trajet à annuler
    - **reason**: Raison de l'annulation (obligatoire)
    - **notify_passengers**: Notifier les passagers (par défaut: true)
    
    Les passagers ayant réservé seront automatiquement notifiés.
    Les remboursements seront traités selon la politique d'annulation.
    """
    try:
        # Annuler le trajet
        cancelled_trip = TripService.cancel_trip(
            db, trip_id, current_driver, cancel_data.reason
        )
        
        return MessageResponse(
            message=f"Trajet {cancelled_trip.route_summary} annulé avec succès. "
                   f"Les passagers ont été notifiés.",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'annulation: {str(e)}"
        )


@router.get("/{trip_id}/stats", response_model=TripStatsResponse)
async def get_trip_stats(
    trip_id: int,
    db: Session = Depends(get_db),
    current_driver: User = Depends(get_current_driver)
):
    """
    Récupérer les statistiques d'un trajet (conducteur propriétaire uniquement)
    
    - **trip_id**: ID du trajet
    
    Retourne :
    - Nombre de réservations
    - Gains estimés et réels
    - Commission de la plateforme
    - Détails financiers
    """
    try:
        stats = TripService.get_trip_stats(db, trip_id, current_driver)
        return TripStatsResponse(**stats)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des statistiques: {str(e)}"
        )


@router.post("/{trip_id}/start", response_model=MessageResponse)
async def start_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_driver: User = Depends(get_current_driver)
):
    """
    Démarrer un trajet (conducteur propriétaire uniquement)
    
    - **trip_id**: ID du trajet à démarrer
    
    Marque le trajet comme "en cours" et enregistre l'heure de départ réelle.
    Les passagers seront notifiés que le trajet a commencé.
    """
    try:
        started_trip = TripService.mark_trip_as_started(db, trip_id, current_driver)
        
        return MessageResponse(
            message=f"Trajet {started_trip.route_summary} démarré avec succès ! "
                   f"Bon voyage et conduisez prudemment.",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du démarrage: {str(e)}"
        )


@router.post("/{trip_id}/complete", response_model=MessageResponse)
async def complete_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    current_driver: User = Depends(get_current_driver)
):
    """
    Terminer un trajet (conducteur propriétaire uniquement)
    
    - **trip_id**: ID du trajet à terminer
    
    Marque le trajet comme "terminé" et finalise les gains.
    Les passagers pourront alors évaluer le conducteur.
    """
    try:
        completed_trip = TripService.mark_trip_as_completed(db, trip_id, current_driver)
        
        return MessageResponse(
            message=f"Trajet {completed_trip.route_summary} terminé avec succès ! "
                   f"Vos gains: {completed_trip.driver_earnings} FCFA. "
                   f"Merci d'avoir utilisé notre plateforme.",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la finalisation: {str(e)}"
        )


# Endpoints de recherche avancée

@router.get("/search/popular-routes", response_model=List[dict])
async def get_popular_routes(
    db: Session = Depends(get_db),
    limit: int = Query(10, description="Nombre de routes à retourner", ge=1, le=50)
):
    """
    Récupérer les routes populaires
    
    Retourne les trajets les plus fréquents basés sur l'historique.
    Utile pour suggérer des destinations populaires.
    """
    try:
        # Requête pour les routes populaires (simplifié pour le MVP)
        popular_routes = db.execute("""
            SELECT 
                departure_city,
                arrival_city,
                COUNT(*) as trip_count,
                AVG(price_per_seat) as avg_price
            FROM trips 
            WHERE status != 'CANCELLED'
            GROUP BY departure_city, arrival_city
            ORDER BY trip_count DESC
            LIMIT :limit
        """, {"limit": limit}).fetchall()
        
        return [
            {
                "departure_city": route.departure_city,
                "arrival_city": route.arrival_city,
                "trip_count": route.trip_count,
                "avg_price": float(route.avg_price) if route.avg_price else 0,
                "route": f"{route.departure_city} → {route.arrival_city}"
            }
            for route in popular_routes
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )