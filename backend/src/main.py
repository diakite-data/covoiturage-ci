"""
Application FastAPI principale - Covoiturage CI
Point d'entrée de l'API
"""
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware  # ← NOUVEAU !
from sqlalchemy.orm import Session
from decouple import config
import uvicorn

# Imports internes
from src.database import get_db, test_db_connection, test_redis_connection
from src.config import get_settings
from src.routers import auth, trip, reservation, geo

# Configuration
settings = get_settings()

# Création de l'application FastAPI
app = FastAPI(
    title="Covoiturage CI API",
    description="API pour l'application de covoiturage en Côte d'Ivoire",
    version="1.0.0",
    docs_url="/docs",  # Documentation Swagger
    redoc_url="/redoc"  # Documentation ReDoc
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inclusion des routers
app.include_router(auth.router)
app.include_router(trip.router) 
app.include_router(reservation.router)
app.include_router(geo.router)

# Routes de santé et de test
@app.get("/")
async def root():
    """Point d'entrée de l'API"""
    return {
        "message": "Bienvenue sur l'API Covoiturage CI! 🚗",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Vérification de l'état de santé de l'API"""
    return {
        "status": "healthy",
        "service": "covoiturage-api",
        "timestamp": "2025-06-27T15:00:00Z"
    }


@app.get("/health/db")
async def database_health():
    """Vérification de l'état des bases de données"""
    
    # Test PostgreSQL
    db_status = test_db_connection()
    
    # Test Redis
    redis_status = test_redis_connection()
    
    # Statut global
    overall_status = "healthy" if (
        db_status["status"] == "success" and 
        redis_status["status"] == "success"
    ) else "unhealthy"
    
    return {
        "status": overall_status,
        "postgresql": db_status,
        "redis": redis_status
    }


@app.get("/health/detailed")
async def detailed_health(db: Session = Depends(get_db)):
    """Vérification détaillée avec test de requête"""
    try:
        # Test d'une requête simple pour vérifier la session
        result = db.execute("SELECT 1 as test")
        test_value = result.fetchone()[0]
        
        db_detailed = {
            "status": "success",
            "message": "Session DB active",
            "test_query": f"SELECT 1 = {test_value}"
        }
        
    except Exception as e:
        db_detailed = {
            "status": "error", 
            "message": f"Erreur session DB: {str(e)}"
        }
    
    return {
        "status": "healthy" if db_detailed["status"] == "success" else "unhealthy",
        "database_session": db_detailed,
        "environment": {
            "debug": settings.DEBUG,
            "database_url": settings.DATABASE_URL.split('@')[-1]  # Masquer credentials
        }
    }


# Routes API principales (à développer)
@app.get("/api/v1/status")
async def api_status():
    """Status de l'API v1"""
    return {
        "api_version": "v1",
        "endpoints": {
            "auth": "/api/v1/auth/*",
            "users": "/api/v1/users/*", 
            "trips": "/api/v1/trips/*",
            "reservations": "/api/v1/reservations/*"
        },
        "status": "development"
    }


# Gestion globale des erreurs
from fastapi.responses import JSONResponse

@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Endpoint non trouvé",
            "message": f"L'endpoint {request.url.path} n'existe pas",
            "available_endpoints": [
                "/", "/health", "/health/db", "/docs", "/api/v1/status"
            ]
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Erreur interne du serveur",
            "message": "Une erreur s'est produite. Consultez les logs.",
            "contact": "support@covoiturage-ci.com"
        }
    )


if __name__ == "__main__":
    """
    Démarrage de l'application en mode développement
    Usage: python src/main.py
    """
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Rechargement automatique en dev
        log_level="info"
    )