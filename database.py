"""
LifeBoard - Database Management Module
Handles SQLite connection, schema creation, data seeding, and relational queries.
Academic Project: IGNOU BCA BCSP-064
Author: Aayush
"""

import sqlite3
import os
import hashlib
from datetime import datetime, date, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lifeboard.db')

def get_db():
    """
    Establish a connection to the SQLite database.
    Enables foreign keys and returns dictionary-accessible rows.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def hash_password(password: str) -> str:
    """
    Hashes a plain-text password using SHA-256 (FR-02 requirement).
    """
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def init_db():
    """
    Initializes the database schema with 3NF relational tables,
    foreign key constraints, cascade rules, and performance indexes.
    """
    conn = get_db()
    cursor = conn.cursor()

    # 1. Users Table (FR-01, FR-02, FR-03, Profile Tab)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) NOT NULL,
        email VARCHAR(150) NOT NULL UNIQUE,
        password_hash VARCHAR(256) NOT NULL,
        role VARCHAR(10) DEFAULT 'user',
        phone VARCHAR(20),
        age INTEGER,
        bio TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Workout Log Table (FR-12, FR-13, FR-14)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS workout_log (
        workout_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        activity_type VARCHAR(50) NOT NULL,
        duration_mins INTEGER NOT NULL CHECK (duration_mins > 0),
        calories INTEGER NOT NULL CHECK (calories > 0),
        notes TEXT,
        log_date DATE NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """)

    # 3. Habit Tracker Table (FR-15, FR-16, FR-17)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS habit_tracker (
        habit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        habit_name VARCHAR(100) NOT NULL,
        streak_count INTEGER DEFAULT 0,
        last_completed_date DATE,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """)

    # 4. Habit Logs Table (Detailed history for streak calculations & reporting)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS habit_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        habit_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        completed_date DATE NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(habit_id, completed_date),
        FOREIGN KEY (habit_id) REFERENCES habit_tracker(habit_id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """)

    # 5. BMI Records Table (FR-18, FR-19, FR-20)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bmi_records (
        bmi_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        height_cm REAL NOT NULL,
        weight_kg REAL NOT NULL,
        bmi_value REAL NOT NULL,
        category VARCHAR(30) NOT NULL,
        recorded_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """)

    # 6. Tasks Table (FR-21 to FR-28)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        task_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title VARCHAR(100) NOT NULL,
        description TEXT,
        priority VARCHAR(10) NOT NULL CHECK (priority IN ('high', 'medium', 'low')),
        status VARCHAR(15) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'done')),
        deadline DATETIME NOT NULL,
        completed_at DATETIME,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """)

    # 7. Expense Log Table (FR-29, FR-30)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS expense_log (
        expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL NOT NULL CHECK (amount > 0),
        category VARCHAR(50) NOT NULL CHECK (category IN ('Food', 'Transport', 'Health', 'Entertainment', 'Other')),
        description TEXT,
        expense_date DATE NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """)

    # 8. Budget Table (FR-31)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS budget (
        budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        category VARCHAR(50) DEFAULT 'Overall',
        monthly_limit REAL NOT NULL CHECK (monthly_limit >= 0),
        month INTEGER NOT NULL CHECK (month BETWEEN 1 AND 12),
        year INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, month, year, category),
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
    );
    """)

    # 9. Audit Log Table (FR-42, FR-43)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        user_email VARCHAR(150),
        action VARCHAR(100) NOT NULL,
        module VARCHAR(50) NOT NULL,
        details TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
    );
    """)

    # Create Performance Indexes as documented in PRD
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_expense_user_date ON expense_log(user_id, expense_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_user_status_deadline ON tasks(user_id, status, deadline);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_workout_user_date ON workout_log(user_id, log_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_habits_user ON habit_tracker(user_id);")

    conn.commit()
    conn.close()

def seed_initial_data():
    """
    Seeds default administrative user and realistic demo data for presentation/evaluation.
    """
    conn = get_db()
    cursor = conn.cursor()

    # Check if admin exists
    cursor.execute("SELECT user_id FROM users WHERE email = ?", ('admin@lifeboard.com',))
    admin_row = cursor.fetchone()
    if not admin_row:
        # Default Admin (FR-39, Persona 3)
        admin_pass = hash_password('admin123')
        cursor.execute("""
        INSERT INTO users (name, email, password_hash, role, phone, age, bio)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('System Administrator', 'admin@lifeboard.com', admin_pass, 'admin', '+91 9876543210', 30, 'LifeBoard System Admin'))
        admin_id = cursor.lastrowid

        cursor.execute("""
        INSERT INTO audit_log (user_id, user_email, action, module, details)
        VALUES (?, ?, ?, ?, ?)
        """, (admin_id, 'admin@lifeboard.com', 'SYSTEM_INIT', 'Authentication', 'Initial admin account provisioned'))

    # Check if demo user (Aayush) exists
    cursor.execute("SELECT user_id FROM users WHERE email = ?", ('aayush@lifeboard.com',))
    user_row = cursor.fetchone()
    if not user_row:
        user_pass = hash_password('user123')
        cursor.execute("""
        INSERT INTO users (name, email, password_hash, role, phone, age, bio)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('Aayush Sharma', 'aayush@lifeboard.com', user_pass, 'user', '+91 9123456789', 21, 'Final Year BCA Student @ IGNOU. Fitness and tech enthusiast.'))
        uid = cursor.lastrowid

        today = date.today()
        now = datetime.now()

        # Seed Workouts for the past 7 days
        activities = [
            ('Gym', 60, 450, 'Chest & Triceps workout', today),
            ('Running', 30, 320, 'Morning 5km jog in the park', today - timedelta(days=1)),
            ('Cycling', 45, 380, 'Evening cycling ride', today - timedelta(days=2)),
            ('HIIT', 35, 400, 'High-intensity interval session', today - timedelta(days=3)),
            ('Yoga', 40, 180, 'Morning flexibility and mindfulness', today - timedelta(days=4)),
            ('Swimming', 45, 420, 'Lap swimming', today - timedelta(days=5)),
            ('Gym', 70, 510, 'Leg day & core', today - timedelta(days=6)),
        ]
        for act, dur, cal, notes, ldate in activities:
            cursor.execute("""
            INSERT INTO workout_log (user_id, activity_type, duration_mins, calories, notes, log_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (uid, act, dur, cal, notes, ldate.strftime('%Y-%m-%d')))

        # Seed Habits & Logs
        habits = [
            ('Morning 5km Run / Walk', 6, today),
            ('Drink 3L Water', 12, today),
            ('Read 20 Pages of Book', 4, today),
            ('30 mins Coding Practice', 8, today - timedelta(days=1))
        ]
        for hname, streak, lcomp in habits:
            cursor.execute("""
            INSERT INTO habit_tracker (user_id, habit_name, streak_count, last_completed_date)
            VALUES (?, ?, ?, ?)
            """, (uid, hname, streak, lcomp.strftime('%Y-%m-%d')))
            hid = cursor.lastrowid

            # Seed habit logs for past consecutive days
            for d_offset in range(streak):
                d_log = lcomp - timedelta(days=d_offset)
                cursor.execute("""
                INSERT OR IGNORE INTO habit_logs (habit_id, user_id, completed_date)
                VALUES (?, ?, ?)
                """, (hid, uid, d_log.strftime('%Y-%m-%d')))

        # Seed BMI records
        bmi_samples = [
            (175, 74.5, 24.3, 'Normal', today - timedelta(days=20)),
            (175, 73.8, 24.1, 'Normal', today - timedelta(days=10)),
            (175, 72.5, 23.7, 'Normal', today)
        ]
        for h, w, bval, cat, bdate in bmi_samples:
            cursor.execute("""
            INSERT INTO bmi_records (user_id, height_cm, weight_kg, bmi_value, category, recorded_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (uid, h, w, bval, cat, bdate.strftime('%Y-%m-%d %H:%M:%S')))

        # Seed Tasks
        tasks = [
            ('Complete IGNOU BCSP-064 Documentation', 'Finalize chapter 4 and chapter 5 data flow diagrams and project report.', 'high', 'in_progress', (now + timedelta(days=1)).strftime('%Y-%m-%d 18:00:00')),
            ('Review Flask Authentication & SHA-256 Hashing', 'Verify bcrypt/sha256 session management and edge case handling.', 'medium', 'done', (now - timedelta(days=1)).strftime('%Y-%m-%d 12:00:00')),
            ('Prepare LifeBoard Presentation Deck', 'Create 10-slide presentation for IGNOU viva examination.', 'high', 'pending', (now + timedelta(days=2)).strftime('%Y-%m-%d 15:00:00')),
            ('Submit Project Synopsis hard copy', 'Submit printed spiral bound project document at study centre.', 'low', 'pending', (now + timedelta(days=5)).strftime('%Y-%m-%d 11:00:00')),
            ('Buy Groceries & Protein Powder', 'Restock monthly nutritional essentials.', 'medium', 'pending', (now + timedelta(hours=14)).strftime('%Y-%m-%d %H:%M:%S')),
        ]
        for title, desc, prio, status, dline in tasks:
            cursor.execute("""
            INSERT INTO tasks (user_id, title, description, priority, status, deadline, completed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (uid, title, desc, prio, status, dline, now.strftime('%Y-%m-%d %H:%M:%S') if status == 'done' else None))

        # Seed Monthly Budget
        cur_month = today.month
        cur_year = today.year
        cursor.execute("""
        INSERT INTO budget (user_id, category, monthly_limit, month, year)
        VALUES (?, 'Overall', 18000.0, ?, ?)
        """, (uid, cur_month, cur_year))

        # Seed Expenses for current month
        expenses = [
            (3200.0, 'Food', 'Monthly grocery supplies and dining', today - timedelta(days=1)),
            (850.0, 'Transport', 'Metro recharge and auto rides', today - timedelta(days=2)),
            (2400.0, 'Health', 'Gym membership renewal & vitamins', today - timedelta(days=4)),
            (650.0, 'Entertainment', 'Movie tickets and streaming subscription', today - timedelta(days=6)),
            (1150.0, 'Other', 'Books and stationery supplies', today - timedelta(days=7)),
            (450.0, 'Food', 'Healthy lunch and juices', today),
        ]
        for amt, cat, desc, edate in expenses:
            cursor.execute("""
            INSERT INTO expense_log (user_id, amount, category, description, expense_date)
            VALUES (?, ?, ?, ?, ?)
            """, (uid, amt, cat, desc, edate.strftime('%Y-%m-%d')))

        # Seed audit log for registration
        cursor.execute("""
        INSERT INTO audit_log (user_id, user_email, action, module, details)
        VALUES (?, ?, 'USER_REGISTER', 'Authentication', 'Demo user account created')
        """, (uid, 'aayush@lifeboard.com'))

    conn.commit()
    conn.close()

def log_audit(user_id, user_email, action, module, details=""):
    """
    Helper function to record an action to the audit_log table.
    """
    try:
        conn = get_db()
        conn.execute("""
        INSERT INTO audit_log (user_id, user_email, action, module, details)
        VALUES (?, ?, ?, ?, ?)
        """, (user_id, user_email, action, module, details))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging audit: {e}")
