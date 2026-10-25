# Modern Hostel Management System (Flask)

A comprehensive, modular Flask application for automating hostel operations, room allocations, student registrations, fee collections, payment reconciliation, and administrative analytics.

![Python](https://img.shields.io/badge/Python-3.12+-blue?style=for-the-badge&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.x-black?style=for-the-badge&logo=flask)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-red?style=for-the-badge)
![Alembic](https://img.shields.io/badge/Database-Migrations-brightgreen?style=for-the-badge)

---

## 🏢 Features

- **Role-Based Access Control (RBAC):** Dedicated administrative dashboards vs student/resident self-service portals.
- **Room & Bed Allocation Management:** Real-time occupancy tracking, room availability states (available, full, maintenance), and automated assignments.
- **Billing & Fee Invoicing:** Automated fee generation, status tracking (`pending`, `partial`, `paid`, `overdue`), and payment recording.
- **Security & Reliability:** CSRF protection with Flask-WTF, rate limiting with Flask-Limiter, and structured error handling.
- **Database Migrations:** Schema evolution managed via Alembic & Flask-Migrate.
- **Presentation Decks Included:** Presentation slide generators and workflow guides for stakeholders.

---

## 🚀 Quick Start

### 1. Prerequisites
- Python 3.10+
- Virtual environment tool (`venv`)

### 2. Setup

```bash
# Clone the repository
git clone https://github.com/tatikondasai2006-debug/Hostel-Management-System-Flask.git
cd Hostel-Management-System-Flask

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
```

### 3. Initialize Database & Run

```bash
# Apply database migrations
flask db upgrade

# Run development server
python run.py
```

Visit `http://localhost:5000` to access the portal.

---

## 🧪 Testing & Code Quality

```bash
# Run test suite
pytest

# Run linter
ruff check .
```

---

## 📄 License

This project is licensed under the MIT License.
