"""
Service d'authentification
Gestion des tokens JWT, hashage des mots de passe, etc.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
import secrets
import redis
from src.models.user import User, UserStatus
from src.config import get_settings

settings = get_settings()

# Configuration du hashage des mots de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Configuration JWT
SECRET_KEY = settings.JWT_SECRET_KEY
ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES


class AuthService:
    """Service d'authentification"""
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash un mot de passe"""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Vérifie un mot de passe"""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Crée un token JWT"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "iat": datetime.utcnow()})
        
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def verify_token(token: str) -> Dict[str, Any]:
        """Vérifie et décode un token JWT"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def register_user(self, db: Session, user_data: dict) -> User:
        """Inscrit un nouvel utilisateur"""
        
        # Vérifier si l'utilisateur existe déjà
        existing_user = db.query(User).filter(User.phone == user_data["phone"]).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un utilisateur avec ce numéro de téléphone existe déjà"
            )
        
        # Vérifier l'email s'il est fourni
        if user_data.get("email"):
            existing_email = db.query(User).filter(User.email == user_data["email"]).first()
            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Un utilisateur avec cet email existe déjà"
                )
        
        # Hasher le mot de passe
        hashed_password = self.hash_password(user_data["password"])
        
        # Créer l'utilisateur
        db_user = User(
            phone=user_data["phone"],
            email=user_data.get("email"),
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            password_hash=hashed_password,
            user_type=user_data["user_type"],
            city=user_data.get("city"),
            neighborhood=user_data.get("neighborhood"),
            status=UserStatus.PENDING
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        # Générer et envoyer l'OTP
        self.send_otp(db_user.phone)
        
        return db_user

    def authenticate_user(self, db: Session, phone: str, password: str) -> Optional[User]:
        """Authentifie un utilisateur"""
        user = db.query(User).filter(User.phone == phone).first()
        
        if not user:
            return None
        
        if not self.verify_password(password, user.password_hash):
            return None
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Compte désactivé"
            )
        
        # Mettre à jour la dernière connexion
        user.last_login = datetime.utcnow()
        db.commit()
        
        return user

    def create_token_for_user(self, user: User) -> dict:
        """Crée un token pour un utilisateur"""
        token_data = {
            "sub": str(user.id),
            "phone": user.phone,
            "user_type": user.user_type.value,
            "is_verified": user.is_verified
        }
        
        access_token = self.create_access_token(data=token_data)
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user_id": user.id,
            "user_type": user.user_type,
            "phone": user.phone
        }

    def get_current_user(self, db: Session, token: str) -> User:
        """Récupère l'utilisateur actuel à partir du token"""
        try:
            payload = self.verify_token(token)
            user_id: int = int(payload.get("sub"))
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token invalide"
                )
        except (JWTError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide"
            )
        
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Utilisateur non trouvé"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Compte désactivé"
            )
        
        return user

    def generate_otp(self) -> str:
        """Génère un code OTP à 6 chiffres"""
        return f"{secrets.randbelow(1000000):06d}"

    def send_otp(self, phone: str) -> str:
        """Envoie un code OTP par SMS"""
        # Générer le code OTP
        otp_code = self.generate_otp()
        
        # Stocker dans Redis avec expiration de 5 minutes
        if self.redis_client:
            otp_key = f"otp:{phone}"
            self.redis_client.setex(otp_key, 300, otp_code)  # 5 minutes
        
        # TODO: Intégrer avec un service SMS réel (ex: Twilio, Orange SMS API)
        # Pour le développement, on affiche le code dans les logs
        print(f"📱 Code OTP pour {phone}: {otp_code}")
        
        return otp_code

    def verify_otp(self, phone: str, otp_code: str) -> bool:
        """Vérifie un code OTP"""
        if not self.redis_client:
            # Fallback pour le développement
            return otp_code == "123456"
        
        otp_key = f"otp:{phone}"
        stored_otp = self.redis_client.get(otp_key)
        
        if not stored_otp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Code OTP expiré ou invalide"
            )
        
        if stored_otp != otp_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Code OTP incorrect"
            )
        
        # Supprimer le code après vérification
        self.redis_client.delete(otp_key)
        return True

    def verify_phone_number(self, db: Session, phone: str, otp_code: str) -> User:
        """Vérifie le numéro de téléphone avec OTP"""
        
        # Vérifier l'OTP
        if not self.verify_otp(phone, otp_code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Code OTP invalide"
            )
        
        # Trouver l'utilisateur
        user = db.query(User).filter(User.phone == phone).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur non trouvé"
            )
        
        # Marquer comme vérifié
        user.is_phone_verified = True
        if user.status == UserStatus.PENDING:
            user.status = UserStatus.VERIFIED
        
        db.commit()
        db.refresh(user)
        
        return user

    def change_password(self, db: Session, user: User, current_password: str, new_password: str) -> bool:
        """Change le mot de passe d'un utilisateur"""
        
        # Vérifier le mot de passe actuel
        if not self.verify_password(current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mot de passe actuel incorrect"
            )
        
        # Hasher le nouveau mot de passe
        user.password_hash = self.hash_password(new_password)
        
        db.commit()
        return True

    def reset_password(self, db: Session, phone: str, otp_code: str, new_password: str) -> User:
        """Réinitialise le mot de passe avec OTP"""
        
        # Vérifier l'OTP
        if not self.verify_otp(phone, otp_code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Code OTP invalide"
            )
        
        # Trouver l'utilisateur
        user = db.query(User).filter(User.phone == phone).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Utilisateur non trouvé"
            )
        
        # Changer le mot de passe
        user.password_hash = self.hash_password(new_password)
        
        db.commit()
        db.refresh(user)
        
        return user


# Instance globale du service
auth_service = AuthService()
