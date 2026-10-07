# InvoiceAI Pro — Backend (Phase 1)

A real, working invoice OCR + vendor risk intelligence backend, built for a final-year project.
This is **Phase 1**: the FastAPI backend, database, auth, OCR pipeline, and vendor risk engine.
The frontend (Next.js dashboard) is Phase 2 — see the note at the bottom.

## What's actually implemented (not stubbed)

- **JWT auth**: signup (creates a Company + admin User), login, refresh tokens, logout-all-devices, Argon2 password hashing
- **Multi-tenant isolation**: every business table has `company_id`; every query goes through `get_tenant_id()` so one company can never see another's data
- **File upload**: PDF/JPG/PNG/TIFF/BMP/WebP, size + extension validation
- **OCR pipeline**: Tesseract (fast path) with automatic EasyOCR fallback on low-confidence pages (handles rotated/low-quality scans), runs as a background task so uploads don't block
- **Field extraction**: regex/rule-based extraction of all the fields you listed (invoice no, GST, PAN, amounts, CGST/SGST/IGST, dates, bank details, etc.) — unmapped fields go into a JSON column
- **Validation**: duplicate detection, missing fields, bad GST format, future dates, negative amounts, invalid invoice numbers
- **Vendor Risk Engine**: exact rule from the spec — 1 delay = Normal, 2 = Medium Risk, 3+ = High Risk — with an audit trail of why a vendor's status changed
- **Dashboard API**: all the executive metrics (totals, trends, top/worst vendors, status breakdown) in one endpoint
- **Search/filter/export**: invoice list endpoint with full filtering, Excel export
- **RBAC**: Super Admin / Company Admin / Employee roles enforced via dependency injection
- **Docker Compose**: Postgres + Redis + backend, one command to run
- **Unit tests** for the validation and risk-scoring rules

## What's intentionally simplified (for an honest, working final-year scope)

- OCR uses free open-source engines (Tesseract/EasyOCR) with regex-based field extraction, not a paid LLM/vision API — accurate on clean invoices, will need manual correction on messy ones (that's what the `PATCH /invoices/{id}` endpoint and `needs_review` status are for)
- No Kubernetes/microservices/CDN — this is a single well-architected service that will comfortably handle a real demo and thousands of invoices, not literally millions on day one. The multi-tenant + indexed schema is designed so it *can* scale that way later.
- Email/OTP delivery is not wired to a real SMTP provider yet (endpoints exist, sending is a follow-up step — plug in SendGrid/SES)

## Running it

```bash
cd backend
cp .env.example .env        # edit JWT_SECRET_KEY at minimum
cd ..
docker compose up --build
```

Backend will be live at `http://localhost:8000`
Swagger docs: `http://localhost:8000/api/docs`

### Seed demo data (optional but recommended for your demo)

```bash
docker compose exec backend python -m app.db.seed_data
```

Then log in with `admin@acme.test` / `Demo@1234` via `POST /api/v1/auth/login`.

### Run tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

## Project structure

```
backend/
  app/
    core/       # config, database, security (JWT/Argon2), auth dependency
    models/     # SQLAlchemy models (Company, User, Invoice, Vendor, AuditLog...)
    schemas/    # Pydantic request/response schemas
    services/   # business logic: OCR, extraction, validation, risk engine, auth
    api/v1/     # route handlers (auth, invoices, vendors, dashboard)
    utils/      # file storage abstraction
    db/         # seed script
  tests/
  Dockerfile
  requirements.txt
docker-compose.yml
```

## Next steps (Phase 2 — say the word and I'll build it next)

- Next.js + TypeScript + Tailwind frontend: login/signup, upload UI with drag-drop, invoice review table, vendor risk dashboard with charts
- Nginx reverse proxy + production docker-compose overlay
- Alembic migrations (currently using `create_all` for simplicity — fine for a project, not for real prod schema changes)
