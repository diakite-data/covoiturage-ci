"""
Routes d'authentification
Endpoints pour inscription, connexion, vérification OTP, etc.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from src.database import get_db, get_redis
from src.schemas.auth import (
    UserRegisterRequest, UserLoginRequest, VerifyPhoneRequest,
    ResendOTPRequest, ChangePasswordRequest, ResetPasswordRequest,
    AuthResponse, TokenResponse, UserProfileResponse, MessageResponse,
    OTPSentResponse, DriverVerificationRequest, DriverVerificationResponse
)
from src.services.auth import AuthService
from src.models.user import User, UserType

# Création du router
router = APIRouter(prefix="/api/v1/auth", tags=["Authentification"])

# Configuration de la sécurité
security = HTTPBearer()

# Instance du service d'authentification
def get_auth_service(redis_client=Depends(get_redis)):
    return AuthService(redis_client)


# ================ DEPENDENCY INJECTION ================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
) -> User:
    """
    Dependency pour récupérer l'utilisateur actuel à partir du token JWT
    Utilisé dans les endpoints protégés
    """
    token = credentials.credentials
    return auth_service.get_current_user(db, token)


async def get_current_verified_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Dependency pour récupérer un utilisateur vérifié
    """
    if not current_user.is_phone_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Numéro de téléphone non vérifié. Veuillez vérifier votre téléphone d'abord."
        )
    return current_user


async def get_current_driver(
    current_user: User = Depends(get_current_verified_user)
) -> User:
    """
    Dependency pour récupérer un conducteur vérifié
    """
    if not current_user.is_driver:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux conducteurs"
        )
    
    if not current_user.driver_license_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permis de conduire non vérifié. Veuillez soumettre vos documents."
        )
    
    return current_user


# ================ ROUTES ================

@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegisterRequest,
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Inscription d'un nouvel utilisateur
    
    - **phone**: Numéro de téléphone (format ivoirien)
    - **email**: Email (optionnel)
    - **first_name**: Prénom
    - **last_name**: Nom de famille
    - **password**: Mot de passe (min 6 caractères)
    - **user_type**: Type d'utilisateur (PASSAGER, CONDUCTEUR, BOTH)
    - **city**: Ville (optionnel)
    - **neighborhood**: Quartier (optionnel)
    
    Envoie automatiquement un code OTP de vérification.
    """
    try:
        # Convertir en dictionnaire
        user_dict = user_data.dict()
        
        # Créer l'utilisateur
        new_user = auth_service.register_user(db, user_dict)
        
        return MessageResponse(
            message=f"Compte créé avec succès pour {new_user.phone}. "
                   f"Un code de vérification a été envoyé par SMS.",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création du compte: {str(e)}"
        )


@router.post("/login", response_model=AuthResponse)
async def login(
    credentials: UserLoginRequest,
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Connexion utilisateur
    
    - **phone**: Numéro de téléphone
    - **password**: Mot de passe
    
    Retourne un token JWT et les informations utilisateur.
    """
    # Authentifier l'utilisateur
    user = auth_service.authenticate_user(db, credentials.phone, credentials.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Numéro de téléphone ou mot de passe incorrect"
        )
    
    # Créer le token
    token_data = auth_service.create_token_for_user(user)
    
    # Préparer la réponse
    return AuthResponse(
        message="Connexion réussie",
        token=TokenResponse(**token_data),
        user=UserProfileResponse.from_orm(user)
    )


@router.post("/verify-phone", response_model=AuthResponse)
async def verify_phone(
    verification_data: VerifyPhoneRequest,
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Vérification du numéro de téléphone avec code OTP
    
    - **phone**: Numéro de téléphone
    - **otp_code**: Code OTP à 6 chiffres
    
    Marque le téléphone comme vérifié et connecte automatiquement l'utilisateur.
    """
    # Vérifier l'OTP et mettre à jour l'utilisateur
    user = auth_service.verify_phone_number(db, verification_data.phone, verification_data.otp_code)
    
    # Créer le token de connexion automatique
    token_data = auth_service.create_token_for_user(user)
    
    return AuthResponse(
        message="Téléphone vérifié avec succès. Vous êtes maintenant connecté.",
        token=TokenResponse(**token_data),
        user=UserProfileResponse.from_orm(user)
    )


@router.post("/resend-otp", response_model=OTPSentResponse)
async def resend_otp(
    otp_request: ResendOTPRequest,
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Renvoie un code OTP
    
    - **phone**: Numéro de téléphone
    """
    # Vérifier que l'utilisateur existe
    user = db.query(User).filter(User.phone == otp_request.phone).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun utilisateur trouvé avec ce numéro"
        )
    
    # Renvoyer l'OTP
    auth_service.send_otp(otp_request.phone)
    
    return OTPSentResponse(
        message="Nouveau code OTP envoyé",
        phone=otp_request.phone,
        expires_in=300
    )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Changer le mot de passe (utilisateur connecté)
    
    - **current_password**: Mot de passe actuel
    - **new_password**: Nouveau mot de passe
    
    Nécessite d'être connecté.
    """
    auth_service.change_password(
        db, current_user, 
        password_data.current_password, 
        password_data.new_password
    )
    
    return MessageResponse(
        message="Mot de passe modifié avec succès"
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    reset_data: ResetPasswordRequest,
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Réinitialiser le mot de passe avec OTP
    
    - **phone**: Numéro de téléphone
    - **otp_code**: Code OTP reçu par SMS
    - **new_password**: Nouveau mot de passe
    
    Utiliser d'abord /forgot-password pour recevoir l'OTP.
    """
    auth_service.reset_password(
        db, reset_data.phone, 
        reset_data.otp_code, 
        reset_data.new_password
    )
    
    return MessageResponse(
        message="Mot de passe réinitialisé avec succès"
    )


@router.post("/forgot-password", response_model=OTPSentResponse)
async def forgot_password(
    phone_request: ResendOTPRequest,
    db: Session = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    Demander la réinitialisation du mot de passe
    
    - **phone**: Numéro de téléphone
    
    Envoie un code OTP pour réinitialiser le mot de passe.
    """
    # Vérifier que l'utilisateur existe
    user = db.query(User).filter(User.phone == phone_request.phone).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun utilisateur trouvé avec ce numéro"
        )
    
    # Envoyer l'OTP
    auth_service.send_otp(phone_request.phone)
    
    return OTPSentResponse(
        message="Code de réinitialisation envoyé par SMS",
        phone=phone_request.phone,
        expires_in=300
    )


@router.post("/driver-verification", response_model=DriverVerificationResponse)
async def request_driver_verification(
    driver_data: DriverVerificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Demander la vérification conducteur
    
    - **driver_license_number**: Numéro de permis de conduire
    - **vehicle_make**: Marque du véhicule
    - **vehicle_model**: Modèle du véhicule
    - **vehicle_year**: Année du véhicule
    - **vehicle_color**: Couleur du véhicule
    - **vehicle_plate**: Plaque d'immatriculation
    - **vehicle_seats**: Nombre de places
    
    Nécessite d'être connecté. Met à jour le type d'utilisateur pour inclure CONDUCTEUR.
    """
    # Vérifier que l'utilisateur peut devenir conducteur
    if current_user.user_type == UserType.PASSAGER:
        current_user.user_type = UserType.BOTH
    elif current_user.user_type != UserType.CONDUCTEUR and current_user.user_type != UserType.BOTH:
        current_user.user_type = UserType.BOTH
    
    # Mettre à jour les informations du véhicule
    current_user.driver_license_number = driver_data.driver_license_number
    current_user.vehicle_make = driver_data.vehicle_make
    current_user.vehicle_model = driver_data.vehicle_model
    current_user.vehicle_year = driver_data.vehicle_year
    current_user.vehicle_color = driver_data.vehicle_color
    current_user.vehicle_plate = driver_data.vehicle_plate
    current_user.vehicle_seats = driver_data.vehicle_seats
    
    # Dans une vraie application, on marquerait comme "en attente de vérification"
    # Pour le MVP, on l'approuve automatiquement
    current_user.driver_license_verified = True
    
    db.commit()
    
    return DriverVerificationResponse(
        message="Demande de vérification conducteur soumise avec succès",
        status="approved",  # Pour le MVP
        estimated_processing_time="Immédiat (mode développement)"
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """
    Récupérer le profil de l'utilisateur connecté
    
    Nécessite d'être connecté avec un token valide.
    """
    return UserProfileResponse.from_orm(current_user)


@router.post("/logout", response_model=MessageResponse)
async def logout(current_user: User = Depends(get_current_user)):
    """
    Déconnexion de l'utilisateur
    
    Dans une implémentation complète, on pourrait blacklister le token.
    Pour le MVP, on retourne simplement un message de confirmation.
    """
    return MessageResponse(
        message=f"Déconnexion réussie pour {current_user.phone}"
    )