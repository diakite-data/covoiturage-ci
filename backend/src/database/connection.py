"""
Configuration de la base de données PostgreSQL
Gestion des sessions SQLAlchemy et connexion Redis
"""
import os
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
import redis
from decouple import config

# Configuration depuis les variables d'environnement
DATABASE_URL = config('DATABASE_URL', default='postgresql://postgres:password@localhost:5433/covoiturage_dev')
REDIS_URL = config('REDIS_URL', default='redis://localhost:6379')

# Configuration SQLAlchemy
engine = create_engine(
    DATABASE_URL,
    poolclass=StaticPool,
    pool_pre_ping=True,  # Vérification automatique des connexions
    pool_recycle=300,    # Recyclage des connexions toutes les 5 minutes
    echo=config('DEBUG', default=True, cast=bool)  # Log des requêtes SQL en mode debug
)

# Session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base pour les modèles
Base = declarative_base()

# Configuration Redis
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    # Test de connexion Redis
    redis_client.ping()
    print("✅ Connexion Redis établie")
except Exception as e:
    print(f"❌ Erreur connexion Redis: {e}")
    redis_client = None


def get_db() -> Generator[Session, None, None]:
    """
    Générateur de session de base de données
    Utilisé comme dépendance FastAPI pour injecter la session DB
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_redis():
    """
    Retourne le client Redis
    """
    return redis_client


def test_db_connection() -> dict:
    """
    Test de connexion à la base de données
    Retourne le statut de la connexion
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1 as test"))
            test_value = result.fetchone()[0]
            
            if test_value == 1:
                return {
                    "status": "success",
                    "message": "Connexion PostgreSQL établie",
                    "database_url": DATABASE_URL.split('@')[-1]  # Masquer les credentials
                }
            else:
                return {
                    "status": "error",
                    "message": "Test de connexion échoué"
                }
                
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur de connexion: {str(e)}"
        }


def test_redis_connection() -> dict:
    """
    Test de connexion à Redis
    """
    try:
        if redis_client:
            redis_client.ping()
            return {
                "status": "success",
                "message": "Connexion Redis établie",
                "redis_url": REDIS_URL
            }
        else:
            return {
                "status": "error",
                "message": "Client Redis non initialisé"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur Redis: {str(e)}"
        }


def init_database():
    """
    Initialise la base de données
    Crée les tables si elles n'existent pas
    """
    try:
        # Import des modèles ici pour éviter les imports circulaires
        from src.models import User, Trip, Reservation, Base as ModelsBase
        
        # Utiliser la Base des modèles au lieu de celle de database
        print(f"📋 Tables à créer/vérifier: {list(ModelsBase.metadata.tables.keys())}")
        
        ModelsBase.metadata.create_all(bind=engine)
        print("✅ Tables de base de données créées/vérifiées")
        
        # Vérification des tables créées
        with engine.connect() as connection:
            result = connection.execute(text("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """))
            tables = [row[0] for row in result.fetchall()]
            print(f"📊 Tables existantes: {tables}")
        
        return True
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation de la DB: {e}")
        import traceback
        traceback.print_exc()
        return False


# Fonction utilitaire pour les tests
def get_db_for_testing():
    """
    Version synchrone pour les tests
    """
    db = SessionLocal()
    try:
        return db
    finally:
        db.close()


if __name__ == "__main__":
    """
    Script de test pour vérifier les connexions
    Usage: python -m src.database.connection
    """
    print("🔍 Test des connexions...")
    
    # Test PostgreSQL
    db_result = test_db_connection()
    print(f"PostgreSQL: {db_result}")
    
    # Test Redis  
    redis_result = test_redis_connection()
    print(f"Redis: {redis_result}")
    
    # Test d'initialisation
    if db_result["status"] == "success":
        init_success = init_database()
        print(f"Initialisation DB: {'✅ Succès' if init_success else '❌ Échec'}")