"""
Schemas Pydantic pour les trajets
Validation des données d'entrée et de sortie
"""
from pydantic import BaseModel, validator, Field
from typing import Optional, List
from datetime import datetime
from src.models.trip import TripType, TripStatus


class TripCreateRequest(BaseModel):
    """Schema pour créer un nouveau trajet"""
    departure_address: str = Field(..., min_length=5, max_length=255)
    departure_city: str = Field(..., min_length=2, max_length=100)
    departure_latitude: Optional[float] = Field(None, ge=-90, le=90)
    departure_longitude: Optional[float] = Field(None, ge=-180, le=180)
    
    arrival_address: str = Field(..., min_length=5, max_length=255)
    arrival_city: str = Field(..., min_length=2, max_length=100)
    arrival_latitude: Optional[float] = Field(None, ge=-90, le=90)
    arrival_longitude: Optional[float] = Field(None, ge=-180, le=180)
    
    departure_datetime: datetime
    estimated_duration_minutes: Optional[int] = Field(None, ge=5, le=1440)
    
    available_seats: int = Field(..., ge=1, le=8)
    price_per_seat: float = Field(..., ge=100, le=50000)
    total_distance_km: Optional[float] = Field(None, ge=0.1, le=2000)
    
    trip_type: TripType = TripType.ONE_TIME
    
    accepts_pets: bool = False
    accepts_smoking: bool = False
    accepts_food: bool = True
    luggage_allowed: bool = True
    max_detour_km: float = Field(2.0, ge=0, le=20)
    
    description: Optional[str] = Field(None, max_length=500)
    special_instructions: Optional[str] = Field(None, max_length=300)
    
    is_recurring: bool = False
    recurring_days: Optional[str] = None
    recurring_end_date: Optional[datetime] = None


class TripUpdateRequest(BaseModel):
    """Schema pour modifier un trajet existant"""
    departure_datetime: Optional[datetime] = None
    available_seats: Optional[int] = Field(None, ge=1, le=8)
    price_per_seat: Optional[float] = Field(None, ge=100, le=50000)
    
    accepts_pets: Optional[bool] = None
    accepts_smoking: Optional[bool] = None
    accepts_food: Optional[bool] = None
    luggage_allowed: Optional[bool] = None
    max_detour_km: Optional[float] = Field(None, ge=0, le=20)
    
    description: Optional[str] = Field(None, max_length=500)
    special_instructions: Optional[str] = Field(None, max_length=300)


class TripSearchFilters(BaseModel):
    """Schema pour les filtres de recherche"""
    departure_city: Optional[str] = None
    arrival_city: Optional[str] = None
    departure_date: Optional[datetime] = None
    min_seats: Optional[int] = Field(None, ge=1, le=8)
    max_price: Optional[float] = Field(None, ge=100)
    accepts_pets: Optional[bool] = None
    trip_type: Optional[TripType] = None
    
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    radius_km: Optional[float] = Field(None, ge=1, le=100)
    
    page: int = Field(1, ge=1)
    per_page: int = Field(20, ge=1, le=100)


class DriverResponse(BaseModel):
    """Informations du conducteur dans un trajet"""
    id: int
    first_name: str
    last_name: str
    rating_average: float
    total_ratings: int
    vehicle_make: Optional[str]
    vehicle_model: Optional[str]
    vehicle_color: Optional[str]
    vehicle_seats: Optional[int]
    trips_as_driver: int

    class Config:
        from_attributes = True


class TripResponse(BaseModel):
    """Schema de réponse pour un trajet"""
    id: int
    driver_id: int
    
    departure_address: str
    departure_city: str
    arrival_address: str
    arrival_city: str
    
    departure_datetime: datetime
    total_seats: int
    available_seats: int
    price_per_seat: float
    
    trip_type: TripType
    status: TripStatus
    
    accepts_pets: bool
    accepts_smoking: bool
    accepts_food: bool
    luggage_allowed: bool
    
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TripListResponse(BaseModel):
    """Schema de réponse pour une liste de trajets"""
    trips: List[TripResponse]
    total_count: int
    page: int
    per_page: int
    total_pages: int
    has_next: bool
    has_prev: bool


class TripStatsResponse(BaseModel):
    """Statistiques d'un trajet pour le conducteur"""
    trip_id: int
    reservations_count: int
    confirmed_reservations: int
    total_earnings: float
    platform_commission: float
    driver_earnings: float


class MyTripsResponse(BaseModel):
    """Mes trajets avec statistiques"""
    active_trips: List[TripResponse]
    completed_trips: List[TripResponse]
    cancelled_trips: List[TripResponse]
    total_trips: int
    total_earnings: float
    total_passengers: int
    average_rating: float


class TripCreateResponse(BaseModel):
    """Réponse après création d'un trajet"""
    message: str
    trip: TripResponse
    success: bool = True


class TripCancelRequest(BaseModel):
    """Schema pour annuler un trajet"""
    reason: str = Field(..., min_length=10, max_length=255)
    notify_passengers: bool = True