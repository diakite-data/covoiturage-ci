"""
Modèle Reservation - Réservations de trajets par les passagers
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Float, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

# Utilisation de la même Base que User
from .user import Base


class ReservationStatus(str, enum.Enum):
    """Statuts des réservations"""
    PENDING = "pending"         # En attente de confirmation du conducteur
    CONFIRMED = "confirmed"     # Confirmée par le conducteur
    PAID = "paid"              # Payée
    STARTED = "started"        # Trajet commencé
    COMPLETED = "completed"    # Trajet terminé
    CANCELLED_BY_PASSENGER = "cancelled_by_passenger"
    CANCELLED_BY_DRIVER = "cancelled_by_driver"
    NO_SHOW = "no_show"       # Passager ne s'est pas présenté


class PaymentMethod(str, enum.Enum):
    """Méthodes de paiement"""
    CASH = "cash"              # Espèces
    MOBILE_MONEY = "mobile_money"  # Mobile Money
    CARD = "card"              # Carte bancaire


class PaymentStatus(str, enum.Enum):
    """Statuts de paiement"""
    PENDING = "pending"        # En attente
    COMPLETED = "completed"    # Payé
    FAILED = "failed"         # Échec
    REFUNDED = "refunded"     # Remboursé


class Reservation(Base):
    """
    Modèle réservation - Réservations de trajets par les passagers
    """
    __tablename__ = "reservations"

    # Identifiants
    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False, index=True)
    passenger_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Détails de la réservation
    number_of_seats = Column(Integer, default=1, nullable=False)
    pickup_address = Column(String(255), nullable=True)    # Adresse de prise en charge
    pickup_latitude = Column(Float, nullable=True)
    pickup_longitude = Column(Float, nullable=True)
    dropoff_address = Column(String(255), nullable=True)   # Adresse de dépose
    dropoff_latitude = Column(Float, nullable=True)
    dropoff_longitude = Column(Float, nullable=True)
    
    # Timing
    requested_pickup_time = Column(DateTime(timezone=True), nullable=True)
    actual_pickup_time = Column(DateTime(timezone=True), nullable=True)
    actual_dropoff_time = Column(DateTime(timezone=True), nullable=True)
    
    # Statut
    status = Column(Enum(ReservationStatus), default=ReservationStatus.PENDING, nullable=False)
    
    # Informations financières
    total_price = Column(Float, nullable=False)            # Prix total à payer
    price_per_seat = Column(Float, nullable=False)         # Prix unitaire (copie du trip)
    platform_fee = Column(Float, default=0.0, nullable=False)  # Frais de plateforme
    
    # Paiement
    payment_method = Column(Enum(PaymentMethod), nullable=True)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    payment_transaction_id = Column(String(100), nullable=True)  # ID transaction externe
    payment_reference = Column(String(100), nullable=True)       # Référence paiement
    paid_at = Column(DateTime(timezone=True), nullable=True)
    
    # Communication
    passenger_phone = Column(String(20), nullable=True)    # Tel du passager (copie)
    special_requests = Column(Text, nullable=True)         # Demandes spéciales
    driver_notes = Column(Text, nullable=True)             # Notes du conducteur
    
    # Tracking
    passenger_rating = Column(Integer, nullable=True)      # Note donnée au passager (1-5)
    driver_rating = Column(Integer, nullable=True)         # Note donnée au conducteur (1-5)
    passenger_comment = Column(Text, nullable=True)        # Commentaire sur le conducteur
    driver_comment = Column(Text, nullable=True)           # Commentaire sur le passager
    
    # Métadonnées
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_reason = Column(String(255), nullable=True)
    
    # Relations
    trip = relationship("Trip")
    passenger = relationship("User", foreign_keys=[passenger_id])

    def __repr__(self):
        return f"<Reservation(id={self.id}, trip_id={self.trip_id}, passenger_id={self.passenger_id}, seats={self.number_of_seats}, status={self.status})>"

    @property
    def can_be_cancelled(self):
        """Vérifie si la réservation peut être annulée"""
        cancellable_statuses = [
            ReservationStatus.PENDING,
            ReservationStatus.CONFIRMED,
            ReservationStatus.PAID
        ]
        return self.status in cancellable_statuses

    @property
    def can_be_paid(self):
        """Vérifie si la réservation peut être payée"""
        return (
            self.status == ReservationStatus.CONFIRMED and
            self.payment_status == PaymentStatus.PENDING
        )

    @property
    def can_be_rated(self):
        """Vérifie si la réservation peut être notée"""
        return self.status == ReservationStatus.COMPLETED

    @property
    def is_active(self):
        """Vérifie si la réservation est active"""
        active_statuses = [
            ReservationStatus.PENDING,
            ReservationStatus.CONFIRMED,
            ReservationStatus.PAID,
            ReservationStatus.STARTED
        ]
        return self.status in active_statuses

    @property
    def total_amount_breakdown(self):
        """Détail du montant total"""
        base_amount = self.price_per_seat * self.number_of_seats
        return {
            "base_price": base_amount,
            "platform_fee": self.platform_fee,
            "total": self.total_price,
            "seats": self.number_of_seats
        }

    def confirm(self):
        """Confirme la réservation"""
        if self.status == ReservationStatus.PENDING:
            self.status = ReservationStatus.CONFIRMED
            self.confirmed_at = func.now()
            return True
        return False

    def cancel(self, reason: str = None, cancelled_by: str = "passenger"):
        """Annule la réservation"""
        if self.can_be_cancelled:
            if cancelled_by == "passenger":
                self.status = ReservationStatus.CANCELLED_BY_PASSENGER
            else:
                self.status = ReservationStatus.CANCELLED_BY_DRIVER
            
            self.cancelled_at = func.now()
            self.cancellation_reason = reason
            return True
        return False

    def mark_as_paid(self, transaction_id: str = None, payment_method: PaymentMethod = None):
        """Marque la réservation comme payée"""
        if self.can_be_paid:
            self.payment_status = PaymentStatus.COMPLETED
            self.status = ReservationStatus.PAID
            self.paid_at = func.now()
            if transaction_id:
                self.payment_transaction_id = transaction_id
            if payment_method:
                self.payment_method = payment_method
            return True
        return False

    def start_trip(self):
        """Marque le début du trajet"""
        if self.status == ReservationStatus.PAID:
            self.status = ReservationStatus.STARTED
            self.actual_pickup_time = func.now()
            return True
        return False

    def complete_trip(self):
        """Marque la fin du trajet"""
        if self.status == ReservationStatus.STARTED:
            self.status = ReservationStatus.COMPLETED
            self.actual_dropoff_time = func.now()
            return True
        return False

    def rate_driver(self, rating: int, comment: str = None):
        """Note le conducteur"""
        if self.can_be_rated and 1 <= rating <= 5:
            self.driver_rating = rating
            self.passenger_comment = comment
            return True
        return False

    def rate_passenger(self, rating: int, comment: str = None):
        """Note le passager (appelé par le conducteur)"""
        if self.can_be_rated and 1 <= rating <= 5:
            self.passenger_rating = rating
            self.driver_comment = comment
            return True
        return False

    def calculate_refund_amount(self, cancellation_policy: dict = None) -> float:
        """
        Calcule le montant du remboursement selon la politique d'annulation
        """
        if self.payment_status != PaymentStatus.COMPLETED:
            return 0.0
        
        # Politique par défaut (à personnaliser)
        if not cancellation_policy:
            cancellation_policy = {
                "more_than_24h": 1.0,   # Remboursement complet
                "12_to_24h": 0.5,       # 50% de remboursement
                "less_than_12h": 0.0    # Pas de remboursement
            }
        
        # Calcul du temps restant avant le départ (implémentation simplifiée)
        # Dans la vraie app, il faudrait comparer avec trip.departure_datetime
        return self.total_price * cancellation_policy.get("more_than_24h", 0.0)