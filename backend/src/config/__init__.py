"""
Configuration de l'application
Gestion centralisée des variables d'environnement
"""
from typing import List
from decouple import config
from functools import lru_cache


class Settings:
    """Classe de configuration centralisée"""
    
    # Base de données
    DATABASE_URL: str = config('DATABASE_URL', default='postgresql://postgres:password@localhost:5333/covoiturage_dev')
    REDIS_URL: str = config('REDIS_URL', default='redis://localhost:6379')
    
    # JWT Configuration
    JWT_SECRET_KEY: str = config('JWT_SECRET_KEY', default='your_super_secret_jwt_key_here')
    JWT_ALGORITHM: str = config('JWT_ALGORITHM', default='HS256')
    ACCESS_TOKEN_EXPIRE_MINUTES: int = config('ACCESS_TOKEN_EXPIRE_MINUTES', default=30, cast=int)
    
    # API Keys
    CINETPAY_API_KEY: str = config('CINETPAY_API_KEY', default='')
    GOOGLE_MAPS_API_KEY: str = config('GOOGLE_MAPS_API_KEY', default='')
    SMS_PROVIDER_API_KEY: str = config('SMS_PROVIDER_API_KEY', default='')
    
    # App Settings
    DEBUG: bool = config('DEBUG', default=True, cast=bool)
    ALLOWED_HOSTS: List[str] = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')
    CORS_ORIGINS: List[str] = config('CORS_ORIGINS', default='http://localhost:3000,http://localhost:8080').split(',')
    
    # File Upload
    MAX_FILE_SIZE: int = config('MAX_FILE_SIZE', default=5242880, cast=int)  # 5MB
    UPLOAD_FOLDER: str = config('UPLOAD_FOLDER', default='uploads')
    
    # Sécurité
    SECRET_KEY: str = config('SECRET_KEY', default='dev-secret-key-change-in-production')
    
    # Pagination
    DEFAULT_PAGE_SIZE: int = config('DEFAULT_PAGE_SIZE', default=20, cast=int)
    MAX_PAGE_SIZE: int = config('MAX_PAGE_SIZE', default=100, cast=int)
    
    def __init__(self):
        # Validation des configurations critiques en mode production
        if not self.DEBUG:
            if self.JWT_SECRET_KEY == 'your_super_secret_jwt_key_here':
                raise ValueError("JWT_SECRET_KEY doit être changé en production!")
            if self.SECRET_KEY == 'dev-secret-key-change-in-production':
                raise ValueError("SECRET_KEY doit être changé en production!")


@lru_cache()
def get_settings() -> Settings:
    """
    Retourne une instance singleton des settings
    Le décorateur @lru_cache assure qu'on crée qu'une seule instance
    """
    return Settings()


# Instance globale pour import facile
settings = get_settings()