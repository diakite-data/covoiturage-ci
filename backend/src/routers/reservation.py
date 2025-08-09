"""
Routes pour la gestion des réservations
Endpoints CRUD pour les réservations de trajets
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
import math

from src.database import get_db
from src.schemas.reservation import (
    ReservationCreateRequest, ReservationUpdateRequest, ReservationCancelRequest,
    ReservationConfirmRequest, RatingRequest, ReservationResponse,
    ReservationListResponse, ReservationCreateResponse, ReservationConfirmResponse,
    MyReservationsResponse, TripReservationsResponse, ReservationStatsResponse
)
from src.schemas.auth import MessageResponse
from src.services.reservation import ReservationService
from src.models.user import User
from src.routers.auth import get_current_user, get_current_verified_user, get_current_driver

# Création du router
router = APIRouter(prefix="/api/v1/reservations", tags=["Réservations"])


@router.post("/", response_model=ReservationCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_reservation(
    reservation_data: ReservationCreateRequest,
    db: Session = Depends(get_db),
    current_passenger: User = Depends(get_current_verified_user)
):
    """
    Réserver un trajet (passagers uniquement)
    
    - **trip_id**: ID du trajet à réserver
    - **number_of_seats**: Nombre de places (1-8)
    - **pickup_address**: Adresse de prise en charge (optionnel)
    - **dropoff_address**: Adresse de dépose (optionnel)
    - **special_requests**: Demandes spéciales (optionnel)
    - **payment_method**: Méthode de paiement (CASH, MOBILE_MONEY, CARD)
    
    Nécessite d'être un utilisateur vérifié (téléphone confirmé).
    """
    try:
        # Convertir en dictionnaire
        reservation_dict = reservation_data.dict()
        trip_id = reservation_dict.pop("trip_id")
        
        # Créer la réservation
        new_reservation = ReservationService.create_reservation(
            db, reservation_dict, current_passenger, trip_id
        )
        
        return ReservationCreateResponse(
            message=f"Réservation créée avec succès ! {new_reservation.number_of_seats} place(s) réservée(s).",
            reservation=ReservationResponse.from_orm(new_reservation)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la réservation: {str(e)}"
        )


@router.get("/my", response_model=MyReservationsResponse)
async def get_my_reservations(
    db: Session = Depends(get_db),
    current_passenger: User = Depends(get_current_verified_user)
):
    """
    Récupérer mes réservations (passager uniquement)
    
    Retourne toutes les réservations du passager connecté :
    - Réservations actives (en attente, confirmées, en cours)
    - Réservations terminées (historique)
    - Réservations annulées
    
    Inclut des statistiques globales.
    """
    try:
        # Récupérer les réservations
        reservations_data = ReservationService.get_my_reservations(db, current_passenger)
        
        # Calculer les statistiques
        total_reservations = (
            len(reservations_data["active_reservations"]) +
            len(reservations_data["completed_reservations"]) +
            len(reservations_data["cancelled_reservations"])
        )
        
        total_spent = sum(
            reservation.total_price 
            for reservation in reservations_data["completed_reservations"]
        )
        
        total_trips = len(reservations_data["completed_reservations"])
        
        # Calculer la note moyenne donnée
        ratings = [
            r.driver_rating for r in reservations_data["completed_reservations"]
            if r.driver_rating is not None
        ]
        average_rating_given = sum(ratings) / len(ratings) if ratings else 0.0
        
        return MyReservationsResponse(
            active_reservations=[
                ReservationResponse.from_orm(r) 
                for r in reservations_data["active_reservations"]
            ],
            completed_reservations=[
                ReservationResponse.from_orm(r) 
                for r in reservations_data["completed_reservations"]
            ],
            cancelled_reservations=[
                ReservationResponse.from_orm(r) 
                for r in reservations_data["cancelled_reservations"]
            ],
            total_reservations=total_reservations,
            total_spent=total_spent,
            total_trips=total_trips,
            average_rating_given=average_rating_given
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


@router.get("/{reservation_id}", response_model=ReservationResponse)
async def get_reservation_details(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Récupérer les détails d'une réservation
    
    - **reservation_id**: ID de la réservation
    
    Accessible au passager et au conducteur concernés.
    """
    try:
        reservation = ReservationService.get_reservation_by_id(db, reservation_id, current_user)
        return ReservationResponse.from_orm(reservation)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


@router.put("/{reservation_id}", response_model=ReservationResponse)
async def update_reservation(
    reservation_id: int,
    update_data: ReservationUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Modifier une réservation (passager uniquement)
    
    - **reservation_id**: ID de la réservation à modifier
    
    Champs modifiables :
    - Adresses de prise en charge et dépose
    - Demandes spéciales
    
    Restrictions :
    - Seul le passager peut modifier
    - Impossible de modifier une réservation confirmée
    """
    try:
        reservation = ReservationService.get_reservation_by_id(db, reservation_id, current_user)
        
        # Vérifier que c'est le passager
        if reservation.passenger_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seul le passager peut modifier cette réservation"
            )
        
        # Mettre à jour les champs modifiables
        update_dict = update_data.dict(exclude_unset=True)
        for field, value in update_dict.items():
            if hasattr(reservation, field):
                setattr(reservation, field, value)
        
        db.commit()
        db.refresh(reservation)
        
        return ReservationResponse.from_orm(reservation)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la modification: {str(e)}"
        )


@router.post("/{reservation_id}/confirm", response_model=ReservationConfirmResponse)
async def confirm_reservation(
    reservation_id: int,
    confirm_data: ReservationConfirmRequest,
    db: Session = Depends(get_db),
    current_driver: User = Depends(get_current_driver)
):
    """
    Confirmer ou refuser une réservation (conducteur uniquement)
    
    - **reservation_id**: ID de la réservation
    - **accept**: true pour accepter, false pour refuser
    - **message**: Message optionnel pour le passager
    
    Seul le conducteur du trajet peut confirmer/refuser.
    """
    try:
        confirmed_reservation = ReservationService.confirm_reservation(
            db, reservation_id, current_driver, 
            confirm_data.accept, confirm_data.message
        )
        
        if confirm_data.accept:
            message = "Réservation confirmée avec succès ! Le passager a été notifié."
        else:
            message = "Réservation refusée. Le passager a été notifié."
        
        return ReservationConfirmResponse(
            message=message,
            reservation=ReservationResponse.from_orm(confirmed_reservation)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la confirmation: {str(e)}"
        )


@router.delete("/{reservation_id}", response_model=MessageResponse)
async def cancel_reservation(
    reservation_id: int,
    cancel_data: ReservationCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Annuler une réservation
    
    - **reservation_id**: ID de la réservation à annuler
    - **reason**: Raison de l'annulation (obligatoire)
    
    Accessible au passager et au conducteur concernés.
    Les places sont automatiquement libérées.
    """
    try:
        cancelled_reservation = ReservationService.cancel_reservation(
            db, reservation_id, current_user, cancel_data.reason
        )
        
        if cancelled_reservation.passenger_id == current_user.id:
            message = "Votre réservation a été annulée avec succès. Le conducteur a été notifié."
        else:
            message = "Réservation annulée. Le passager a été notifié et sera remboursé si nécessaire."
        
        return MessageResponse(
            message=message,
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'annulation: {str(e)}"
        )


@router.post("/{reservation_id}/start", response_model=MessageResponse)
async def start_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Marquer une réservation comme commencée
    
    - **reservation_id**: ID de la réservation
    
    Accessible au passager et au conducteur.
    Marque le début effectif du trajet.
    """
    try:
        started_reservation = ReservationService.mark_reservation_as_started(
            db, reservation_id, current_user
        )
        
        return MessageResponse(
            message="Trajet commencé ! Bon voyage et arrivée en toute sécurité.",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du démarrage: {str(e)}"
        )


@router.post("/{reservation_id}/complete", response_model=MessageResponse)
async def complete_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Marquer une réservation comme terminée
    
    - **reservation_id**: ID de la réservation
    
    Accessible au passager et au conducteur.
    Finalise le trajet et permet les évaluations.
    """
    try:
        completed_reservation = ReservationService.mark_reservation_as_completed(
            db, reservation_id, current_user
        )
        
        return MessageResponse(
            message="Trajet terminé avec succès ! Vous pouvez maintenant évaluer votre expérience.",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la finalisation: {str(e)}"
        )


@router.post("/{reservation_id}/rate", response_model=MessageResponse)
async def rate_trip(
    reservation_id: int,
    rating_data: RatingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Noter un trajet après completion
    
    - **reservation_id**: ID de la réservation
    - **rating**: Note de 1 à 5
    - **comment**: Commentaire optionnel
    
    - Le passager note le conducteur
    - Le conducteur note le passager
    
    Uniquement possible après completion du trajet.
    """
    try:
        rated_reservation = ReservationService.rate_trip(
            db, reservation_id, current_user, 
            rating_data.rating, rating_data.comment
        )
        
        if rated_reservation.passenger_id == current_user.id:
            message = f"Merci d'avoir noté le conducteur ({rating_data.rating}/5) !"
        else:
            message = f"Merci d'avoir noté le passager ({rating_data.rating}/5) !"
        
        return MessageResponse(
            message=message,
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'évaluation: {str(e)}"
        )


# Endpoints pour les conducteurs

@router.get("/trip/{trip_id}", response_model=TripReservationsResponse)
async def get_trip_reservations(
    trip_id: int,
    db: Session = Depends(get_db),
    current_driver: User = Depends(get_current_driver)
):
    """
    Récupérer toutes les réservations d'un trajet (conducteur uniquement)
    
    - **trip_id**: ID du trajet
    
    Retourne :
    - Réservations en attente de confirmation
    - Réservations confirmées
    - Réservations annulées
    
    Accessible uniquement au conducteur propriétaire du trajet.
    """
    try:
        reservations_data = ReservationService.get_trip_reservations(db, trip_id, current_driver)
        
        # Calculer les statistiques
        total_reservations = (
            len(reservations_data["pending_reservations"]) +
            len(reservations_data["confirmed_reservations"]) +
            len(reservations_data["cancelled_reservations"])
        )
        
        confirmed_passengers = sum(
            r.number_of_seats for r in reservations_data["confirmed_reservations"]
        )
        
        total_earnings = sum(
            r.total_price for r in reservations_data["confirmed_reservations"]
        )
        
        return TripReservationsResponse(
            trip_id=trip_id,
            trip_summary=f"Trajet #{trip_id}",
            pending_reservations=[
                ReservationResponse.from_orm(r) 
                for r in reservations_data["pending_reservations"]
            ],
            confirmed_reservations=[
                ReservationResponse.from_orm(r) 
                for r in reservations_data["confirmed_reservations"]
            ],
            cancelled_reservations=[
                ReservationResponse.from_orm(r) 
                for r in reservations_data["cancelled_reservations"]
            ],
            total_reservations=total_reservations,
            confirmed_passengers=confirmed_passengers,
            total_earnings=total_earnings
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


@router.get("/stats", response_model=ReservationStatsResponse)
async def get_reservation_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Statistiques globales des réservations
    
    Pour les passagers : leurs statistiques de réservation
    Pour les conducteurs : statistiques de leurs trajets
    """
    try:
        if current_user.is_driver:
            # Stats pour conducteur (à implémenter)
            return ReservationStatsResponse(
                total_reservations=0,
                pending_count=0,
                confirmed_count=0,
                completed_count=0,
                cancelled_count=0,
                total_revenue=0.0,
                average_rating=current_user.rating_average
            )
        else:
            # Stats pour passager
            reservations_data = ReservationService.get_my_reservations(db, current_user)
            
            total_reservations = (
                len(reservations_data["active_reservations"]) +
                len(reservations_data["completed_reservations"]) +
                len(reservations_data["cancelled_reservations"])
            )
            
            return ReservationStatsResponse(
                total_reservations=total_reservations,
                pending_count=len([r for r in reservations_data["active_reservations"] if r.status.value == "pending"]),
                confirmed_count=len([r for r in reservations_data["active_reservations"] if r.status.value in ["confirmed", "paid"]]),
                completed_count=len(reservations_data["completed_reservations"]),
                cancelled_count=len(reservations_data["cancelled_reservations"]),
                total_revenue=0.0,  # Pour passager
                average_rating=current_user.rating_average
            )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des statistiques: {str(e)}"
        )
