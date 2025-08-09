"""
Service de gestion des réservations
Logique métier pour la réservation, confirmation et gestion des trajets
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from fastapi import HTTPException, status
import math

from src.models.reservation import Reservation, ReservationStatus, PaymentStatus, PaymentMethod
from src.models.trip import Trip, TripStatus
from src.models.user import User
from src.services.trip import TripService


class ReservationService:
    """Service de gestion des réservations"""

    @staticmethod
    def create_reservation(db: Session, reservation_data: dict, passenger: User, trip_id: int) -> Reservation:
        """Crée une nouvelle réservation"""
        
        # Récupérer le trajet
        trip = TripService.get_trip_by_id(db, trip_id)
        
        # Vérifications préliminaires
        if not passenger.is_phone_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous devez vérifier votre téléphone pour réserver un trajet"
            )
        
        if trip.driver_id == passenger.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vous ne pouvez pas réserver votre propre trajet"
            )
        
        # Vérification manuelle au lieu d'utiliser les propriétés
        now = datetime.now(timezone.utc)  # Utiliser UTC pour comparer
        if (trip.status != TripStatus.ACTIVE or 
            trip.available_seats <= 0 or 
            trip.departure_datetime <= now):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ce trajet ne peut pas être réservé (complet, expiré ou annulé)"
            )
        
        # Vérifier la disponibilité des places
        seats_requested = reservation_data.get("number_of_seats", 1)
        if trip.available_seats < seats_requested:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Seulement {trip.available_seats} place(s) disponible(s)"
            )
        
        # Vérifier qu'il n'y a pas déjà une réservation active
        existing_reservation = db.query(Reservation).filter(
            Reservation.trip_id == trip_id,
            Reservation.passenger_id == passenger.id,
            Reservation.status.in_([
                ReservationStatus.PENDING,
                ReservationStatus.CONFIRMED,
                ReservationStatus.PAID,
                ReservationStatus.STARTED
            ])
        ).first()
        
        if existing_reservation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vous avez déjà une réservation active pour ce trajet"
            )
        
        # Calculer le prix total
        total_price = trip.price_per_seat * seats_requested
        platform_fee = total_price * 0.05  # 5% de commission (exemple)
        
        # Créer la réservation
        new_reservation = Reservation(
            trip_id=trip_id,
            passenger_id=passenger.id,
            number_of_seats=seats_requested,
            pickup_address=reservation_data.get("pickup_address"),
            pickup_latitude=reservation_data.get("pickup_latitude"),
            pickup_longitude=reservation_data.get("pickup_longitude"),
            dropoff_address=reservation_data.get("dropoff_address"),
            dropoff_latitude=reservation_data.get("dropoff_latitude"),
            dropoff_longitude=reservation_data.get("dropoff_longitude"),
            total_price=total_price,
            price_per_seat=trip.price_per_seat,
            platform_fee=platform_fee,
            payment_method=reservation_data.get("payment_method", PaymentMethod.CASH),
            payment_status=PaymentStatus.PENDING,
            passenger_phone=passenger.phone,
            special_requests=reservation_data.get("special_requests"),
            status=ReservationStatus.PENDING
        )
        
        db.add(new_reservation)
        
        # Réserver les places temporairement (en attente de confirmation)
        # Note: On ne décrémente pas encore available_seats car c'est en attente
        
        db.commit()
        db.refresh(new_reservation)
        
        # TODO: Envoyer notification au conducteur
        
        return new_reservation

    @staticmethod
    def get_reservation_by_id(db: Session, reservation_id: int, current_user: User) -> Reservation:
        """Récupère une réservation par son ID"""
        reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
        
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Réservation non trouvée"
            )
        
        # Vérifier les permissions
        if (reservation.passenger_id != current_user.id and 
            reservation.trip.driver_id != current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé à cette réservation"
            )
        
        return reservation

    @staticmethod
    def confirm_reservation(db: Session, reservation_id: int, conductor: User, accept: bool, message: str = None) -> Reservation:
        """Confirme ou refuse une réservation (conducteur)"""
        reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
        
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Réservation non trouvée"
            )
        
        # Vérifier que c'est bien le conducteur du trajet
        if reservation.trip.driver_id != conductor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seul le conducteur du trajet peut confirmer cette réservation"
            )
        
        # Vérifier que la réservation est en attente
        if reservation.status != ReservationStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cette réservation ne peut plus être modifiée"
            )
        
        if accept:
            # Vérifier encore la disponibilité des places
            if reservation.trip.available_seats < reservation.number_of_seats:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Plus assez de places disponibles"
                )
            
            # Confirmer la réservation
            reservation.status = ReservationStatus.CONFIRMED
            reservation.confirmed_at = datetime.now(timezone.utc)
            
            # Décrémenter les places disponibles
            reservation.trip.available_seats -= reservation.number_of_seats
            
            # Marquer le trajet comme complet si plus de places
            if reservation.trip.available_seats == 0:
                reservation.trip.status = TripStatus.FULL
                
        else:
            # Refuser la réservation
            reservation.status = ReservationStatus.CANCELLED_BY_DRIVER
            reservation.cancelled_at = datetime.now(timezone.utc)
            reservation.cancellation_reason = message or "Refusé par le conducteur"
        
        if message:
            reservation.driver_notes = message
        
        db.commit()
        db.refresh(reservation)
        
        # TODO: Envoyer notification au passager
        
        return reservation

    @staticmethod
    def cancel_reservation(db: Session, reservation_id: int, user: User, reason: str) -> Reservation:
        """Annule une réservation"""
        reservation = ReservationService.get_reservation_by_id(db, reservation_id, user)
        
        # Vérifier que la réservation peut être annulée
        if not reservation.can_be_cancelled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cette réservation ne peut plus être annulée"
            )
        
        # Vérifier qui annule
        if reservation.passenger_id == user.id:
            reservation.status = ReservationStatus.CANCELLED_BY_PASSENGER
        elif reservation.trip.driver_id == user.id:
            reservation.status = ReservationStatus.CANCELLED_BY_DRIVER
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous ne pouvez pas annuler cette réservation"
            )
        
        reservation.cancelled_at = datetime.now(timezone.utc)
        reservation.cancellation_reason = reason
        
        # Libérer les places si la réservation était confirmée
        if reservation.status in [ReservationStatus.CONFIRMED, ReservationStatus.PAID]:
            reservation.trip.available_seats += reservation.number_of_seats
            
            # Réactiver le trajet si il était complet
            if reservation.trip.status == TripStatus.FULL:
                reservation.trip.status = TripStatus.ACTIVE
        
        db.commit()
        db.refresh(reservation)
        
        # TODO: Gérer les remboursements si nécessaire
        # TODO: Envoyer notifications
        
        return reservation

    @staticmethod
    def get_my_reservations(db: Session, passenger: User) -> Dict[str, List[Reservation]]:
        """Récupère toutes les réservations d'un passager"""
        
        # Réservations actives
        active_reservations = db.query(Reservation).filter(
            Reservation.passenger_id == passenger.id,
            Reservation.status.in_([
                ReservationStatus.PENDING,
                ReservationStatus.CONFIRMED,
                ReservationStatus.PAID,
                ReservationStatus.STARTED
            ])
        ).order_by(desc(Reservation.created_at)).all()
        
        # Réservations terminées
        completed_reservations = db.query(Reservation).filter(
            Reservation.passenger_id == passenger.id,
            Reservation.status == ReservationStatus.COMPLETED
        ).order_by(desc(Reservation.actual_dropoff_time)).limit(10).all()
        
        # Réservations annulées
        cancelled_reservations = db.query(Reservation).filter(
            Reservation.passenger_id == passenger.id,
            Reservation.status.in_([
                ReservationStatus.CANCELLED_BY_PASSENGER,
                ReservationStatus.CANCELLED_BY_DRIVER,
                ReservationStatus.NO_SHOW
            ])
        ).order_by(desc(Reservation.cancelled_at)).limit(5).all()
        
        return {
            "active_reservations": active_reservations,
            "completed_reservations": completed_reservations,
            "cancelled_reservations": cancelled_reservations
        }

    @staticmethod
    def get_trip_reservations(db: Session, trip_id: int, conductor: User) -> Dict[str, List[Reservation]]:
        """Récupère toutes les réservations d'un trajet (conducteur)"""
        trip = TripService.get_trip_by_id(db, trip_id)
        
        if trip.driver_id != conductor.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès refusé"
            )
        
        # Réservations en attente
        pending_reservations = db.query(Reservation).filter(
            Reservation.trip_id == trip_id,
            Reservation.status == ReservationStatus.PENDING
        ).order_by(asc(Reservation.created_at)).all()
        
        # Réservations confirmées
        confirmed_reservations = db.query(Reservation).filter(
            Reservation.trip_id == trip_id,
            Reservation.status.in_([
                ReservationStatus.CONFIRMED,
                ReservationStatus.PAID,
                ReservationStatus.STARTED
            ])
        ).order_by(asc(Reservation.confirmed_at)).all()
        
        # Réservations annulées
        cancelled_reservations = db.query(Reservation).filter(
            Reservation.trip_id == trip_id,
            Reservation.status.in_([
                ReservationStatus.CANCELLED_BY_PASSENGER,
                ReservationStatus.CANCELLED_BY_DRIVER,
                ReservationStatus.NO_SHOW
            ])
        ).order_by(desc(Reservation.cancelled_at)).all()
        
        return {
            "pending_reservations": pending_reservations,
            "confirmed_reservations": confirmed_reservations,
            "cancelled_reservations": cancelled_reservations
        }

    @staticmethod
    def mark_reservation_as_started(db: Session, reservation_id: int, user: User) -> Reservation:
        """Marque une réservation comme commencée"""
        reservation = ReservationService.get_reservation_by_id(db, reservation_id, user)
        
        if reservation.status != ReservationStatus.CONFIRMED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La réservation doit être confirmée pour être démarrée"
            )
        
        reservation.status = ReservationStatus.STARTED
        reservation.actual_pickup_time = datetime.now(timezone.utc)
        
        db.commit()
        
        return reservation

    @staticmethod
    def mark_reservation_as_completed(db: Session, reservation_id: int, user: User) -> Reservation:
        """Marque une réservation comme terminée"""
        reservation = ReservationService.get_reservation_by_id(db, reservation_id, user)
        
        if reservation.status != ReservationStatus.STARTED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La réservation doit être en cours pour être terminée"
            )
        
        reservation.status = ReservationStatus.COMPLETED
        reservation.actual_dropoff_time = datetime.now(timezone.utc)
        
        # Mettre à jour les statistiques du passager
        passenger = reservation.passenger
        passenger.trips_as_passenger += 1
        
        db.commit()
        
        return reservation

    @staticmethod
    def rate_trip(db: Session, reservation_id: int, user: User, rating: int, comment: str = None) -> Reservation:
        """Noter un trajet après completion"""
        reservation = ReservationService.get_reservation_by_id(db, reservation_id, user)
        
        if not reservation.can_be_rated:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cette réservation ne peut pas être notée"
            )
        
        if reservation.passenger_id == user.id:
            # Le passager note le conducteur
            reservation.driver_rating = rating
            reservation.passenger_comment = comment
            
            # Mettre à jour la note moyenne du conducteur
            driver = reservation.trip.driver
            driver.update_rating(rating)
            
        elif reservation.trip.driver_id == user.id:
            # Le conducteur note le passager
            reservation.passenger_rating = rating
            reservation.driver_comment = comment
            
            # Mettre à jour la note moyenne du passager
            passenger = reservation.passenger
            passenger.update_rating(rating)
        
        db.commit()
        
        return reservation


# Instance globale du service
reservation_service = ReservationService()