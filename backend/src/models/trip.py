"""
Modèle Trip - Trajets proposés par les conducteurs
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, Enum
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import enum

# Utilisation de la même Base que User
from .user import Base


class TripStatus(str, enum.Enum):
    """Statuts des trajets"""
    ACTIVE = "active"        # Actif, accepte les réservations
    FULL = "full"           # Complet, plus de places
    STARTED = "started"     # Trajet commencé
    COMPLETED = "completed" # Trajet terminé
    CANCELLED = "cancelled" # Annulé


class TripType(str, enum.Enum):
    """Types de trajets"""
    ONE_TIME = "one_time"   # Trajet unique
    DAILY = "daily"         # Trajet quotidien
    WEEKLY = "weekly"       # Trajet hebdomadaire


class Trip(Base):
    """
    Modèle trajet - Trajets proposés par les conducteurs
    """
    __tablename__ = "trips"

    # Identifiants
    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Informations du trajet
    departure_address = Column(String(255), nullable=False)
    departure_city = Column(String(100), nullable=False)
    departure_latitude = Column(Float, nullable=True)   # Coordonnées GPS
    departure_longitude = Column(Float, nullable=True)
    
    arrival_address = Column(String(255), nullable=False)
    arrival_city = Column(String(100), nullable=False)
    arrival_latitude = Column(Float, nullable=True)
    arrival_longitude = Column(Float, nullable=True)
    
    # Timing
    departure_datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    estimated_duration_minutes = Column(Integer, nullable=True)  # Durée estimée
    actual_departure_time = Column(DateTime(timezone=True), nullable=True)
    actual_arrival_time = Column(DateTime(timezone=True), nullable=True)
    
    # Capacité et tarification
    total_seats = Column(Integer, nullable=False)      # Places totales dans le véhicule
    available_seats = Column(Integer, nullable=False)  # Places disponibles
    price_per_seat = Column(Float, nullable=False)     # Prix par place en FCFA
    total_distance_km = Column(Float, nullable=True)   # Distance totale
    
    # Type et statut
    trip_type = Column(Enum(TripType), default=TripType.ONE_TIME, nullable=False)
    status = Column(Enum(TripStatus), default=TripStatus.ACTIVE, nullable=False)
    
    # Préférences et règles
    accepts_pets = Column(Boolean, default=False, nullable=False)
    accepts_smoking = Column(Boolean, default=False, nullable=False)
    accepts_food = Column(Boolean, default=True, nullable=False)
    luggage_allowed = Column(Boolean, default=True, nullable=False)
    max_detour_km = Column(Float, default=2.0, nullable=False)  # Détour max pour récupérer passagers
    
    # Informations additionnelles
    description = Column(Text, nullable=True)          # Description libre
    special_instructions = Column(Text, nullable=True)  # Instructions spéciales
    
    # Points d'arrêt intermédiaires (JSON ou relation séparée)
    waypoints = Column(Text, nullable=True)  # JSON des points d'arrêt
    
    # Récurrence (pour trajets réguliers)
    is_recurring = Column(Boolean, default=False, nullable=False)
    recurring_days = Column(String(20), nullable=True)  # "1,2,3,4,5" pour lun-ven
    recurring_end_date = Column(DateTime(timezone=True), nullable=True)
    
    # Informations financières
    total_earnings = Column(Float, default=0.0, nullable=False)  # Gains totaux
    platform_commission = Column(Float, default=0.0, nullable=False)  # Commission plateforme
    driver_earnings = Column(Float, default=0.0, nullable=False)   # Gains conducteur
    
    # Métadonnées
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_reason = Column(String(255), nullable=True)
    
    # Relations
    driver = relationship("User", foreign_keys=[driver_id])
    # reservations = relationship("Reservation", back_populates="trip", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Trip(id={self.id}, {self.departure_city}→{self.arrival_city}, {self.departure_datetime}, seats={self.available_seats}/{self.total_seats})>"

    @property
    def is_bookable(self):
        """Vérifie si le trajet peut être réservé"""
        return (
            self.status == TripStatus.ACTIVE and
            self.available_seats > 0 and
            self.departure_datetime > func.now()
        )

    @property
    def occupancy_rate(self):
        """Taux d'occupation du trajet"""
        if self.total_seats == 0:
            return 0
        return ((self.total_seats - self.available_seats) / self.total_seats) * 100

    @property
    def route_summary(self):
        """Résumé de l'itinéraire"""
        return f"{self.departure_city} → {self.arrival_city}"

    @property
    def earnings_breakdown(self):
        """Détail des gains"""
        return {
            "total": self.total_earnings,
            "commission": self.platform_commission,
            "driver": self.driver_earnings,
            "commission_rate": (self.platform_commission / self.total_earnings * 100) if self.total_earnings > 0 else 0
        }

    def book_seat(self, passenger_count: int = 1) -> bool:
        """
        Réserve des places dans le trajet
        Retourne True si la réservation est possible
        """
        if self.available_seats >= passenger_count and self.is_bookable:
            self.available_seats -= passenger_count
            if self.available_seats == 0:
                self.status = TripStatus.FULL
            return True
        return False

    def cancel_booking(self, passenger_count: int = 1):
        """Annule une réservation et libère les places"""
        self.available_seats += passenger_count
        if self.status == TripStatus.FULL and self.available_seats > 0:
            self.status = TripStatus.ACTIVE

    def calculate_earnings(self, commission_rate: float = 0.10):
        """Calcule les gains basés sur les réservations"""
        occupied_seats = self.total_seats - self.available_seats
        self.total_earnings = occupied_seats * self.price_per_seat
        self.platform_commission = self.total_earnings * commission_rate
        self.driver_earnings = self.total_earnings - self.platform_commission

    def can_be_modified_by(self, user_id: int) -> bool:
        """Vérifie si un utilisateur peut modifier ce trajet"""
        return (
            self.driver_id == user_id and
            self.status in [TripStatus.ACTIVE, TripStatus.FULL] and
            self.departure_datetime > func.now()
        )

    def get_distance_to_point(self, latitude: float, longitude: float) -> float:
        """
        Calcule la distance entre le point de départ et un point donné
        (Implémentation basique - à améliorer avec une vraie API de géolocalisation)
        """
        if not self.departure_latitude or not self.departure_longitude:
            return float('inf')
        
        # Formule de distance approximative (à remplacer par une vraie API)
        lat_diff = abs(self.departure_latitude - latitude)
        lon_diff = abs(self.departure_longitude - longitude)
        return ((lat_diff ** 2 + lon_diff ** 2) ** 0.5) * 111  # Approximation en km