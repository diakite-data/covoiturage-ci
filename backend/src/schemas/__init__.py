"""
Module schemas - Validation des données avec Pydantic
"""

from .auth import (
    UserRegisterRequest,
    UserLoginRequest, 
    VerifyPhoneRequest,
    ResendOTPRequest,
    ChangePasswordRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserProfileResponse,
    AuthResponse,
    MessageResponse,
    OTPSentResponse,
    DriverVerificationRequest,
    DriverVerificationResponse
)

from .trip import (
    TripCreateRequest,
    TripUpdateRequest,
    TripSearchFilters,
    TripResponse,
    TripListResponse,
    TripCreateResponse,
    TripStatsResponse,
    MyTripsResponse,
    TripCancelRequest
)

from .reservation import (
    ReservationCreateRequest,
    ReservationUpdateRequest,
    ReservationCancelRequest,
    ReservationConfirmRequest,
    RatingRequest,
    ReservationResponse,
    ReservationListResponse,
    ReservationCreateResponse,
    ReservationConfirmResponse,
    MyReservationsResponse,
    TripReservationsResponse,
    ReservationStatsResponse
)

__all__ = [
    # Auth requests
    "UserRegisterRequest",
    "UserLoginRequest",
    "VerifyPhoneRequest", 
    "ResendOTPRequest",
    "ChangePasswordRequest",
    "ResetPasswordRequest",
    "DriverVerificationRequest",
    
    # Auth responses
    "TokenResponse",
    "UserProfileResponse",
    "AuthResponse", 
    "MessageResponse",
    "OTPSentResponse",
    "DriverVerificationResponse",
    
    # Trip requests
    "TripCreateRequest",
    "TripUpdateRequest", 
    "TripSearchFilters",
    "TripCancelRequest",
    
    # Trip responses
    "TripResponse",
    "TripListResponse",
    "TripCreateResponse",
    "TripStatsResponse",
    "MyTripsResponse",

    # Reservation requests
    "ReservationCreateRequest",
    "ReservationUpdateRequest",
    "ReservationCancelRequest", 
    "ReservationConfirmRequest",
    "RatingRequest",
    
    # Reservation responses
    "ReservationResponse",
    "ReservationListResponse",
    "ReservationCreateResponse",
    "ReservationConfirmResponse",
    "MyReservationsResponse",
    "TripReservationsResponse",
    "ReservationStatsResponse"
]