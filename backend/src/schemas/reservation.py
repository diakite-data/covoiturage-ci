"""
Schemas Pydantic pour les réservations
Validation des données d'entrée et de sortie
"""
from pydantic import BaseModel, validator, Field
from typing import Optional, List
from datetime import datetime
from src.models.reservation import ReservationStatus, PaymentMethod, PaymentStatus


class ReservationCreateRequest(BaseModel):
    """Schema pour créer une nouvelle réservation"""
    trip_id: int = Field(..., gt=0)
    number_of_seats: int = Field(1, ge=1, le=8)
    pickup_address: Optional[str] = Field(None, max_length=255)
    pickup_latitude: Optional[float] = Field(None, ge=-90, le=90)
    pickup_longitude: Optional[float] = Field(None, ge=-180, le=180)
    dropoff_address: Optional[str] = Field(None, max_length=255)
    dropoff_latitude: Optional[float] = Field(None, ge=-90, le=90)
    dropoff_longitude: Optional[float] = Field(None, ge=-180, le=180)
    special_requests: Optional[str] = Field(None, max_length=500)
    payment_method: Optional[PaymentMethod] = PaymentMethod.CASH

    @validator('number_of_seats')
    def validate_seats(cls, v):
        if v < 1 or v > 8:
            raise ValueError('Le nombre de places doit être entre 1 et 8')
        return v


class ReservationUpdateRequest(BaseModel):
    """Schema pour modifier une réservation"""
    pickup_address: Optional[str] = Field(None, max_length=255)
    pickup_latitude: Optional[float] = Field(None, ge=-90, le=90)
    pickup_longitude: Optional[float] = Field(None, ge=-180, le=180)
    dropoff_address: Optional[str] = Field(None, max_length=255)
    dropoff_latitude: Optional[float] = Field(None, ge=-90, le=90)
    dropoff_longitude: Optional[float] = Field(None, ge=-180, le=180)
    special_requests: Optional[str] = Field(None, max_length=500)


class ReservationCancelRequest(BaseModel):
    """Schema pour annuler une réservation"""
    reason: str = Field(..., min_length=5, max_length=255)


class ReservationConfirmRequest(BaseModel):
    """Schema pour confirmer une réservation (conducteur)"""
    accept: bool
    message: Optional[str] = Field(None, max_length=200)


class RatingRequest(BaseModel):
    """Schema pour noter un trajet"""
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=300)

    @validator('rating')
    def validate_rating(cls, v):
        if v < 1 or v > 5:
            raise ValueError('La note doit être entre 1 et 5')
        return v


# ================ RESPONSES ================

class PassengerResponse(BaseModel):
    """Informations du passager dans une réservation"""
    id: int
    first_name: str
    last_name: str
    phone: str
    rating_average: float
    total_ratings: int
    trips_as_passenger: int

    class Config:
        from_attributes = True


class TripSummaryResponse(BaseModel):
    """Résumé du trajet pour une réservation"""
    id: int
    departure_city: str
    arrival_city: str
    departure_datetime: datetime
    price_per_seat: float
    driver_name: Optional[str] = None
    vehicle_info: Optional[str] = None

    class Config:
        from_attributes = True


class ReservationResponse(BaseModel):
    """Schema de réponse pour une réservation"""
    id: int
    trip_id: int
    passenger_id: int
    
    number_of_seats: int
    pickup_address: Optional[str]
    dropoff_address: Optional[str]
    
    status: ReservationStatus
    total_price: float
    price_per_seat: float
    platform_fee: float
    
    payment_method: Optional[PaymentMethod]
    payment_status: PaymentStatus
    
    special_requests: Optional[str]
    driver_notes: Optional[str]
    
    passenger_rating: Optional[int]
    driver_rating: Optional[int]
    passenger_comment: Optional[str]
    driver_comment: Optional[str]
    
    created_at: datetime
    confirmed_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    cancellation_reason: Optional[str]
    
    # Relations
    trip: Optional[TripSummaryResponse]
    passenger: Optional[PassengerResponse]

    class Config:
        from_attributes = True


class ReservationListResponse(BaseModel):
    """Schema de réponse pour une liste de réservations"""
    reservations: List[ReservationResponse]
    total_count: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool


class MyReservationsResponse(BaseModel):
    """Mes réservations avec statistiques"""
    active_reservations: List[ReservationResponse]
    completed_reservations: List[ReservationResponse]
    cancelled_reservations: List[ReservationResponse]
    
    total_reservations: int
    total_spent: float
    total_trips: int
    average_rating_given: float


class TripReservationsResponse(BaseModel):
    """Réservations pour un trajet (vue conducteur)"""
    trip_id: int
    trip_summary: str
    pending_reservations: List[ReservationResponse]
    confirmed_reservations: List[ReservationResponse]
    cancelled_reservations: List[ReservationResponse]
    
    total_reservations: int
    confirmed_passengers: int
    total_earnings: float


class ReservationCreateResponse(BaseModel):
    """Réponse après création d'une réservation"""
    message: str
    reservation: ReservationResponse
    next_steps: List[str]
    success: bool = True

    @validator('next_steps', pre=True, always=True)
    def set_next_steps(cls, v, values):
        return [
            "Votre demande de réservation a été envoyée au conducteur",
            "Vous recevrez une notification dès que le conducteur aura répondu",
            "Vous pouvez annuler votre réservation jusqu'à 2h avant le départ"
        ]


class ReservationConfirmResponse(BaseModel):
    """Réponse après confirmation d'une réservation"""
    message: str
    reservation: ReservationResponse
    passenger_contact: dict
    success: bool = True

    @validator('passenger_contact', pre=True, always=True)
    def set_contact(cls, v, values):
        return {
            "phone": "Visible après confirmation",
            "pickup_point": "Selon les détails de la réservation"
        }


class ReservationStatsResponse(BaseModel):
    """Statistiques des réservations"""
    total_reservations: int
    pending_count: int
    confirmed_count: int
    completed_count: int
    cancelled_count: int
    total_revenue: float
    average_rating: float


class PaymentResponse(BaseModel):
    """Réponse de paiement"""
    reservation_id: int
    amount: float
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    transaction_id: Optional[str]
    payment_url: Optional[str]  # Pour Mobile Money
    success: bool

    class Config:
        from_attributes = True