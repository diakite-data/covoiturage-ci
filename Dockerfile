# Dockerfile pour le backend FastAPI
FROM python:3.11-slim

# Définir le répertoire de travail
WORKDIR /app

# Installer les dépendances système
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de requirements
COPY requirements.txt .

# Créer et activer l'environnement virtuel
RUN python -m venv env_cov
RUN /app/env_cov/bin/pip install --upgrade pip
RUN /app/env_cov/bin/pip install -r requirements.txt

# Copier le code source
COPY . .

# Exposer le port
EXPOSE 8000

# Définir les variables d'environnement
ENV PYTHONPATH=/app
ENV PATH="/app/env_cov/bin:$PATH"

# Commande pour démarrer l'application
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]