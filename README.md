# OMI Global Productions

A creative hub dedicated to storytelling, wellness, and sustainability. Built with FastAPI and Tailwind CSS.

## Features

- 🎬 **Storytelling** - Narratives that move the soul
- 🧘 **Wellness** - Holistic practices for inner balance
- 🌱 **Sustainability** - Building a greener future

## Tech Stack

- **Backend**: Python 3.11+ with FastAPI
- **Database**: PostgreSQL (no ORM, raw SQL with psycopg2)
- **Frontend**: Tailwind CSS 3 (locally compiled, no CDN)
- **Templates**: Jinja2
- **Fonts**: Manrope & Material Symbols (locally hosted)

## Project Structure

```
omi-stitch/
├── app/
│   ├── main.py              # FastAPI application
│   ├── database.py          # PostgreSQL connection pool
│   ├── routers/             # API route handlers
│   ├── templates/           # Jinja2 HTML templates
│   └── static/
│       ├── css/             # Tailwind CSS files
│       ├── fonts/           # Local font files
│       ├── images/          # Image assets
│       └── js/              # JavaScript files
├── migrations/              # SQL migration files
├── requirements.txt         # Python dependencies
├── tailwind.config.js       # Tailwind configuration
└── package.json             # Node.js dependencies
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+

### Installation

1. **Clone and install Python dependencies:**
   ```bash
   cd omi-stitch
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Install Node.js dependencies (for Tailwind CSS):**
   ```bash
   npm install
   ```

3. **Configure environment:**
   ```bash
   cp env.example .env
   # Edit .env with your database credentials
   ```

4. **Initialize database:**
   ```bash
   # Create database
   createdb omi_stitch
   
   # Run migrations
   psql -d omi_stitch -f migrations/001_initial_schema.sql
   ```

5. **Build CSS (or watch for changes):**
   ```bash
   npm run css:build
   # Or for development:
   npm run css:watch
   ```

6. **Run the application:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

7. **Open in browser:**
   Visit [http://localhost:8000](http://localhost:8000)

## Development

### CSS Changes

When modifying Tailwind classes in templates, rebuild CSS:
```bash
npm run css:build
```

Or run in watch mode during development:
```bash
npm run css:watch
```

### Database Migrations

Create new migrations in `migrations/` folder with sequential numbering:
```
migrations/001_initial_schema.sql
migrations/002_add_feature.sql
```

Apply migrations manually:
```bash
psql -d omi_stitch -f migrations/XXX_migration_name.sql
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Landing page |
| GET | `/health` | Health check |
| GET | `/api/v1/pillars` | Get the three pillars |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | localhost | PostgreSQL host |
| `DB_PORT` | 5432 | PostgreSQL port |
| `DB_NAME` | omi_stitch | Database name |
| `DB_USER` | postgres | Database user |
| `DB_PASSWORD` | postgres | Database password |
| `DB_MIN_CONN` | 1 | Min pool connections |
| `DB_MAX_CONN` | 10 | Max pool connections |

## License

© 2024 OMI Hub. Consciously created for a better tomorrow.
