# Setup & Deployment Guide

## Overview
This guide covers local development, Docker Compose, Kubernetes, and production deployment on Contabo VPS (domain: nevadapub.co.ke).

---

## 1. Local Development

### Prerequisites
- Python 3.11+
- Node.js 22+
- PostgreSQL 15+
- Redis 7+
- npm/yarn/pnpm

### Backend
```sh
cd backend
python -m venv env
source env/bin/activate  # or .\env\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env  # Set environment variables
python manage.py migrate
python manage.py runserver
```

### Frontend
```sh
cd frontend
npm install
npm run dev
```

---

## 2. Docker Compose (Recommended for Local Dev)
```sh
./deploy-local.sh
# Frontend: http://localhost:8080
# Backend: http://localhost:8000/api/v1/
```

---

## 3. Kubernetes (Local or Production)

### Local (minikube/kind)
- The Ingress is set to `kitchenbloom.local`.
- Add this to your `/etc/hosts`:
  ```
  127.0.0.1 kitchenbloom.local
  ```
- Access the app at http://kitchenbloom.local
- No TLS/HTTPS by default for local.

#### **Full Local Build & Deploy**
To build Docker images, load them into your local Kubernetes (minikube/kind), and deploy:
```sh
./deploy-k8s-local-full.sh
```

### Production (Contabo VPS)
- The Ingress is set to `nevadapub.co.ke` and includes TLS (HTTPS) via cert-manager.
- Set up DNS for nevadapub.co.ke to point to your VPS IP.
- Ensure cert-manager is installed for automatic Let's Encrypt SSL.
- Build and push Docker images to registry.
- Update image fields in k8s manifests.
- Run:
```sh
./deploy-k8s-prod-full.sh
```
- Access app at https://nevadapub.co.ke

---

## 4. Nginx Configuration (Frontend)
- The frontend Docker image uses Nginx to serve the SPA and proxy `/api` to the backend.
- This config works for both local (Docker Compose, K8s) and production (K8s Ingress).
- No changes needed between environments as long as service names are consistent.

---

## 5. Environment Variables
- See `backend/config/settings.py` for all Django envs
- See `frontend/.env.example` for frontend envs

---

## 6. HTTPS (Production)
- Uses cert-manager and Let's Encrypt for automatic SSL.
- Ingress manifest includes TLS section for production.

---

## 7. Troubleshooting
- Check logs: `docker compose logs -f` or `kubectl logs ...`
- Common issues: DB connection, static/media permissions, CORS, HTTPS

---

## 8. Useful Links
- [Kubernetes Docs](https://kubernetes.io/docs/)
- [Docker Docs](https://docs.docker.com/)
- [Cert-Manager](https://cert-manager.io/)
- [Contabo VPS](https://contabo.com/) 