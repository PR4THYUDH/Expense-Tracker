# 💳 FinTrack AI — Intelligent Personal Expense Management

[![Django](https://img.shields.io/badge/Django-6.0-092E20?logo=django)](https://www.djangoproject.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python)](https://www.python.org/)
[![Anthropic Claude](https://img.shields.io/badge/Claude-3.5%20Sonnet-D97706?logo=anthropic)](https://www.anthropic.com/)
[![Plotly](https://img.shields.io/badge/Plotly-Interactive-3F4F75?logo=plotly)](https://plotly.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A production-ready, full-stack personal finance and expense management platform built with **Django 6**, **Pandas**, **Plotly**, and **Anthropic's Claude 3.5 Sonnet**. 

Designed for individuals and professionals seeking automated receipt scanning, real-time budget monitoring, and conversational financial intelligence with strict multi-tenant privacy guarantees.

---

## 🌟 Key Features

### 1. 📊 Interactive Analytics & KPI Dashboard
* **Dynamic Visualizations:** Time-series spending trends and category distribution donut charts rendered dynamically with **Plotly Express** and **Pandas**.
* **Month-over-Month Benchmarking:** Automated calculation of current vs. previous calendar month spending with directional change percentages.
* **Granular Filtering:** Real-time filtering by custom date ranges, standardized categories, and keyword searches across merchants and notes.

### 2. 🎯 Budgeting & Trajectory Alerts
* **Monthly Allocation Targets:** Set custom budget ceilings for any month and year.
* **Proactive Warning System:** Visual progress bars with threshold alerts at 80% capacity and danger banners when budgets are exceeded.
* **Safe Database Derivation:** All budget statistics are computed in real time from the database.

### 3. 🤖 Genuine Anthropic Claude AI Capabilities
* **📸 Multimodal Receipt Scanning (Claude Vision):** Upload photos of physical or digital receipts. Claude extracts merchant name, date, itemized lines, taxes, and totals into an editable form for explicit review *before* saving.
* **💡 Objective Spending Observations:** Claude analyzes aggregated monthly numbers and category shifts to deliver 3–4 concise, actionable financial takeaways without hallucinating figures.
* **💬 Natural Language Assistant ("Ask Claude"):** Ask questions like *"What did I spend the most on this month?"* or *"Did my dining expenses increase?"*. The application executes verified backend data queries and passes structured snapshots to Claude—**arbitrary SQL execution is strictly prohibited**.
* **🛡️ Graceful Keyless Fallback:** If `ANTHROPIC_API_KEY` is not configured, the platform functions with a clear UI advisory rather than crashing.

### 4. 📥 CSV Export & Strict Multi-Tenant Security
* **User Isolation:** All records are scoped to `request.user`. User A cannot view, update, delete, or export User B's financial records.
* **Filtered Exports:** Export your personal transaction history to standard CSV files matching your active dashboard filters.

---

## 🏗️ Architecture

```
User (Browser)
    │
    ├── Django Views & Authentication (CSRF, Sessions)
    │       │
    │       ├── Scoped Relational ORM (PostgreSQL / SQLite)
    │       │       ├── Expense Model (amount, category, vendor, date)
    │       │       └── Budget Model (user, month, year, amount)
    │       │
    │       ├── Analytics Service (Pandas Aggregation & Plotly Charts)
    │       │
    │       └── Claude AI Service (Official Anthropic SDK)
    │               ├── Receipt Vision OCR (Pre-save validation)
    │               ├── Aggregated Financial Insights
    │               └── Controlled Natural Language Q&A
```

---

## 🛠️ Tech Stack

* **Backend Framework:** Django 6.0
* **Data Processing & Analytics:** Pandas 2.3, NumPy 2.3, Plotly 6.5
* **AI & LLM:** Anthropic Python SDK (`claude-3-5-sonnet-20241022`)
* **Styling & UI:** Tailwind CSS, Responsive Flex/Grid, Accessible Modals
* **Production Deployment:** Gunicorn, WhiteNoise 6.11, `dj-database-url`, `psycopg2-binary`
* **Test Suite:** `pytest`, `pytest-django` (21 automated tests)

---

## 🚀 Getting Started Locally

### 1. Clone Repository & Setup Virtual Environment
```bash
git clone https://github.com/PR4THYUDH/Expense-Tracker.git
cd Expense-Tracker

python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your settings:
```ini
DEBUG=True
SECRET_KEY=local-dev-secret-key-change-in-production
ALLOWED_HOSTS=127.0.0.1,localhost
DATABASE_URL=
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```
*(Leave `DATABASE_URL` empty to automatically use local SQLite).*

### 4. Apply Migrations & Run Development Server
```bash
python manage.py migrate
python manage.py runserver
```
Visit `http://127.0.0.1:8000/` in your browser.

---

## 🧪 Running Automated Tests

Run the complete 21-test suite verifying authentication, user isolation, CRUD operations, budgeting, CSV export, and Claude AI service mocks:

```bash
pytest -v
```

---

## 🌐 Production Deployment Guide

### Recommended Platform: Railway (or Render / Fly.io)

1. **Connect GitHub:** Link your `PR4THYUDH/Expense-Tracker` repository to Railway.
2. **Add PostgreSQL:** Add a PostgreSQL database plugin in your project dashboard (Railway automatically sets `DATABASE_URL`).
3. **Configure Environment Variables:**
   * `DEBUG`: `False`
   * `SECRET_KEY`: `<Generate a random 50+ character string>`
   * `ALLOWED_HOSTS`: `.up.railway.app,yourdomain.com`
   * `CSRF_TRUSTED_ORIGINS`: `https://*.up.railway.app,https://yourdomain.com`
   * `ANTHROPIC_API_KEY`: `<Your Anthropic API key>`
4. **Deploy:** Railway utilizes `railway.toml` and `Procfile` to run migrations, collect static assets, and boot Gunicorn automatically.

---

## 🔒 Security & Privacy Statement

* **Zero Arbitrary SQL:** Claude is never given direct access or raw query execution privileges over the database.
* **Minimized Payloads:** Only high-level mathematical aggregations are transmitted for AI insights; bank credentials and sensitive account identifiers are never transmitted.
* **Review Before Commit:** Multimodal receipt extractions are presented in an editable modal and require affirmative user confirmation before saving to the database.

---

## 👨‍💻 Author

**Prathyudh Prem**  
* GitHub: [@PR4THYUDH](https://github.com/PR4THYUDH)
