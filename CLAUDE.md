# SkogsplanSaaS - Project Guide

## Project Overview

SkogsplanSaaS is a Swedish forest management planning SaaS platform. It enables forest owners, consultants, and planners to create, manage, and share forest management plans (skogsbruksplaner) with geospatial data, field measurements, economic calculations, and PDF export.

## Tech Stack

- **Backend:** Python 3.12 / FastAPI / SQLAlchemy (async) / Alembic
- **Frontend:** React / TypeScript / MapLibre GL JS / Vite
- **Database:** PostgreSQL 16 + PostGIS 3.4
- **Cache:** Redis 7 (geodata response caching)
- **PDF Generation:** WeasyPrint
- **Geospatial:** GDAL, GEOS, PROJ, Shapely, GeoAlchemy2
- **Containerization:** Docker / Docker Compose
- **Reverse Proxy:** Nginx

## Directory Structure

```
Skogsplanering/
├── backend/               # FastAPI application
│   ├── app/               # Application package
│   │   ├── main.py        # FastAPI app entry point
│   │   ├── models/        # SQLAlchemy ORM models
│   │   ├── schemas/       # Pydantic request/response schemas
│   │   ├── routers/       # API route handlers
│   │   ├── services/      # Business logic layer
│   │   ├── core/          # Config, security, dependencies
│   │   └── utils/         # Helpers (geo transforms, PDF, etc.)
│   ├── alembic/           # Database migrations
│   ├── tests/             # Pytest test suite
│   ├── requirements.txt   # Python dependencies
│   └── Dockerfile
├── frontend/              # React/TypeScript application
│   ├── src/               # Source code
│   │   ├── components/    # React components
│   │   ├── pages/         # Page-level components
│   │   ├── hooks/         # Custom React hooks
│   │   ├── services/      # API client functions
│   │   ├── types/         # TypeScript type definitions
│   │   └── utils/         # Frontend utilities
│   ├── public/            # Static assets
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── nginx/                 # Reverse proxy config
│   └── nginx.conf
├── docker/                # Docker support files
│   └── init-db.sql        # Database initialization SQL
├── data/                  # Data directory (gitignored)
│   ├── rasters/           # Raster data (SHF, elevation)
│   ├── uploads/           # User uploads (photos)
│   └── pdfs/              # Generated PDF plans
├── shared/                # Shared types/constants
├── docker-compose.yml
├── Makefile               # Common dev commands
├── .env.example           # Environment variable template
└── CLAUDE.md              # This file
```

## How to Run

```bash
# First time: copy environment file
cp .env.example .env

# Start all services (builds containers on first run)
make dev
# or: docker-compose up --build

# Stop services
make stop

# Reset database (drops and recreates)
make db-reset

# View logs
make logs

# Open database shell
make shell
```

The application will be available at:
- Frontend: http://localhost (via nginx) or http://localhost:5173 (direct)
- API: http://localhost/api or http://localhost:8000
- Database: localhost:5432

## Key Domain Concepts

### Properties (Fastigheter)
A forest property corresponds to a real estate unit (fastighet) in the Swedish land registry. Identified by a designation like "Mora Smedby 1:5". Each property has a boundary geometry stored in SWEREF99 TM.

### Stands (Avdelningar / Bestand)
A stand is a contiguous area of forest with similar characteristics (species, age, density). Properties are divided into numbered stands. Each stand has detailed forest data: volume, height, basal area, species composition, age, and site index.

### Forest Plans (Skogsbruksplaner)
A forest management plan is the primary deliverable. It contains all stand data, proposed management actions, economic summaries, and maps. Plans can be exported as PDF and shared via token-based links.

### Target Classes (Malklasser)
Each stand is assigned a target class indicating its management objective:
- **PG** - Produktion med generell hansyn (Production with general conservation)
- **NS** - Naturvard skotsel (Nature conservation with management)
- **NO** - Naturvard orort (Nature conservation without management)
- **PF** - Produktion med forstarkt hansyn (Production with enhanced conservation)

### Management Actions (Atgardsforslag)
- **slutavverkning** - Final felling / clear cut
- **gallring** - Thinning
- **rojning** - Pre-commercial thinning (cleaning)
- **foryngring** - Regeneration (planting/seeding)
- **ingen** - No action

## Coordinate Systems

- **Storage:** SWEREF99 TM (EPSG:3006) - The Swedish national coordinate reference system. All geometries in PostGIS use this CRS.
- **Display:** WGS84 (EPSG:4326) - Used for map display in MapLibre. The API transforms coordinates between systems as needed.
- **Conversion:** Backend utilities handle CRS transformation via pyproj/Shapely. Frontend receives GeoJSON in EPSG:4326.

## API Routes Overview

```
POST   /auth/register          # User registration
POST   /auth/login             # JWT authentication
GET    /auth/me                # Current user profile

GET    /properties             # List user's properties
POST   /properties             # Create property (with GeoJSON boundary)
GET    /properties/{id}        # Get property details + stands
PUT    /properties/{id}        # Update property
DELETE /properties/{id}        # Delete property

GET    /properties/{id}/stands         # List stands for property
POST   /properties/{id}/stands         # Create stand
GET    /stands/{id}                    # Get stand details
PUT    /stands/{id}                    # Update stand data
DELETE /stands/{id}                    # Delete stand

POST   /stands/{id}/field-data         # Record field measurements
GET    /stands/{id}/field-data         # Get field data history

GET    /properties/{id}/plans          # List plans for property
POST   /properties/{id}/plans          # Create new plan
GET    /plans/{id}                     # Get plan details
PUT    /plans/{id}                     # Update plan
POST   /plans/{id}/publish             # Publish plan
GET    /plans/{id}/pdf                 # Generate/download PDF
GET    /plans/shared/{token}           # Access shared plan (public)

GET    /geo/skogsdatalaser/{property_id}   # Fetch SLU forest data
GET    /geo/property-boundary/{designation} # Fetch boundary from Lantmateriet
POST   /geo/import-shapefile               # Import stands from shapefile

GET    /analytics/property/{id}/summary    # Property summary statistics
GET    /analytics/property/{id}/economics  # Economic summary
```

## Swedish Forestry Terminology Glossary

| Swedish | English | Description |
|---------|---------|-------------|
| avdelning | stand | A contiguous forest compartment |
| bestand | stand data | The characteristics/data of a stand |
| skogsbruksplan | forest management plan | 10-year planning document |
| slutavverkning | final felling | Clear cutting mature forest |
| gallring | thinning | Selective removal to improve growth |
| rojning | pre-commercial thinning | Cleaning young dense forest |
| foryngring | regeneration | Establishing new forest after harvest |
| bonitet / SI | site index | Productive capacity of the land |
| malklass | target class | Management objective category (PG/NS/NO/PF) |
| relaskop | relascope | Basal area measurement instrument |
| grundyta | basal area | Cross-sectional area of stems per hectare (m2/ha) |
| volym | volume | Standing timber volume (m3sk) |
| tradslag | tree species | Species composition of a stand |
| tall | Scots pine | Pinus sylvestris |
| gran | Norway spruce | Picea abies |
| lov | deciduous | Broadleaf species |
| contorta | lodgepole pine | Pinus contorta |
| fastighet | property | Real estate unit |
| fastighetsbeteckning | property designation | Official property identifier |
| SHF | Skogliga Hojddata | Forest height data from laser scanning |
| skotsel | management | Forest management/silviculture |
| naturvard | nature conservation | Environmental protection measures |
| timmer | timber / sawlog | Large-diameter logs for lumber |
| massaved | pulpwood | Small-diameter logs for pulp/paper |
| barkborre | bark beetle | Ips typographus - major pest |

## Development Notes

- Use `make lint` to run linting (ruff for Python, eslint for TypeScript)
- Use `make test` to run the test suite
- Database migrations are managed with Alembic in `backend/alembic/`
- The init-db.sql creates the schema on first boot; subsequent changes should use Alembic migrations
- Redis caches geodata API responses to avoid redundant external calls
- File uploads (photos) go to the `data/uploads/` directory (volume-mounted)
- Generated PDFs are stored in `data/pdfs/`
