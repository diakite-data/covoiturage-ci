# 🚗 Covoiturage CI

Application de covoiturage pour la Côte d'Ivoire - Facilitant la mobilité urbaine durable.

## 🏗️ Architecture

- **Backend**: FastAPI + PostgreSQL + Redis
- **Mobile**: Flutter + Riverpod
- **Admin**: React + Vite
- **Base de données**: PostgreSQL avec Redis pour le cache

## 🚀 Démarrage rapide

### Prérequis
- Python 3.11+
- Flutter 3.10+
- Node.js 18+
- Docker & Docker Compose

### Installation

1. **Cloner le projet**
```bash
git clone <repo-url>
cd covoiturage-ci
```

2. **Démarrer les services (Docker)**
```bash
docker-compose up -d postgres redis
```

3. **Backend**
```bash
cd backend
source env_cov/bin/activate  # Linux/Mac
# ou env_cov\Scripts\activate  # Windows
pip install -r requirements.txt
cp .env.example .env
# Modifier les variables dans .env
uvicorn src.main:app --reload
```

4. **Mobile**
```bash
cd mobile
flutter pub get
flutter run
```

5. **Admin Dashboard**
```bash
cd admin-dashboard
npm install
npm run dev
```

## 📁 Structure du projet

```
covoiturage-ci/
├── backend/          # API FastAPI
├── mobile/           # App Flutter
├── admin-dashboard/  # Interface admin React
├── docs/            # Documentation
└── scripts/         # Scripts d'automatisation
```

## 🛠️ Technologies utilisées

### Backend
- FastAPI
- SQLAlchemy + Alembic
- PostgreSQL
- Redis
- Pydantic

### Mobile
- Flutter
- Riverpod
- Dio (HTTP)
- Google Maps

### Admin
- React + Vite
- Tailwind CSS
- React Query
- Recharts

## 📖 Documentation

- [API Documentation](docs/api/)
- [Guide de déploiement](docs/deployment/)
- [Guide utilisateur](docs/user-guide/)

## 🤝 Contribution

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/AmazingFeature`)
3. Commit (`git commit -m 'Add AmazingFeature'`)
4. Push (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## 📄 Licence

Ce projet est sous licence MIT - voir le fichier [LICENSE](LICENSE) pour plus de détails.
