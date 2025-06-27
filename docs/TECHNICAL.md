# Technical Guide

## 1. Architecture Overview
- **Backend:** Django 5, Django REST Framework, Channels (ASGI), PostgreSQL, Redis
- **Frontend:** Vue 3, Vite, Vuetify, Axios
- **Deployment:** Docker, Kubernetes, Nginx, Gunicorn/Daphne
- **Domain:** https://nevadapub.co.ke

---

## 2. Project Structure
- **backend/**: Django project, modular apps (accounts, sales, inventory, etc.)
- **frontend/**: Vue 3 SPA, modular components, views, services
- **k8s/**: Kubernetes manifests (base, prod overlays)
- **docs/**: All documentation

---

## 3. API
- RESTful endpoints under `/api/v1/`
- JWT authentication, role-based permissions
- Real-time updates via WebSockets (Channels)
- See [Inventory API](inventory-api.md) and per-module docs

---

## 4. CI/CD (Recommended)
- Use GitHub Actions or GitLab CI for:
  - Linting, tests
  - Build Docker images
  - Push to registry
  - Deploy to Kubernetes (with secrets)
- Example workflow:
  - On push: build & test
  - On tag: build, push, deploy

---

## 5. Scaling & Performance
- Use Kubernetes HPA for auto-scaling
- Use Redis for cache and Channels
- Use Postgres with persistent storage
- Serve static/media via Nginx or cloud storage

---

## 6. Security
- Use strong secrets in production (see k8s secrets)
- Enable HTTPS (cert-manager, Let's Encrypt)
- Use CORS/CSRF protection (see Django settings)
- Restrict admin access by IP if needed
- Regularly update dependencies

---

## 7. Deployment
- See [SETUP.md](SETUP.md) for local/dev/prod instructions
- Use Docker Compose for local, Kubernetes for production
- Update image fields in k8s manifests for your registry
- Use Ingress for domain routing

---

## 8. Module Overview
- **Accounts:** User management, RBAC, authentication, OTP, biometrics
- **Inventory:** Products, batches, stock, expiry, suppliers
- **Sales:** Orders, payments, receipts, customer management
- **KDS:** Kitchen stations, real-time order tracking
- **HRM:** Employees, attendance, roles
- **Loyalty:** Points, tiers, gift cards
- **Tables:** Floor plan, reservations
- **Reporting:** Analytics, exports, dashboard
- **Accounting:** Expenses, revenue, financials

---

## 9. References
- [Feature Analysis](feature_analysis.md)
- [System Plan](plan.md)
- [Inventory API](inventory-api.md)
- [Accounting Module](accounting.md) 