# LifeBoard — A Personal Resource Management System (PRMS)

**A unified, web-based platform to manage your Health, Tasks, and Finances all in one place.**

Academic Project for **IGNOU — Bachelor of Computer Applications (BCA)**  
Course Code: **BCSP-064** | Version: **1.0**  
Prepared By: **Aayush**

---

## 🌟 Key Features

1. **User Authentication & Role-Based Access Control**:
   - Secure registration, email uniqueness validation, and **SHA-256 password hashing** (FR-01 to FR-06).
   - Session-based authorization with automatic unauthenticated redirection and HTTP 403 enforcement for non-admin users.

2. **Unified Central Dashboard**:
   - 4 Interactive, clickable summary metric cards: Today's Workouts, Active Habit Streaks, Pending Tasks, and Monthly Finance.
   - 7-Day Workout Activity Chart (Chart.js) and real-time monthly budget progress bar with 80% caution and 100%+ danger alerts.
   - Upcoming tasks filter (due in the next 3 days) and last 5 recent expense transactions.

3. **Health & Physical Activity Module**:
   - Log workouts across 8 categorized activity types with duration, calories burned, and notes.
   - Computes total calories burned in the current week.
   - Daily habit tracker with consecutive daily streak increment and missed-day streak resets.
   - Real-time BMI Calculator and categorizer (Underweight, Normal, Overweight, Obese) with a 10-record historical tracking log.

4. **Schedule & Deadline Management Module**:
   - Create, edit, and filter tasks by status (All, Pending, In Progress, Done, Overdue).
   - Priority badges: Red (High), Orange (Medium), Green (Low).
   - Dynamic badges for **OVERDUE** and **Due Soon** (<24 hours).
   - Dual view toggle: **Table List View** and interactive **Kanban Board View** (Pending ➔ In Progress ➔ Done).

5. **Personal Finance Management Module**:
   - Log categorized expenses (Food, Transport, Health, Entertainment, Other) in Indian Rupees (₹).
   - Set monthly budget limits per user.
   - Automatic 80% spending warning banner and 100% overspending alert banner with exact deficit calculation ("Over Budget by ₹X").
   - Category-wise spending Doughnut/Pie chart and 7-day daily spending bar chart (Chart.js).

6. **"You" Personal Profile Tab**:
   - View and manage personal profile details (Full Name, Age, Phone Number, Bio, Email).
   - Lifetime accomplishment metrics (Total Workouts, Calories Burned, Tasks Done, Expenses Tracked, Longest Streak).
   - Password change and security controls.

7. **Consolidated Monthly Reports Generation**:
   - Printable HTML report combining Health & Fitness, Task Execution, and Financial Analytics.
   - Print-ready stylesheet (`@media print`) for 1-click PDF export.

8. **Admin Control Panel & System Audit Logs**:
   - Role-restricted (`admin` only) control panel displaying system-wide usage statistics.
   - User management table with account deletion and cascade integrity.
   - Live audit logging table recording system actions (registrations, logins, CRUD operations) with timestamps and details.

---

## 🛠️ Technology Stack

| Layer | Technology | Details |
|---|---|---|
| **Backend** | Python 3.10+ & Flask 3.x | Lightweight, robust WSGI framework |
| **Database** | SQLite 3 | Embedded RDBMS in 3NF with Foreign Keys, Cascades & Indexes |
| **Frontend** | HTML5, CSS3, ES6 JavaScript | Vanilla, zero build step, no npm dependency |
| **Data Visualization** | Chart.js 4.x (CDN) | Interactive, animated charts |
| **Icons & Typography**| Font Awesome 6.5 & Plus Jakarta Sans | Modern SaaS aesthetic |

---

## 🚀 Quick Start & Run Instructions

### 1. Requirements
- Python 3.10 or higher installed on your system.

### 2. Run the Application
From the `lifeboard` directory, run:
```bash
python app.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

### 3. Pre-Seeded Evaluation Accounts

| Role | Email | Password |
|---|---|---|
| **Demo User** | `aayush@lifeboard.com` | `user123` |
| **Administrator** | `admin@lifeboard.com` | `admin123` |

*Note: You can also register a brand new account anytime via the Registration page.*

---

## 🧪 Testing & Verification

A dedicated automated test suite is included in `test_app.py`. To execute all unit and integration tests:
```bash
python -m unittest test_app.py -v
```

---

## 📂 Project Architecture

```
lifeboard/
├── app.py                     # Main Flask routes and controllers
├── database.py                # SQLite connection, schema, indexes, seeder & audit logging
├── models.py                  # Domain logic, BMI, streaks, budget tracking, report queries
├── test_app.py                # Automated unit & integration test suite
├── lifeboard.db               # SQLite database file (auto-generated)
├── static/
│   ├── css/
│   │   ├── style.css          # Core SaaS design system
│   │   └── responsive.css     # Mobile (360px) to Desktop (1920px) styles
│   └── js/
│       ├── main.js            # UI handlers, modals, confirmations
│       ├── charts.js          # Chart.js visualization configs
│       └── modules.js         # Dynamic module interactions & BMI preview
└── templates/
    ├── base.html              # Master layout
    ├── index.html             # Landing page
    ├── auth/                  # Login & Registration
    ├── dashboard/             # Central Dashboard
    ├── health/                # Health & Fitness
    ├── tasks/                 # Tasks & Schedule
    ├── finance/               # Personal Finance
    ├── profile/               # "You" Profile Tab
    ├── reports/               # Monthly Reports
    ├── admin/                 # Administrator Panel
    └── errors/                # 403, 404, 500 error pages
```
