# ExpenseIQ — Enterprise Personal Finance & Wealth Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.7%2B-blue.svg?logo=python&logoColor=white)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.x-092e20.svg?logo=django&logoColor=white)](https://djangoproject.com)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952b3.svg?logo=bootstrap&logoColor=white)](https://getbootstrap.com)
[![Tests](https://img.shields.io/badge/Tests-58%20Passed-10b981.svg)](#automated-testing)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**ExpenseIQ** is a full-featured personal finance and cash-flow intelligence suite built with Django, vanilla CSS design tokens, Bootstrap 5, and Chart.js. It features multi-tenant data isolation, dynamic threshold alert calculation, recurring subscription management, milestone savings goals, and bank statement CSV ingestion.

---

## 🌟 Key Features

- **🌓 Dual-Theme Engine (Dark / Light)**: High-contrast, glassmorphic UI with seamless theme switching and `localStorage` persistence.
- **📊 Real-Time Threshold Alert Engine**:
  - **Healthy (< 80%)**: Emerald progress indicators and positive safe runway.
  - **Warning (80% – 99%)**: Amber alert badges signaling budget exhaustion risks.
  - **Danger (≥ 100%)**: Critical crimson alerts calculating exact deficit/overspend.
- **💵 Income & Cash Flow Engine**: Log multi-channel earnings (Salary, Freelance, Dividends, Bonus) to compute real-time **Net Cash Flow** and **Savings Rate**.
- **🔄 Recurring Subscriptions Tracker**: Track SaaS licenses, streaming media, and utilities. Features **one-click "Mark as Paid"** automation that logs the expense and advances the next billing date by one month.
- **🎯 Financial Savings Goals**: Set target sums and milestones (Emergency Fund, Vacations, Tech), logging deposits with real-time visual progress bars.
- **📥 Intelligent Bank Statement CSV Importer**: Auto-matches flexible column names (`Date`, `Category`, `Amount`, `Notes`, `Payment Method`), handles currency symbols, and auto-provisions categories.
- **📈 Wealth Analytics Hub (`/analytics/`)**: 6-month historical cash-flow trends, spending velocity, and payment method distribution charts.
- **⚡ Power-User Keyboard Shortcuts**:
  - `E` — Quick log expense modal
  - `I` — Quick record income modal
  - `T` — Instant theme toggle (Dark / Light)
  - `?` — Keyboard shortcuts reference

---

## 🏗️ System Architecture

```text
expense_tracker/
├── manage.py
├── seed_demo.py               # Pre-configured demo data generator
├── generate_pdf_report.py     # Programmatic PDF documentation generator
├── requirements.txt           # Project dependencies
├── expense_tracker/           # Django project root (settings, urls, wsgi)
├── tracker/                   # Core application module
│   ├── models.py              # Category, Budget, Expense, Income, Subscription, FinancialGoal
│   ├── views.py               # CRUD views, CSV parser, analytics aggregation
│   ├── forms.py               # Model forms, validation rules, category choice resolver
│   ├── utils.py               # Budget calculations, thresholds, trends, insights
│   ├── urls.py                # RESTful endpoint routes
│   └── tests.py               # 58 automated unit and integration tests
└── templates/                 # Glassmorphic responsive templates
    ├── base.html              # Shell layout, navbar, FAB, shortcuts modal
    └── tracker/               # Dashboard, analytics, forms, list views
```

---

## 🚀 Quick Start Guide

### 1. Clone the Repository
```bash
git clone https://github.com/<your-username>/expense-tracker.git
cd expense-tracker
```

### 2. Set Up Virtual Environment
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run Database Migrations
```bash
python manage.py migrate
```

### 5. Seed Demonstration Data (Optional)
Populate realistic categories, budgets, incomes, expenses, subscriptions, and savings goals:
```bash
python seed_demo.py
```
> **Default Demo Login:**
> - **Username**: `demo`
> - **Password**: `password123`

### 6. Start the Server
```bash
python manage.py runserver
```
Visit **[http://127.0.0.1:8000/dashboard/](http://127.0.0.1:8000/dashboard/)** in your browser.

---

## 🧪 Automated Testing

ExpenseIQ includes a comprehensive test suite of **58 unit and integration tests** verifying threshold boundary conditions, multi-tenant isolation, negative amount protection, safe cascade deletion, CSV ingestion, and subscription payment automation:

```bash
python manage.py test
```

**Expected output:**
```text
Ran 58 tests in 21.857s
OK
System check identified no issues (0 silenced).
```

---

## 📄 Generating PDF Documentation

To generate a formal 9-page executive PDF report with embedded high-resolution screenshots, threshold matrices, and data schemas:

```bash
python generate_pdf_report.py
```
Output saved to `ExpenseIQ_Project_Documentation.pdf`.

---

## 🌐 Deploying Online (Free Hosting Options)

Because ExpenseIQ is a dynamic Django app with a database backend, you can host it online for free using one of the following providers connected to your GitHub repository:

### Option A: Render.com (Recommended)
1. Push this repository to GitHub.
2. Log into [Render.com](https://render.com) and create a **New Web Service**.
3. Select your GitHub repository.
4. Set **Build Command**: `pip install -r requirements.txt && python manage.py migrate`
5. Set **Start Command**: `gunicorn expense_tracker.wsgi:application`
6. Click **Deploy**.

### Option B: PythonAnywhere
1. Create a free account on [PythonAnywhere.com](https://www.pythonanywhere.com/).
2. Open a Bash console and clone your repo: `git clone https://github.com/<username>/expense-tracker.git`.
3. In the **Web** tab, configure a new Manual Configuration (Python 3.10 / Django), point the WSGI configuration to `expense_tracker/wsgi.py`, and reload.

---

## 📜 License
Distributed under the MIT License. See `LICENSE` for more information.
