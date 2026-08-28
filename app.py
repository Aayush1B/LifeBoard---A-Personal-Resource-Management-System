"""
LifeBoard - A Personal Resource Management System (PRMS)
Main Flask Application & Routing Controller
Academic Project: IGNOU BCA BCSP-064
Author: Aayush
"""

import os
from functools import wraps
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, make_response, send_file

import database
from database import init_db, seed_initial_data, log_audit
import models

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'lifeboard_secure_dev_key_2026_ignou_bcsp064')

# Ensure database is initialized and seeded on startup
with app.app_context():
    init_db()
    seed_initial_data()

# -------------------------------------------------------------
# Authentication & Authorization Decorators
# -------------------------------------------------------------

def login_required(f):
    """
    Ensures user is authenticated before accessing protected routes (FR-05).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """
    Restricts access to users with role == 'admin'.
    Unauthenticated users are redirected to /login (FR-05).
    Authenticated non-admins receive HTTP 403 Forbidden (FR-39).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in as an administrator.', 'warning')
            return redirect(url_for('login', next=request.path))
        if session.get('role') != 'admin':
            return render_template('errors/403.html'), 403
        return f(*args, **kwargs)
    return decorated_function

@app.after_request
def add_security_headers(response):
    """
    Prevents caching of sensitive pages so back-button after logout does not restore session (FR-06).
    """
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.context_processor
def inject_global_variables():
    """
    Injects global template helpers and current user data across all templates.
    """
    current_user = None
    notifications = []
    if 'user_id' in session:
        current_user = models.get_user_by_id(session['user_id'])
        notifications = models.get_user_notifications(session['user_id'])

    return {
        'current_user': current_user,
        'notifications': notifications,
        'unread_notifications_count': len(notifications),
        'today_date': date.today().strftime('%A, %d %B %Y'),
        'current_year': date.today().year,
        'current_month': date.today().month,
        'now': datetime.now()
    }


# -------------------------------------------------------------
# Public & Authentication Routes (FR-01 to FR-06)
# -------------------------------------------------------------

@app.route('/')
def index():
    """
    Public landing page introducing LifeBoard. Redirects logged-in users to Dashboard.
    """
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles user login, credential verification, and session setup (FR-02, FR-04).
    """
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            flash('Please provide both email and password.', 'danger')
            return render_template('auth/login.html')

        user = models.get_user_by_email(email)
        if user and user['password_hash'] == models.hash_password(password):
            session.clear()
            session['user_id'] = user['user_id']
            session['name'] = user['name']
            session['email'] = user['email']
            session['role'] = user['role']

            log_audit(user['user_id'], user['email'], 'USER_LOGIN', 'Authentication', 'User logged in successfully')
            flash(f"Welcome back, {user['name']}!", 'success')

            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')

    return render_template('auth/login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles new user registration with password hashing and email uniqueness (FR-01, FR-02, FR-03).
    """
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()
        phone = request.form.get('phone', '').strip()
        age = request.form.get('age', '')

        # Validations
        if not name or not email or not password:
            flash('Please fill in all required fields.', 'danger')
            return render_template('auth/register.html')

        if password != confirm_password:
            flash('Passwords do not match. Please re-enter.', 'danger')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
            return render_template('auth/register.html')

        parsed_age = int(age) if age and age.isdigit() else None

        success, result = models.register_user(name, email, password, phone, parsed_age)
        if success:
            # Auto-login newly registered user
            session.clear()
            session['user_id'] = result
            session['name'] = name
            session['email'] = email
            session['role'] = 'user'

            flash('Registration successful! Welcome to your LifeBoard.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash(result, 'danger')

    return render_template('auth/register.html')

@app.route('/logout')
def logout():
    """
    Destroys active session completely and redirects to login (FR-06).
    """
    user_id = session.get('user_id')
    user_email = session.get('email', '')
    if user_id:
        log_audit(user_id, user_email, 'USER_LOGOUT', 'Authentication', 'User logged out')

    session.clear()
    flash('You have been logged out securely.', 'info')
    return redirect(url_for('login'))


# -------------------------------------------------------------
# Unified Dashboard Route (FR-07 to FR-11)
# -------------------------------------------------------------

@app.route('/dashboard')
@login_required
def dashboard():
    """
    Displays central dashboard with 4 clickable summary cards, workout chart,
    budget progress bar, upcoming tasks (3 days), and last 5 expenses.
    """
    user_id = session['user_id']
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')

    # Card 1: Today's Workouts & Weekly Calories
    weekly_cal_data = models.get_weekly_calories(user_id)
    all_workouts = models.get_user_workouts(user_id, limit=10)
    today_workouts = [w for w in all_workouts if w['log_date'] == today_str]
    today_cals = sum(w['calories'] for w in today_workouts)

    # Card 2: Active Habits & Streaks
    habits = models.get_user_habits(user_id)
    habits_done_today = sum(1 for h in habits if h['done_today'])
    total_habits = len(habits)
    max_streak = max([h['streak_count'] for h in habits], default=0)

    # Card 3: Pending Tasks & Overdue
    task_summary = models.get_task_summary(user_id)
    upcoming_tasks = models.get_upcoming_tasks(user_id, days=3)

    # Card 4: Monthly Finance & Budget
    fin_summary = models.get_financial_summary(user_id, today.month, today.year)
    recent_expenses = models.get_user_expenses(user_id, limit=5)

    # 7-day Workout Chart Data
    workout_chart = models.get_7day_workout_chart_data(user_id)

    # Category Spending Data for quick pie chart
    spending_pie = models.get_category_spending_chart_data(user_id, today.month, today.year)

    # Calculate LifeScore & AI Daily Briefing
    lifescore = models.calculate_lifescore(user_id)
    ai_briefing = models.get_ai_daily_briefing(user_id)

    # Activity Heatmap & Financial Projection
    heatmap_data = models.get_activity_heatmap_data(user_id)
    financial_projection = models.get_financial_projection(user_id, today.month, today.year)

    return render_template('dashboard/index.html',
                           today_workouts_count=len(today_workouts),
                           today_cals=today_cals,
                           weekly_cal_data=weekly_cal_data,
                           habits=habits,
                           habits_done_today=habits_done_today,
                           total_habits=total_habits,
                           max_streak=max_streak,
                           task_summary=task_summary,
                           upcoming_tasks=upcoming_tasks,
                           fin_summary=fin_summary,
                           recent_expenses=recent_expenses,
                           workout_chart=workout_chart,
                           spending_pie=spending_pie,
                           lifescore=lifescore,
                           ai_briefing=ai_briefing,
                           heatmap_data=heatmap_data,
                           financial_projection=financial_projection)


# -------------------------------------------------------------
# Health & Activity Module Routes (FR-12 to FR-20)
# -------------------------------------------------------------

@app.route('/health')
@login_required
def health():
    """
    Health & Activity module page with workout logs, habit streak tracking, and BMI calculator.
    """
    user_id = session['user_id']
    today = date.today()
    workouts = models.get_user_workouts(user_id)
    weekly_stats = models.get_weekly_calories(user_id)
    habits = models.get_user_habits(user_id)
    bmi_history = models.get_user_bmi_history(user_id)
    workout_chart = models.get_7day_workout_chart_data(user_id)

    return render_template('health/index.html',
                           workouts=workouts,
                           weekly_stats=weekly_stats,
                           habits=habits,
                           bmi_history=bmi_history,
                           workout_chart=workout_chart,
                           today_str=today.strftime('%Y-%m-%d'))

@app.route('/health/workout/add', methods=['POST'])
@login_required
def add_workout():
    """
    Logs a new workout entry (FR-12).
    """
    user_id = session['user_id']
    activity_type = request.form.get('activity_type', '').strip()
    duration_mins = request.form.get('duration_mins', '0')
    calories = request.form.get('calories', '0')
    notes = request.form.get('notes', '').strip()
    log_date = request.form.get('log_date', '').strip()

    try:
        duration_int = int(duration_mins)
        calories_int = int(calories)
        if duration_int <= 0 or calories_int <= 0:
            flash('Duration and Calories must be numbers greater than zero.', 'danger')
            return redirect(request.referrer or url_for('health'))
    except ValueError:
        flash('Please enter valid numeric values for duration and calories.', 'danger')
        return redirect(request.referrer or url_for('health'))

    success, msg = models.log_workout(user_id, activity_type, duration_int, calories_int, notes, log_date)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')

    return redirect(request.referrer or url_for('health'))

@app.route('/health/workout/delete/<int:workout_id>', methods=['POST'])
@login_required
def delete_workout(workout_id):
    """
    Deletes a workout entry with confirmation (FR-13).
    """
    user_id = session['user_id']
    success, msg = models.delete_workout(user_id, workout_id)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(request.referrer or url_for('health'))

@app.route('/health/habit/add', methods=['POST'])
@login_required
def add_habit():
    """
    Adds a new daily habit (FR-15).
    """
    user_id = session['user_id']
    habit_name = request.form.get('habit_name', '').strip()
    success, msg = models.add_habit(user_id, habit_name)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(request.referrer or url_for('health'))

@app.route('/health/habit/toggle/<int:habit_id>', methods=['POST'])
@login_required
def toggle_habit(habit_id):
    """
    Toggles habit completion for today and updates streak (FR-16, FR-17).
    Supports both AJAX and standard POST.
    """
    user_id = session['user_id']
    success, msg = models.toggle_habit_today(user_id, habit_id)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'success': success, 'message': msg})

    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(request.referrer or url_for('health'))

@app.route('/health/habit/delete/<int:habit_id>', methods=['POST'])
@login_required
def delete_habit(habit_id):
    user_id = session['user_id']
    success, msg = models.delete_habit(user_id, habit_id)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(request.referrer or url_for('health'))

@app.route('/health/bmi/calculate', methods=['POST'])
@login_required
def calculate_bmi():
    """
    Calculates BMI, categorizes, and saves record (FR-18, FR-19, FR-20).
    Supports AJAX and standard POST.
    """
    user_id = session['user_id']
    try:
        height_cm = float(request.form.get('height_cm', '0'))
        weight_kg = float(request.form.get('weight_kg', '0'))
    except ValueError:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'success': False, 'message': 'Invalid height or weight.'}), 400
        flash('Please enter valid numeric values for height and weight.', 'danger')
        return redirect(url_for('health'))

    success, msg, data = models.calculate_and_save_bmi(user_id, height_cm, weight_kg)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        if success:
            return jsonify({'success': True, 'message': msg, 'data': data})
        return jsonify({'success': False, 'message': msg}), 400

    if success:
        flash(f"BMI calculated: {data['bmi']} ({data['category']})", 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('health'))

@app.route('/health/bmi/delete/<int:bmi_id>', methods=['POST'])
@login_required
def delete_bmi(bmi_id):
    """
    Deletes a BMI calculation entry.
    """
    user_id = session['user_id']
    success, msg = models.delete_bmi_record(user_id, bmi_id)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('health'))


# -------------------------------------------------------------
# Schedule & Task Management Module Routes (FR-21 to FR-28)
# -------------------------------------------------------------

@app.route('/tasks')
@login_required
def tasks():
    """
    Schedule & Task Management page with priority color badges, overdue markers,
    filter tabs, and summary statistics.
    """
    user_id = session['user_id']
    filter_status = request.args.get('status', 'all').lower()
    view_mode = request.args.get('view', 'list') # 'list' or 'board'

    task_list = models.get_user_tasks(user_id, filter_status=filter_status)
    task_summary = models.get_task_summary(user_id)

    # Prepare board columns if Kanban view requested
    pending_tasks = [t for t in task_list if t['status'] == 'pending']
    in_progress_tasks = [t for t in task_list if t['status'] == 'in_progress']
    done_tasks = [t for t in task_list if t['status'] == 'done']

    return render_template('tasks/index.html',
                           tasks=task_list,
                           summary=task_summary,
                           current_filter=filter_status,
                           view_mode=view_mode,
                           pending_tasks=pending_tasks,
                           in_progress_tasks=in_progress_tasks,
                           done_tasks=done_tasks)

@app.route('/tasks/add', methods=['POST'])
@login_required
def add_task():
    """
    Creates a new task (FR-21).
    """
    user_id = session['user_id']
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    priority = request.form.get('priority', 'medium').lower()
    recurring = request.form.get('recurring', 'none').lower()
    deadline_date = request.form.get('deadline_date', '').strip()
    deadline_time = request.form.get('deadline_time', '23:59').strip()

    if not deadline_date:
        flash('Please select a deadline date.', 'danger')
        return redirect(request.referrer or url_for('tasks'))

    deadline = f"{deadline_date} {deadline_time}:00"

    success, msg = models.create_task(user_id, title, description, priority, deadline, recurring)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')

    return redirect(request.referrer or url_for('tasks'))

@app.route('/tasks/edit/<int:task_id>', methods=['POST'])
@login_required
def edit_task(task_id):
    """
    Edits task properties (FR-28).
    """
    user_id = session['user_id']
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    priority = request.form.get('priority', 'medium').lower()
    recurring = request.form.get('recurring', 'none').lower()
    deadline_date = request.form.get('deadline_date', '').strip()
    deadline_time = request.form.get('deadline_time', '23:59').strip()

    deadline = f"{deadline_date} {deadline_time}:00"
    success, msg = models.update_task(user_id, task_id, title, description, priority, deadline, recurring)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')

    return redirect(request.referrer or url_for('tasks'))

@app.route('/tasks/status/<int:task_id>', methods=['POST'])
@login_required
def update_task_status_route(task_id):
    """
    Updates task status (FR-27). Supports inline AJAX toggle.
    """
    user_id = session['user_id']
    new_status = request.form.get('status', 'pending')

    success, msg = models.update_task_status(user_id, task_id, new_status)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'success': success, 'message': msg})

    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')

    return redirect(request.referrer or url_for('tasks'))

@app.route('/tasks/delete/<int:task_id>', methods=['POST'])
@login_required
def delete_task_route(task_id):
    user_id = session['user_id']
    success, msg = models.delete_task(user_id, task_id)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(request.referrer or url_for('tasks'))


# -------------------------------------------------------------
# Personal Finance Module Routes (FR-29 to FR-38)
# -------------------------------------------------------------

@app.route('/finance')
@login_required
def finance():
    """
    Personal Finance module with monthly budget setting, expense logging,
    category pie chart, 7-day daily spending bar chart, and budget breach alerts.
    """
    user_id = session['user_id']
    today = date.today()

    # Allow filtering by month/year
    try:
        month = int(request.args.get('month', today.month))
        year = int(request.args.get('year', today.year))
    except ValueError:
        month = today.month
        year = today.year

    fin_summary = models.get_financial_summary(user_id, month, year)
    expenses = models.get_user_expenses(user_id, month, year, limit=100)
    category_chart = models.get_category_spending_chart_data(user_id, month, year)
    daily_chart = models.get_7day_spending_chart_data(user_id)

    return render_template('finance/index.html',
                           summary=fin_summary,
                           expenses=expenses,
                           category_chart=category_chart,
                           daily_chart=daily_chart,
                           categories=models.EXPENSE_CATEGORIES,
                           selected_month=month,
                           selected_year=year,
                           today_str=today.strftime('%Y-%m-%d'))

@app.route('/finance/expense/add', methods=['POST'])
@login_required
def add_expense():
    """
    Logs an expense (FR-29, FR-30).
    """
    user_id = session['user_id']
    amount_str = request.form.get('amount', '0')
    category = request.form.get('category', '').strip()
    description = request.form.get('description', '').strip()
    expense_date = request.form.get('expense_date', '').strip()

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash('Expense amount must be greater than zero.', 'danger')
            return redirect(request.referrer or url_for('finance'))
    except ValueError:
        flash('Please enter a valid numeric amount.', 'danger')
        return redirect(request.referrer or url_for('finance'))

    success, msg = models.log_expense(user_id, amount, category, description, expense_date)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')

    return redirect(request.referrer or url_for('finance'))

@app.route('/finance/expense/edit/<int:expense_id>', methods=['POST'])
@login_required
def edit_expense(expense_id):
    """
    Edits an existing expense record (FR-29, FR-30).
    """
    user_id = session['user_id']
    amount_str = request.form.get('amount', '0')
    category = request.form.get('category', '').strip()
    description = request.form.get('description', '').strip()
    expense_date = request.form.get('expense_date', '').strip()

    try:
        amount = float(amount_str)
        if amount <= 0:
            flash('Expense amount must be greater than zero.', 'danger')
            return redirect(request.referrer or url_for('finance'))
    except ValueError:
        flash('Please enter a valid numeric amount.', 'danger')
        return redirect(request.referrer or url_for('finance'))

    success, msg = models.update_expense(user_id, expense_id, amount, category, description, expense_date)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')

    return redirect(request.referrer or url_for('finance'))

@app.route('/finance/expense/delete/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense_route(expense_id):
    user_id = session['user_id']
    success, msg = models.delete_expense(user_id, expense_id)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(request.referrer or url_for('finance'))

@app.route('/finance/budget/set', methods=['POST'])
@login_required
def set_budget():
    """
    Sets or updates the monthly budget limit (FR-31).
    """
    user_id = session['user_id']
    budget_str = request.form.get('monthly_limit', '0')
    month = request.form.get('month')
    year = request.form.get('year')

    try:
        monthly_limit = float(budget_str)
        if monthly_limit <= 0:
            flash('Budget must be greater than zero.', 'danger')
            return redirect(request.referrer or url_for('finance'))
        m = int(month) if month else None
        y = int(year) if year else None
    except ValueError:
        flash('Please enter a valid numeric budget.', 'danger')
        return redirect(request.referrer or url_for('finance'))

    success, msg = models.set_monthly_budget(user_id, monthly_limit, m, y)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')

    return redirect(request.referrer or url_for('finance'))


# -------------------------------------------------------------
# "You" Personal Profile Tab (PRD Page 10 Requirement)
# -------------------------------------------------------------

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """
    Displays and edits user personal information (Name, Age, Email, Phone, Bio),
    lifetime accomplishment metrics, and password management.
    """
    user_id = session['user_id']
    user = models.get_user_by_id(user_id)

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_profile':
            name = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            age_str = request.form.get('age', '').strip()
            bio = request.form.get('bio', '').strip()

            if not name:
                flash('Name cannot be empty.', 'danger')
                return redirect(url_for('profile'))

            age = int(age_str) if age_str and age_str.isdigit() else None
            success, msg = models.update_user_profile(user_id, name, phone, age, bio, email)
            if success:
                session['name'] = name
                if email:
                    session['email'] = email
                flash(msg, 'success')
            else:
                flash(msg, 'danger')

        elif action == 'change_password':
            old_pass = request.form.get('old_password', '')
            new_pass = request.form.get('new_password', '')
            confirm_pass = request.form.get('confirm_password', '')

            if new_pass != confirm_pass:
                flash('New passwords do not match.', 'danger')
            else:
                success, msg = models.change_user_password(user_id, old_pass, new_pass)
                if success:
                    flash(msg, 'success')
                else:
                    flash(msg, 'danger')

        return redirect(url_for('profile'))

    # Lifetime metrics
    all_workouts = models.get_user_workouts(user_id, limit=1000)
    total_lifetime_calories = sum(w['calories'] for w in all_workouts)
    total_lifetime_workouts = len(all_workouts)

    task_summary = models.get_task_summary(user_id)
    all_expenses = models.get_user_expenses(user_id, limit=1000)
    total_lifetime_spent = sum(e['amount'] for e in all_expenses)

    habits = models.get_user_habits(user_id)
    max_streak = max([h['streak_count'] for h in habits], default=0)

    # Achievements & Activity Heatmap
    achievements = models.get_user_achievements(user_id)
    heatmap_data = models.get_activity_heatmap_data(user_id)

    return render_template('profile/index.html',
                           user=user,
                           total_lifetime_calories=total_lifetime_calories,
                           total_lifetime_workouts=total_lifetime_workouts,
                           task_summary=task_summary,
                           total_lifetime_spent=total_lifetime_spent,
                           max_streak=max_streak,
                           achievements=achievements,
                           heatmap_data=heatmap_data)


# -------------------------------------------------------------
# Monthly Reports Generation Module (Synopsis Section 5.5)
# -------------------------------------------------------------

@app.route('/reports')
@login_required
def reports():
    """
    Generates printable monthly HTML reports combining Health, Tasks, and Finance.
    """
    user_id = session['user_id']
    today = date.today()

    try:
        month = int(request.args.get('month', today.month))
        year = int(request.args.get('year', today.year))
    except ValueError:
        month = today.month
        year = today.year

    report_data = models.generate_monthly_report_data(user_id, month, year)

    return render_template('reports/index.html',
                           report=report_data,
                           selected_month=month,
                           selected_year=year)


# -------------------------------------------------------------
# Admin Control Panel Routes (FR-39 to FR-43)
# -------------------------------------------------------------

@app.route('/admin/verify', methods=['GET', 'POST'])
def admin_verify():
    """
    Dedicated Security Authentication checkpoint for Admin Panel.
    Requires explicit Admin Email and Password verification.
    """
    next_url = request.args.get('next', url_for('admin_panel'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not email or not password:
            flash('Both Administrator Email and Password are required.', 'danger')
            return render_template('auth/admin_verify.html', next=next_url)

        user = models.get_user_by_email(email)
        if user and user['password_hash'] == models.hash_password(password) and user['role'] == 'admin':
            session['user_id'] = user['user_id']
            session['name'] = user['name']
            session['email'] = user['email']
            session['role'] = 'admin'

            log_audit(user['user_id'], user['email'], 'ADMIN_VERIFY_SUCCESS', 'Admin', 'Admin credentials verified successfully')
            flash('Administrative access granted.', 'success')
            return redirect(next_url)
        else:
            log_audit(session.get('user_id'), email, 'ADMIN_VERIFY_FAILED', 'Admin', f"Failed admin access attempt with email '{email}'")
            flash('Access Denied: Invalid administrator credentials.', 'danger')

    return render_template('auth/admin_verify.html', next=next_url)

@app.route('/admin')
@admin_required
def admin_panel():
    """
    Administrator dashboard showing system statistics, user management, and audit logs.
    """
    stats = models.get_admin_system_stats()
    users = models.get_all_registered_users()
    logs = models.get_audit_logs(limit=50)

    return render_template('admin/index.html',
                           stats=stats,
                           users=users,
                           logs=logs)

@app.route('/admin/user/delete/<int:target_user_id>', methods=['POST'])
@admin_required
def admin_delete_user(target_user_id):
    """
    Allows admin to delete user accounts with cascade cleanup (FR-41).
    """
    admin_id = session['user_id']
    success, msg = models.delete_user_by_admin(admin_id, target_user_id)
    if success:
        flash(msg, 'success')
    else:
        flash(msg, 'danger')
    return redirect(url_for('admin_panel'))


# -------------------------------------------------------------
# AI Voice Command API Endpoint
# -------------------------------------------------------------

@app.route('/api/voice-command', methods=['POST'])
@login_required
def api_voice_command():
    """
    Processes spoken natural language commands from the Web Speech API and
    creates Workouts, Tasks, Expenses, or Habits in real-time.
    """
    user_id = session['user_id']
    data = request.get_json(silent=True) or request.form
    speech_text = data.get('speech_text', '').strip()

    if not speech_text:
        return jsonify({'success': False, 'message': 'No voice input provided.'}), 400

    success, msg, action_info = models.parse_and_execute_voice_command(user_id, speech_text)
    
    if success:
        return jsonify({
            'success': True,
            'message': msg,
            'action_info': action_info
        })
    else:
        return jsonify({
            'success': False,
            'message': msg
        }), 400


# -------------------------------------------------------------
# Multi-Domain Synchronized Calendar Route
# -------------------------------------------------------------

@app.route('/calendar')
@login_required
def calendar_view():
    """
    Displays integrated multi-domain calendar mapping Workouts, Tasks, and Expenses.
    """
    user_id = session['user_id']
    today = date.today()
    try:
        month = int(request.args.get('month', today.month))
        year = int(request.args.get('year', today.year))
    except ValueError:
        month = today.month
        year = today.year

    cal_data = models.get_calendar_events(user_id, month, year)
    return render_template('calendar/index.html',
                           cal_data=cal_data,
                           current_month=today.month,
                           current_year=today.year)


# -------------------------------------------------------------
# Data Export & Import (CSV / Excel) Routes
# -------------------------------------------------------------

@app.route('/export/csv/<module_name>')
@login_required
def export_csv(module_name):
    """
    Exports user data for specified module (workouts, tasks, finance) to CSV.
    """
    user_id = session['user_id']
    csv_content, filename = models.generate_csv_data(user_id, module_name)
    if not csv_content:
        flash('Invalid export module requested.', 'danger')
        return redirect(url_for('dashboard'))

    log_audit(user_id, session.get('email', ''), 'DATA_EXPORT_CSV', module_name.capitalize(), f"Exported {module_name} to CSV")
    response = make_response(csv_content)
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    return response

@app.route('/import/csv/<module_name>', methods=['POST'])
@login_required
def import_csv(module_name):
    """
    Imports user records from an uploaded CSV file.
    """
    user_id = session['user_id']
    if 'csv_file' not in request.files:
        flash('No file uploaded.', 'danger')
        return redirect(request.referrer or url_for('dashboard'))

    file = request.files['csv_file']
    if file.filename == '':
        flash('Please select a valid CSV file to upload.', 'warning')
        return redirect(request.referrer or url_for('dashboard'))

    try:
        csv_text = file.read().decode('utf-8')
        success, msg = models.import_csv_data(user_id, module_name, csv_text)
        if success:
            flash(msg, 'success')
        else:
            flash(msg, 'danger')
    except Exception as e:
        flash(f'Failed to process file: {str(e)}', 'danger')

    return redirect(request.referrer or url_for('dashboard'))


# -------------------------------------------------------------
# Admin Database Backup & Restore Routes
# -------------------------------------------------------------

@app.route('/admin/backup/download')
@admin_required
def download_database_backup():
    """
    Allows administrator to download a complete live snapshot of SQLite DB.
    """
    db_path = database.DB_PATH
    if not os.path.exists(db_path):
        flash('Database file not found.', 'danger')
        return redirect(url_for('admin_panel'))

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"lifeboard_backup_{timestamp}.db"
    return send_file(db_path, as_attachment=True, download_name=filename)

@app.route('/admin/backup/restore', methods=['POST'])
@admin_required
def restore_database_backup():
    """
    Allows administrator to upload and restore a database file.
    """
    if 'backup_file' not in request.files:
        flash('No backup file selected.', 'danger')
        return redirect(url_for('admin_panel'))

    file = request.files['backup_file']
    if file.filename == '' or not file.filename.endswith('.db'):
        flash('Please select a valid SQLite .db backup file.', 'warning')
        return redirect(url_for('admin_panel'))

    try:
        file.save(database.DB_PATH)
        log_audit(session['user_id'], session['email'], 'DB_RESTORE', 'Admin', 'Database restored from backup file')
        flash('Database successfully restored from backup snapshot.', 'success')
    except Exception as e:
        flash(f'Restore failed: {str(e)}', 'danger')

    return redirect(url_for('admin_panel'))


# -------------------------------------------------------------
# PWA Static Files Serving
# -------------------------------------------------------------

@app.route('/manifest.json')
def serve_manifest():
    return app.send_static_file('manifest.json')

@app.route('/sw.js')
def serve_sw():
    response = make_response(app.send_static_file('sw.js'))
    response.headers['Content-Type'] = 'application/javascript'
    return response


# -------------------------------------------------------------
# Error Handlers (404, 403, 500)
# -------------------------------------------------------------

@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html'), 500


# -------------------------------------------------------------
# Application Execution Entry Point
# -------------------------------------------------------------

if __name__ == '__main__':
    # host='0.0.0.0' allows access from localhost and any device on the same local network / Wi-Fi
    app.run(host='0.0.0.0', port=5000, debug=True)
