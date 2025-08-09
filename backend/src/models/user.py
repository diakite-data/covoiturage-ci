"""
Modèle User - Utilisateurs de l'application (passagers et conducteurs)
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum, Float
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import enum

# Base pour les modèles
Base = declarative_base()


class UserType(str, enum.Enum):
    """Types d'utilisateurs"""
    PASSAGER = "passager"
    CONDUCTEUR = "conducteur"
    BOTH = "both"  # Peut être les deux


class UserStatus(str, enum.Enum):
    """Statuts de vérification"""
    PENDING = "pending"      # En attente de vérification
    VERIFIED = "verified"    # Vérifié
    SUSPENDED = "suspended"  # Suspendu
    BANNED = "banned"       # Banni


class User(Base):
    """
    Modèle utilisateur - Base commune pour passagers et conducteurs
    """
    __tablename__ = "users"

    # Identifiants
    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)
    
    # Informations personnelles
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    date_of_birth = Column(DateTime, nullable=True)
    gender = Column(Enum("M", "F", "Other", name="gender_enum"), nullable=True)
    
    # Authentification
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_phone_verified = Column(Boolean, default=False, nullable=False)
    is_email_verified = Column(Boolean, default=False, nullable=False)
    
    # Type et statut
    user_type = Column(Enum(UserType), default=UserType.PASSAGER, nullable=False)
    status = Column(Enum(UserStatus), default=UserStatus.PENDING, nullable=False)
    
    # Localisation
    city = Column(String(100), nullable=True)
    neighborhood = Column(String(100), nullable=True)  # Quartier
    
    # Profil
    profile_picture = Column(String(500), nullable=True)  # URL de la photo
    bio = Column(Text, nullable=True)
    
    # Évaluations
    rating_average = Column(Float, default=0.0, nullable=False)
    total_ratings = Column(Integer, default=0, nullable=False)
    
    # Compteurs
    trips_as_driver = Column(Integer, default=0, nullable=False)
    trips_as_passenger = Column(Integer, default=0, nullable=False)
    total_distance_km = Column(Float, default=0.0, nullable=False)
    
    # Informations conducteur (si applicable)
    driver_license_number = Column(String(50), nullable=True)
    driver_license_verified = Column(Boolean, default=False, nullable=False)
    vehicle_make = Column(String(50), nullable=True)  # Marque
    vehicle_model = Column(String(50), nullable=True)  # Modèle
    vehicle_year = Column(Integer, nullable=True)
    vehicle_color = Column(String(30), nullable=True)
    vehicle_plate = Column(String(20), nullable=True)  # Plaque d'immatriculation
    vehicle_seats = Column(Integer, nullable=True)     # Nombre de places
    
    # Préférences
    accepts_pets = Column(Boolean, default=False, nullable=False)
    accepts_smoking = Column(Boolean, default=False, nullable=False)
    music_preference = Column(String(50), nullable=True)  # "silence", "radio", "playlist"
    conversation_level = Column(String(50), nullable=True)  # "quiet", "chatty", "flexible"
    
    # Métadonnées
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    last_login = Column(DateTime(timezone=True), nullable=True)
    last_location_update = Column(DateTime(timezone=True), nullable=True)
    
    # Relations (définies plus tard avec les autres modèles)
    # trips_created = relationship("Trip", foreign_keys="Trip.driver_id")
    # reservations = relationship("Reservation", foreign_keys="Reservation.passenger_id")
    # reviews_given = relationship("Review", foreign_keys="Review.reviewer_id")
    # reviews_received = relationship("Review", foreign_keys="Review.reviewed_id")

    def __repr__(self):
        return f"<User(id={self.id}, phone={self.phone}, name={self.first_name} {self.last_name}, type={self.user_type})>"

    @property
    def full_name(self):
        """Nom complet de l'utilisateur"""
        return f"{self.first_name} {self.last_name}"

    @property
    def is_driver(self):
        """Vérifie si l'utilisateur peut être conducteur"""
        return self.user_type in [UserType.CONDUCTEUR, UserType.BOTH]

    @property
    def is_passenger(self):
        """Vérifie si l'utilisateur peut être passager"""
        return self.user_type in [UserType.PASSAGER, UserType.BOTH]

    @property
    def is_verified(self):
        """Vérifie si l'utilisateur est complètement vérifié"""
        basic_verified = self.is_phone_verified and self.status == UserStatus.VERIFIED
        if self.is_driver:
            return basic_verified and self.driver_license_verified
        return basic_verified

    @property
    def vehicle_info(self):
        """Informations complètes du véhicule"""
        if not self.is_driver:
            return None
        return {
            "make": self.vehicle_make,
            "model": self.vehicle_model,
            "year": self.vehicle_year,
            "color": self.vehicle_color,
            "plate": self.vehicle_plate,
            "seats": self.vehicle_seats
        }

    def update_rating(self, new_rating: float):
        """Met à jour la note moyenne de l'utilisateur"""
        total_score = self.rating_average * self.total_ratings
        self.total_ratings += 1
        self.rating_average = (total_score + new_rating) / self.total_ratings

    def can_create_trip(self) -> bool:
        """Vérifie si l'utilisateur peut créer un trajet"""
        return (
            self.is_driver and 
            self.is_verified and 
            self.status == UserStatus.VERIFIED and
            self.is_active
        )

    def can_book_trip(self) -> bool:
        """Vérifie si l'utilisateur peut réserver un trajet"""
        return (
            self.is_passenger and
            self.is_phone_verified and
            self.status in [UserStatus.VERIFIED, UserStatus.PENDING] and
            self.is_active
        )