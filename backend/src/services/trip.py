"""
Service de gestion des trajets
Logique métier pour la création, modification et recherche de trajets
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from fastapi import HTTPException, status
import math

from src.models.trip import Trip, TripStatus, TripType
from src.models.user import User, UserType
from src.schemas.trip import TripSearchFilters


class TripService:
    """Service de gestion des trajets"""

    @staticmethod
    def create_trip(db: Session, trip_data: dict, driver: User) -> Trip:
        """Crée un nouveau trajet"""
        
        # Vérifications préliminaires
        if not driver.can_create_trip():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous devez être un conducteur vérifié pour créer un trajet"
            )
        
        # Vérifier que le conducteur n'a pas trop de trajets actifs
        active_trips_count = db.query(Trip).filter(
            Trip.driver_id == driver.id,
            Trip.status.in_([TripStatus.ACTIVE, TripStatus.FULL])
        ).count()
        
        if active_trips_count >= 5:  # Limite à 5 trajets actifs
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vous avez atteint la limite de trajets actifs (5 maximum)"
            )
        
        # Créer le trajet
        new_trip = Trip(
            driver_id=driver.id,
            departure_address=trip_data["departure_address"],
            departure_city=trip_data["departure_city"],
            departure_latitude=trip_data.get("departure_latitude"),
            departure_longitude=trip_data.get("departure_longitude"),
            arrival_address=trip_data["arrival_address"],
            arrival_city=trip_data["arrival_city"],
            arrival_latitude=trip_data.get("arrival_latitude"),
            arrival_longitude=trip_data.get("arrival_longitude"),
            departure_datetime=trip_data["departure_datetime"],
            estimated_duration_minutes=trip_data.get("estimated_duration_minutes"),
            total_seats=trip_data["available_seats"],
            available_seats=trip_data["available_seats"],
            price_per_seat=trip_data["price_per_seat"],
            total_distance_km=trip_data.get("total_distance_km"),
            trip_type=trip_data["trip_type"],
            accepts_pets=trip_data["accepts_pets"],
            accepts_smoking=trip_data["accepts_smoking"],
            accepts_food=trip_data["accepts_food"],
            luggage_allowed=trip_data["luggage_allowed"],
            max_detour_km=trip_data["max_detour_km"],
            description=trip_data.get("description"),
            special_instructions=trip_data.get("special_instructions"),
            is_recurring=trip_data["is_recurring"],
            recurring_days=trip_data.get("recurring_days"),
            recurring_end_date=trip_data.get("recurring_end_date"),
            status=TripStatus.ACTIVE
        )
        
        db.add(new_trip)
        db.commit()
        db.refresh(new_trip)
        
        # Mettre à jour les statistiques du conducteur
        driver.trips_as_driver += 1
        db.commit()
        
        return new_trip

    @staticmethod
    def get_trip_by_id(db: Session, trip_id: int, current_user: Optional[User] = None) -> Trip:
        """Récupère un trajet par son ID"""
        trip = db.query(Trip).filter(Trip.id == trip_id).first()
        
        if not trip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trajet non trouvé"
            )
        
        return trip

    @staticmethod
    def update_trip(db: Session, trip_id: int, update_data: dict, driver: User) -> Trip:
        """Met à jour un trajet"""
        trip = TripService.get_trip_by_id(db, trip_id)
        
        # Vérifier que c'est bien le conducteur du trajet
        if trip.driver_id != driver.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous ne pouvez modifier que vos propres trajets"
            )
        
        # Vérifier que le trajet peut être modifié
        if not trip.can_be_modified_by(driver.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce trajet ne peut plus être modifié"
            )
        
        # Vérifier qu'il reste assez de temps (2h minimum)
        time_until_departure = trip.departure_datetime - datetime.now()
        if time_until_departure < timedelta(hours=2):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Impossible de modifier un trajet moins de 2h avant le départ"
            )
        
        # Mettre à jour les champs modifiables
        for field, value in update_data.items():
            if value is not None and hasattr(trip, field):
                setattr(trip, field, value)
        
        trip.updated_at = datetime.now()
        db.commit()
        db.refresh(trip)
        
        return trip

    @staticmethod
    def cancel_trip(db: Session, trip_id: int, driver: User, reason: str) -> Trip:
        """Annule un trajet"""
        trip = TripService.get_trip_by_id(db, trip_id)
        
        # Vérifier que c'est bien le conducteur du trajet
        if trip.driver_id != driver.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous ne pouvez annuler que vos propres trajets"
            )
        
        # Vérifier que le trajet peut être annulé
        if trip.status not in [TripStatus.ACTIVE, TripStatus.FULL]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce trajet ne peut pas être annulé"
            )
        
        # Annuler le trajet
        trip.status = TripStatus.CANCELLED
        trip.cancelled_at = datetime.now()
        trip.cancellation_reason = reason
        
        db.commit()
        
        # TODO: Notifier les passagers qui ont réservé
        # TODO: Gérer les remboursements
        
        return trip

    @staticmethod
    def search_trips(db: Session, filters: TripSearchFilters, current_user: Optional[User] = None) -> Tuple[List[Trip], int]:
        """Recherche les trajets selon les filtres"""
        query = db.query(Trip).filter(Trip.status == TripStatus.ACTIVE)
        
        # Filtres de base
        if filters.departure_city:
            query = query.filter(Trip.departure_city.ilike(f"%{filters.departure_city}%"))
        
        if filters.arrival_city:
            query = query.filter(Trip.arrival_city.ilike(f"%{filters.arrival_city}%"))
        
        if filters.departure_date:
            # Recherche pour toute la journée
            start_date = filters.departure_date.replace(hour=0, minute=0, second=0)
            end_date = start_date + timedelta(days=1)
            query = query.filter(
                and_(
                    Trip.departure_datetime >= start_date,
                    Trip.departure_datetime < end_date
                )
            )
        
        if filters.min_seats:
            query = query.filter(Trip.available_seats >= filters.min_seats)
        
        if filters.max_price:
            query = query.filter(Trip.price_per_seat <= filters.max_price)
        
        if filters.accepts_pets is not None:
            query = query.filter(Trip.accepts_pets == filters.accepts_pets)
        
        if filters.trip_type:
            query = query.filter(Trip.trip_type == filters.trip_type)
        
        # Filtre géographique (recherche par proximité)
        if filters.latitude and filters.longitude and filters.radius_km:
            # Calcul approximatif de distance (pour un filtre plus précis, utiliser PostGIS)
            lat_range = filters.radius_km / 111.0  # 1 degré ≈ 111 km
            lon_range = lat_range / math.cos(math.radians(filters.latitude))
            
            query = query.filter(
                and_(
                    Trip.departure_latitude.between(
                        filters.latitude - lat_range,
                        filters.latitude + lat_range
                    ),
                    Trip.departure_longitude.between(
                        filters.longitude - lon_range,
                        filters.longitude + lon_range
                    )
                )
            )
        
        # Exclure les trajets de l'utilisateur connecté (s'il est conducteur)
        if current_user and current_user.is_driver:
            query = query.filter(Trip.driver_id != current_user.id)
        
        # Compter le total
        total_count = query.count()
        
        # Tri par défaut : date de départ croissante
        query = query.order_by(asc(Trip.departure_datetime))
        
        # Pagination
        offset = (filters.page - 1) * filters.per_page
        trips = query.offset(offset).limit(filters.per_page).all()
        
        return trips, total_count

    @staticmethod
    def get_my_trips(db: Session, driver: User) -> Dict[str, List[Trip]]:
        """Récupère tous les trajets d'un conducteur"""
        if not driver.is_driver:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès réservé aux conducteurs"
            )
        
        # Trajets actifs
        active_trips = db.query(Trip).filter(
            Trip.driver_id == driver.id,
            Trip.status.in_([TripStatus.ACTIVE, TripStatus.FULL]),
            Trip.departure_datetime > datetime.now()
        ).order_by(asc(Trip.departure_datetime)).all()
        
        # Trajets terminés
        completed_trips = db.query(Trip).filter(
            Trip.driver_id == driver.id,
            Trip.status == TripStatus.COMPLETED
        ).order_by(desc(Trip.departure_datetime)).limit(10).all()
        
        # Trajets annulés
        cancelled_trips = db.query(Trip).filter(
            Trip.driver_id == driver.id,
            Trip.status == TripStatus.CANCELLED
        ).order_by(desc(Trip.cancelled_at)).limit(5).all()
        
        return {
            "active_trips": active_trips,
            "completed_trips": completed_trips,
            "cancelled_trips": cancelled_trips
        }

    @staticmethod
    def get_trip_stats(db: Session, trip_id: int, driver: User) -> Dict[str, Any]:
        """Récupère les statistiques d'un trajet"""
        trip = TripService.get_trip_by_id(db, trip_id)
        
        if trip.driver_id != driver.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé"
            )
        
        # TODO: Ajouter les statistiques des réservations
        # Pour l'instant, calcul basique
        reservations_count = trip.total_seats - trip.available_seats
        
        return {
            "trip_id": trip.id,
            "reservations_count": reservations_count,
            "confirmed_reservations": reservations_count,  # Simplifié pour le MVP
            "total_earnings": trip.total_earnings,
            "platform_commission": trip.platform_commission,
            "driver_earnings": trip.driver_earnings
        }

    @staticmethod
    def mark_trip_as_started(db: Session, trip_id: int, driver: User) -> Trip:
        """Marque un trajet comme commencé"""
        trip = TripService.get_trip_by_id(db, trip_id)
        
        if trip.driver_id != driver.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé"
            )
        
        if trip.status not in [TripStatus.ACTIVE, TripStatus.FULL]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce trajet ne peut pas être démarré"
            )
        
        trip.status = TripStatus.STARTED
        trip.actual_departure_time = datetime.now()
        
        db.commit()
        
        return trip

    @staticmethod
    def mark_trip_as_completed(db: Session, trip_id: int, driver: User) -> Trip:
        """Marque un trajet comme terminé"""
        trip = TripService.get_trip_by_id(db, trip_id)
        
        if trip.driver_id != driver.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé"
            )
        
        if trip.status != TripStatus.STARTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Le trajet doit être en cours pour être terminé"
            )
        
        trip.status = TripStatus.COMPLETED
        trip.actual_arrival_time = datetime.now()
        
        # Calculer les gains finaux
        trip.calculate_earnings()
        
        db.commit()
        
        return trip


# Instance globale du service
trip_service = TripService()
