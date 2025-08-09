"""
Schemas Pydantic pour l'authentification
Validation des données d'entrée et de sortie
"""
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
from datetime import datetime
from src.models.user import UserType, UserStatus


class UserRegisterRequest(BaseModel):
    """Schema pour l'inscription d'un nouvel utilisateur"""
    phone: str
    email: Optional[EmailStr] = None
    first_name: str
    last_name: str
    password: str
    user_type: UserType = UserType.PASSAGER
    city: Optional[str] = None
    neighborhood: Optional[str] = None

    @validator('phone')
    def validate_phone(cls, v):
        # Validation basique du numéro de téléphone ivoirien
        if not v.startswith(('+225', '225', '0')):
            raise ValueError('Le numéro doit être un numéro ivoirien valide')
        # Nettoyer le numéro
        cleaned = v.replace('+', '').replace(' ', '').replace('-', '')
        if not cleaned.isdigit():
            raise ValueError('Le numéro ne doit contenir que des chiffres')
        if len(cleaned) < 8 or len(cleaned) > 12:
            raise ValueError('Le numéro doit contenir entre 8 et 12 chiffres')
        return cleaned

    @validator('password')
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError('Le mot de passe doit contenir au moins 6 caractères')
        return v

    @validator('first_name', 'last_name')
    def validate_names(cls, v):
        if len(v.strip()) < 2:
            raise ValueError('Le nom doit contenir au moins 2 caractères')
        return v.strip().title()


class UserLoginRequest(BaseModel):
    """Schema pour la connexion utilisateur"""
    phone: str
    password: str

    @validator('phone')
    def validate_phone(cls, v):
        # Même validation que pour l'inscription
        cleaned = v.replace('+', '').replace(' ', '').replace('-', '')
        if not cleaned.isdigit():
            raise ValueError('Format de numéro invalide')
        return cleaned


class VerifyPhoneRequest(BaseModel):
    """Schema pour la vérification du téléphone par OTP"""
    phone: str
    otp_code: str

    @validator('otp_code')
    def validate_otp(cls, v):
        if not v.isdigit() or len(v) != 6:
            raise ValueError('Le code OTP doit contenir exactement 6 chiffres')
        return v


class ResendOTPRequest(BaseModel):
    """Schema pour renvoyer un code OTP"""
    phone: str


class ChangePasswordRequest(BaseModel):
    """Schema pour changer le mot de passe"""
    current_password: str
    new_password: str

    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 6:
            raise ValueError('Le nouveau mot de passe doit contenir au moins 6 caractères')
        return v


class ResetPasswordRequest(BaseModel):
    """Schema pour réinitialiser le mot de passe"""
    phone: str
    otp_code: str
    new_password: str

    @validator('new_password')
    def validate_new_password(cls, v):
        if len(v) < 6:
            raise ValueError('Le nouveau mot de passe doit contenir au moins 6 caractères')
        return v


# ================ RESPONSES ================

class TokenResponse(BaseModel):
    """Schema de réponse avec token JWT"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Durée en secondes
    user_id: int
    user_type: UserType
    phone: str


class UserProfileResponse(BaseModel):
    """Schema de réponse avec profil utilisateur"""
    id: int
    phone: str
    email: Optional[str]
    first_name: str
    last_name: str
    full_name: str
    user_type: UserType
    status: UserStatus
    city: Optional[str]
    neighborhood: Optional[str]
    profile_picture: Optional[str]
    rating_average: float
    total_ratings: int
    is_phone_verified: bool
    is_email_verified: bool
    is_verified: bool
    created_at: datetime
    last_login: Optional[datetime]

    class Config:
        from_attributes = True  # Pour SQLAlchemy models

    @validator('full_name', pre=True, always=True)
    def set_full_name(cls, v, values):
        if 'first_name' in values and 'last_name' in values:
            return f"{values['first_name']} {values['last_name']}"
        return v


class AuthResponse(BaseModel):
    """Schema de réponse complète d'authentification"""
    message: str
    token: TokenResponse
    user: UserProfileResponse


class MessageResponse(BaseModel):
    """Schema de réponse simple avec message"""
    message: str
    success: bool = True


class OTPSentResponse(BaseModel):
    """Schema de réponse après envoi d'OTP"""
    message: str
    phone: str
    expires_in: int = 300  # 5 minutes par défaut
    success: bool = True


# ================ DRIVER VERIFICATION ================

class DriverVerificationRequest(BaseModel):
    """Schema pour la vérification conducteur"""
    driver_license_number: str
    vehicle_make: str
    vehicle_model: str
    vehicle_year: int
    vehicle_color: str
    vehicle_plate: str
    vehicle_seats: int

    @validator('vehicle_year')
    def validate_year(cls, v):
        current_year = datetime.now().year
        if v < 1990 or v > current_year + 1:
            raise ValueError(f'Année du véhicule invalide (1990-{current_year + 1})')
        return v

    @validator('vehicle_seats')
    def validate_seats(cls, v):
        if v < 2 or v > 9:
            raise ValueError('Le nombre de places doit être entre 2 et 9')
        return v

    @validator('driver_license_number')
    def validate_license(cls, v):
        if len(v.strip()) < 5:
            raise ValueError('Numéro de permis invalide')
        return v.strip().upper()

    @validator('vehicle_plate')
    def validate_plate(cls, v):
        if len(v.strip()) < 4:
            raise ValueError('Plaque d\'immatriculation invalide')
        return v.strip().upper()


class DriverVerificationResponse(BaseModel):
    """Schema de réponse après demande de vérification conducteur"""
    message: str
    status: str = "pending"
    verification_id: Optional[str] = None
    estimated_processing_time: str = "24-48 heures"
