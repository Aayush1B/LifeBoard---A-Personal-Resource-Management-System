"""
LifeBoard - Data Models & Business Logic Module
Contains domain logic, streak computation, BMI calculation, budget tracking,
and query abstractions for all modules.
Academic Project: IGNOU BCA BCSP-064
Author: Aayush
"""

from datetime import datetime, date, timedelta
from database import get_db, hash_password, log_audit

# ==========================================
# 1. USER & AUTHENTICATION BUSINESS LOGIC
# ==========================================

def get_user_by_email(email: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),))
    user = cursor.fetchone()
    conn.close()
    return user

def get_user_by_id(user_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def register_user(name: str, email: str, password: str, phone: str = "", age: int = None, bio: str = ""):
    """
    Registers a new user, hashes password with SHA-256 (FR-02) and verifies email uniqueness (FR-03).
    """
    if not name or not email or not password:
        return False, "All required fields must be filled."
    
    email = email.strip().lower()
    if get_user_by_email(email):
        return False, "An account with this email already exists."

    pwd_hash = hash_password(password)
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO users (name, email, password_hash, role, phone, age, bio)
        VALUES (?, ?, ?, 'user', ?, ?, ?)
        """, (name.strip(), email, pwd_hash, phone.strip(), age, bio.strip()))
        user_id = cursor.lastrowid

        # Set a default initial monthly budget of ₹15,000
        today = date.today()
        cursor.execute("""
        INSERT OR IGNORE INTO budget (user_id, category, monthly_limit, month, year)
        VALUES (?, 'Overall', 15000.0, ?, ?)
        """, (user_id, today.month, today.year))

        conn.commit()
        log_audit(user_id, email, 'USER_REGISTER', 'Authentication', 'New user registered successfully')
        return True, user_id
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def update_user_profile(user_id: int, name: str, phone: str, age: int, bio: str, email: str = None):
    conn = get_db()
    cursor = conn.cursor()
    try:
        if email:
            email_clean = email.strip().lower()
            if not email_clean:
                return False, "Email address cannot be empty."
            
            # Check if email belongs to another user
            cursor.execute("SELECT user_id FROM users WHERE LOWER(email) = LOWER(?) AND user_id != ?", (email_clean, user_id))
            existing = cursor.fetchone()
            if existing:
                return False, "This email address is already in use by another account."

            cursor.execute("""
            UPDATE users
            SET name = ?, email = ?, phone = ?, age = ?, bio = ?
            WHERE user_id = ?
            """, (name.strip(), email_clean, phone.strip(), age, bio.strip(), user_id))
        else:
            cursor.execute("""
            UPDATE users
            SET name = ?, phone = ?, age = ?, bio = ?
            WHERE user_id = ?
            """, (name.strip(), phone.strip(), age, bio.strip(), user_id))

        conn.commit()
        log_audit(user_id, email or "", 'USER_PROFILE_UPDATE', 'Profile', f"Updated profile details for user ID {user_id}")
        return True, "Profile updated successfully."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def change_user_password(user_id: int, old_password: str, new_password: str):
    user = get_user_by_id(user_id)
    if not user:
        return False, "User not found."
    if user['password_hash'] != hash_password(old_password):
        return False, "Current password is incorrect."
    if len(new_password) < 6:
        return False, "New password must be at least 6 characters."

    conn = get_db()
    cursor = conn.cursor()
    try:
        new_hash = hash_password(new_password)
        cursor.execute("UPDATE users SET password_hash = ? WHERE user_id = ?", (new_hash, user_id))
        conn.commit()
        log_audit(user_id, user['email'], 'PASSWORD_CHANGE', 'Authentication', 'User changed password')
        return True, "Password changed successfully."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


# ==========================================
# 2. HEALTH & WORKOUT MODULE LOGIC
# ==========================================

def log_workout(user_id: int, activity_type: str, duration_mins: int, calories: int, notes: str = "", log_date: str = None):
    """
    Logs a workout entry (FR-12).
    """
    if duration_mins <= 0 or calories <= 0:
        return False, "Duration and Calories burned must be positive numbers."

    if not log_date:
        log_date = date.today().strftime('%Y-%m-%d')

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO workout_log (user_id, activity_type, duration_mins, calories, notes, log_date)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, activity_type, duration_mins, calories, notes.strip(), log_date))
        conn.commit()
        log_audit(user_id, "", 'WORKOUT_LOGGED', 'Health', f"Logged {activity_type} ({duration_mins}m, {calories} kcal)")
        return True, "Workout logged successfully."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_user_workouts(user_id: int, limit: int = None):
    conn = get_db()
    cursor = conn.cursor()
    if limit:
        cursor.execute("""
        SELECT * FROM workout_log
        WHERE user_id = ?
        ORDER BY log_date DESC, created_at DESC
        LIMIT ?
        """, (user_id, limit))
    else:
        cursor.execute("""
        SELECT * FROM workout_log
        WHERE user_id = ?
        ORDER BY log_date DESC, created_at DESC
        """, (user_id,))
    workouts = cursor.fetchall()
    conn.close()
    return workouts

def delete_workout(user_id: int, workout_id: int):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM workout_log WHERE workout_id = ? AND user_id = ?", (workout_id, user_id))
        conn.commit()
        log_audit(user_id, "", 'WORKOUT_DELETED', 'Health', f"Deleted workout record #{workout_id}")
        return True, "Workout deleted."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_weekly_calories(user_id: int):
    """
    Computes total calories burned in current week (Monday to Sunday) (FR-14).
    """
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT COALESCE(SUM(calories), 0) AS total_calories,
           COALESCE(SUM(duration_mins), 0) AS total_duration,
           COUNT(*) AS workout_count
    FROM workout_log
    WHERE user_id = ? AND log_date BETWEEN ? AND ?
    """, (user_id, start_of_week.strftime('%Y-%m-%d'), end_of_week.strftime('%Y-%m-%d')))
    result = cursor.fetchone()
    conn.close()
    return {
        'total_calories': result['total_calories'],
        'total_duration': result['total_duration'],
        'workout_count': result['workout_count']
    }

def get_7day_workout_chart_data(user_id: int):
    """
    Returns calories burned and duration per day for the last 7 days (FR-09).
    """
    today = date.today()
    labels = []
    calories_data = []
    duration_data = []

    conn = get_db()
    cursor = conn.cursor()

    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.strftime('%Y-%m-%d')
        labels.append(day.strftime('%a (%d %b)'))

        cursor.execute("""
        SELECT COALESCE(SUM(calories), 0) as cals, COALESCE(SUM(duration_mins), 0) as mins
        FROM workout_log
        WHERE user_id = ? AND log_date = ?
        """, (user_id, day_str))
        row = cursor.fetchone()
        calories_data.append(row['cals'])
        duration_data.append(row['mins'])

    conn.close()
    return {
        'labels': labels,
        'calories': calories_data,
        'duration': duration_data
    }


# ==========================================
# 3. HABIT TRACKER & STREAK LOGIC
# ==========================================

def add_habit(user_id: int, habit_name: str):
    """
    Adds a new daily habit (FR-15).
    """
    if not habit_name.strip():
        return False, "Habit name cannot be empty."

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO habit_tracker (user_id, habit_name, streak_count, last_completed_date)
        VALUES (?, ?, 0, NULL)
        """, (user_id, habit_name.strip()))
        conn.commit()
        log_audit(user_id, "", 'HABIT_ADDED', 'Health', f"Added new habit '{habit_name.strip()}'")
        return True, "Habit added successfully."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def delete_habit(user_id: int, habit_id: int):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM habit_tracker WHERE habit_id = ? AND user_id = ?", (habit_id, user_id))
        conn.commit()
        log_audit(user_id, "", 'HABIT_DELETED', 'Health', f"Deleted habit #{habit_id}")
        return True, "Habit deleted."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def toggle_habit_today(user_id: int, habit_id: int):
    """
    Marks habit done for today or toggles it off.
    Enforces consecutive streak increment (FR-16) and streak reset if yesterday was missed (FR-17).
    """
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')
    yesterday_str = (today - timedelta(days=1)).strftime('%Y-%m-%d')

    conn = get_db()
    cursor = conn.cursor()
    try:
        # Check if habit belongs to user
        cursor.execute("SELECT * FROM habit_tracker WHERE habit_id = ? AND user_id = ?", (habit_id, user_id))
        habit = cursor.fetchone()
        if not habit:
            return False, "Habit not found."

        # Check if completed today in habit_logs
        cursor.execute("SELECT * FROM habit_logs WHERE habit_id = ? AND completed_date = ?", (habit_id, today_str))
        log_entry = cursor.fetchone()

        if log_entry:
            # Toggle OFF: remove today's log entry
            cursor.execute("DELETE FROM habit_logs WHERE habit_id = ? AND completed_date = ?", (habit_id, today_str))
            
            # Recalculate streak based on latest remaining logs
            cursor.execute("SELECT completed_date FROM habit_logs WHERE habit_id = ? ORDER BY completed_date DESC", (habit_id,))
            logs = [r['completed_date'] for r in cursor.fetchall()]
            
            new_streak = 0
            if logs:
                # Check consecutive backwards from yesterday
                check_date = today - timedelta(days=1)
                for l_str in logs:
                    if l_str == check_date.strftime('%Y-%m-%d'):
                        new_streak += 1
                        check_date -= timedelta(days=1)
                    else:
                        break
                last_d = logs[0]
            else:
                last_d = None

            cursor.execute("""
            UPDATE habit_tracker
            SET streak_count = ?, last_completed_date = ?
            WHERE habit_id = ?
            """, (new_streak, last_d, habit_id))
            conn.commit()
            log_audit(user_id, "", 'HABIT_TOGGLE_OFF', 'Health', f"Unmarked habit '{habit['habit_name']}' for today")
            return True, "Habit unmarked for today."
        else:
            # Toggle ON: add today's log entry
            cursor.execute("""
            INSERT OR IGNORE INTO habit_logs (habit_id, user_id, completed_date)
            VALUES (?, ?, ?)
            """, (habit_id, user_id, today_str))

            # Calculate new streak
            last_date_str = habit['last_completed_date']
            current_streak = habit['streak_count'] or 0

            if last_date_str == yesterday_str:
                # Consecutive day: increment streak
                new_streak = current_streak + 1
            else:
                # Missed previous day or brand new: reset to 1
                new_streak = 1

            cursor.execute("""
            UPDATE habit_tracker
            SET streak_count = ?, last_completed_date = ?
            WHERE habit_id = ?
            """, (new_streak, today_str, habit_id))
            conn.commit()
            log_audit(user_id, "", 'HABIT_COMPLETED', 'Health', f"Completed habit '{habit['habit_name']}' (Streak: {new_streak})")
            return True, f"Great job! Streak is now {new_streak} days."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_user_habits(user_id: int):
    """
    Returns all habits for a user with calculated status for today and active streak.
    """
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')
    yesterday_str = (today - timedelta(days=1)).strftime('%Y-%m-%d')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT h.*, 
           CASE WHEN hl.log_id IS NOT NULL THEN 1 ELSE 0 END AS done_today
    FROM habit_tracker h
    LEFT JOIN habit_logs hl ON h.habit_id = hl.habit_id AND hl.completed_date = ?
    WHERE h.user_id = ?
    ORDER BY h.created_at DESC
    """, (today_str, user_id))
    habits = cursor.fetchall()
    
    # Process display streak (if not done today and last done was before yesterday, effective streak display is 0 until done)
    processed = []
    for h in habits:
        h_dict = dict(h)
        last_d = h['last_completed_date']
        if not h['done_today'] and last_d != yesterday_str and last_d != today_str:
            h_dict['display_streak'] = 0
        else:
            h_dict['display_streak'] = h['streak_count']
        processed.append(h_dict)

    conn.close()
    return processed


# ==========================================
# 4. BMI CALCULATOR & HISTORY LOGIC
# ==========================================

def calculate_and_save_bmi(user_id: int, height_cm: float, weight_kg: float):
    """
    Computes BMI using weight_kg / (height_m^2) (FR-18), classifies category (FR-19),
    and saves the record (FR-20).
    """
    if height_cm <= 0 or weight_kg <= 0:
        return False, "Height and weight must be positive values.", None

    height_m = height_cm / 100.0
    bmi_value = round(weight_kg / (height_m * height_m), 1)

    if bmi_value < 18.5:
        category = "Underweight"
        category_color = "warning"
    elif 18.5 <= bmi_value <= 24.9:
        category = "Normal"
        category_color = "success"
    elif 25.0 <= bmi_value <= 29.9:
        category = "Overweight"
        category_color = "warning"
    else:
        category = "Obese"
        category_color = "danger"

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO bmi_records (user_id, height_cm, weight_kg, bmi_value, category)
        VALUES (?, ?, ?, ?, ?)
        """, (user_id, height_cm, weight_kg, bmi_value, category))
        new_id = cursor.lastrowid
        conn.commit()
        log_audit(user_id, "", 'BMI_CALCULATED', 'Health', f"Calculated BMI: {bmi_value} ({category})")
        return True, "BMI recorded successfully.", {
            'bmi_id': new_id,
            'bmi': bmi_value,
            'category': category,
            'color': category_color,
            'height': height_cm,
            'weight': weight_kg,
            'recorded_date': date.today().strftime('%Y-%m-%d')
        }
    except Exception as e:
        conn.rollback()
        return False, str(e), None
    finally:
        conn.close()

def get_user_bmi_history(user_id: int, limit: int = None):
    """
    Returns historical BMI calculations for a user, ordered by most recent.
    """
    conn = get_db()
    cursor = conn.cursor()
    if limit:
        cursor.execute("""
        SELECT * FROM bmi_records
        WHERE user_id = ?
        ORDER BY recorded_date DESC
        LIMIT ?
        """, (user_id, limit))
    else:
        cursor.execute("""
        SELECT * FROM bmi_records
        WHERE user_id = ?
        ORDER BY recorded_date DESC
        """, (user_id,))
    records = cursor.fetchall()
    conn.close()
    return records

def delete_bmi_record(user_id: int, bmi_id: int):
    """
    Deletes a BMI history entry with user ownership check.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM bmi_records WHERE bmi_id = ? AND user_id = ?", (bmi_id, user_id))
        conn.commit()
        log_audit(user_id, "", 'BMI_DELETED', 'Health', f"Deleted BMI record #{bmi_id}")
        return True, "BMI record deleted."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()


# ==========================================
# 5. TASKS & SCHEDULE MODULE LOGIC
# ==========================================

def create_task(user_id: int, title: str, description: str, priority: str, deadline: str, recurring: str = 'none'):
    """
    Creates a new task with priority, deadline, and recurrence option (FR-21).
    """
    if not title.strip() or not deadline.strip() or priority not in ('high', 'medium', 'low'):
        return False, "Title, priority, and deadline are required."

    if recurring not in ('none', 'daily', 'weekly', 'monthly'):
        recurring = 'none'

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO tasks (user_id, title, description, priority, status, recurring, deadline)
        VALUES (?, ?, ?, ?, 'pending', ?, ?)
        """, (user_id, title.strip(), description.strip() if description else "", priority, recurring, deadline))
        conn.commit()
        log_audit(user_id, "", 'TASK_CREATED', 'Tasks', f"Created task '{title.strip()}' [Priority: {priority}, Recurrence: {recurring}]")
        return True, "Task created successfully."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def update_task(user_id: int, task_id: int, title: str, description: str, priority: str, deadline: str, recurring: str = 'none'):
    """
    Updates task fields (FR-28).
    """
    if not title.strip() or not deadline.strip() or priority not in ('high', 'medium', 'low'):
        return False, "Title, priority, and deadline are required."

    if recurring not in ('none', 'daily', 'weekly', 'monthly'):
        recurring = 'none'

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        UPDATE tasks
        SET title = ?, description = ?, priority = ?, recurring = ?, deadline = ?
        WHERE task_id = ? AND user_id = ?
        """, (title.strip(), description.strip() if description else "", priority, recurring, deadline, task_id, user_id))
        conn.commit()
        log_audit(user_id, "", 'TASK_UPDATED', 'Tasks', f"Updated task #{task_id}")
        return True, "Task updated successfully."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def update_task_status(user_id: int, task_id: int, new_status: str):
    """
    Inline update of task status (FR-27).
    When a recurring task is completed, automatically advances deadline and schedules next occurrence.
    """
    if new_status not in ('pending', 'in_progress', 'done'):
        return False, "Invalid task status."

    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S') if new_status == 'done' else None
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM tasks WHERE task_id = ? AND user_id = ?", (task_id, user_id))
        task_row = cursor.fetchone()
        if not task_row:
            conn.close()
            return False, "Task not found."

        rec = dict(task_row).get('recurring', 'none') or 'none'

        if new_status == 'done' and rec != 'none':
            # Parse existing deadline
            dl_str = task_row['deadline']
            try:
                curr_dl = datetime.strptime(dl_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    curr_dl = datetime.strptime(dl_str, '%Y-%m-%dT%H:%M')
                except ValueError:
                    curr_dl = datetime.strptime(dl_str[:10], '%Y-%m-%d')

            # Calculate next deadline based on recurrence interval
            if rec == 'daily':
                next_dl = curr_dl + timedelta(days=1)
                if next_dl < now: next_dl = now + timedelta(days=1)
                rec_label = "tomorrow (Daily Repeat)"
            elif rec == 'weekly':
                next_dl = curr_dl + timedelta(days=7)
                if next_dl < now: next_dl = now + timedelta(days=7)
                rec_label = "next week (Weekly Repeat)"
            elif rec == 'monthly':
                next_dl = curr_dl + timedelta(days=30)
                if next_dl < now: next_dl = now + timedelta(days=30)
                rec_label = "next month (Monthly Repeat)"
            else:
                next_dl = curr_dl + timedelta(days=1)
                rec_label = "next cycle"

            next_dl_str = next_dl.strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute("""
            UPDATE tasks
            SET status = 'pending', completed_at = ?, deadline = ?
            WHERE task_id = ? AND user_id = ?
            """, (now_str, next_dl_str, task_id, user_id))
            conn.commit()
            log_audit(user_id, "", 'TASK_RECURRED', 'Tasks', f"Task #{task_id} marked done and rescheduled for {rec_label}")
            return True, f"Task completed! Rescheduled for {rec_label}."
        else:
            cursor.execute("""
            UPDATE tasks
            SET status = ?, completed_at = ?
            WHERE task_id = ? AND user_id = ?
            """, (new_status, now_str, task_id, user_id))
            conn.commit()
            log_audit(user_id, "", 'TASK_STATUS_UPDATED', 'Tasks', f"Task #{task_id} status updated to {new_status}")
            return True, f"Task marked as {new_status.replace('_', ' ').title()}."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def delete_task(user_id: int, task_id: int):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM tasks WHERE task_id = ? AND user_id = ?", (task_id, user_id))
        conn.commit()
        log_audit(user_id, "", 'TASK_DELETED', 'Tasks', f"Deleted task #{task_id}")
        return True, "Task deleted."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_user_tasks(user_id: int, filter_status: str = 'all'):
    """
    Retrieves tasks for user, computing dynamic overdue and due soon badges (FR-22, FR-23, FR-24, FR-25).
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM tasks
    WHERE user_id = ?
    ORDER BY CASE status WHEN 'done' THEN 2 ELSE 1 END, deadline ASC
    """, (user_id,))
    raw_tasks = cursor.fetchall()
    conn.close()

    now = datetime.now()
    due_threshold = now + timedelta(hours=24)

    tasks_list = []
    for t in raw_tasks:
        td = dict(t)
        if 'recurring' not in td or td['recurring'] is None:
            td['recurring'] = 'none'
        # Parse deadline
        try:
            d_time = datetime.strptime(td['deadline'], '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                d_time = datetime.strptime(td['deadline'], '%Y-%m-%dT%H:%M')
            except ValueError:
                d_time = datetime.strptime(td['deadline'][:10], '%Y-%m-%d')

        td['deadline_dt'] = d_time
        td['is_overdue'] = (td['status'] != 'done' and d_time < now)
        td['is_due_soon'] = (td['status'] != 'done' and not td['is_overdue'] and d_time <= due_threshold)

        # Filter check
        if filter_status == 'all':
            tasks_list.append(td)
        elif filter_status == 'overdue' and td['is_overdue']:
            tasks_list.append(td)
        elif filter_status == td['status']:
            tasks_list.append(td)

    return tasks_list

def get_task_summary(user_id: int):
    """
    Returns counts for total, done, pending, in_progress, overdue tasks, and completion % (FR-26).
    """
    tasks = get_user_tasks(user_id, 'all')
    total = len(tasks)
    done = sum(1 for t in tasks if t['status'] == 'done')
    in_progress = sum(1 for t in tasks if t['status'] == 'in_progress')
    pending = sum(1 for t in tasks if t['status'] == 'pending')
    overdue = sum(1 for t in tasks if t['is_overdue'])
    due_soon = sum(1 for t in tasks if t['is_due_soon'])
    completion_rate = round((done / total * 100.0), 1) if total > 0 else 0

    return {
        'total': total,
        'done': done,
        'in_progress': in_progress,
        'pending': pending,
        'overdue': overdue,
        'due_soon': due_soon,
        'completion_rate': completion_rate
    }

def get_upcoming_tasks(user_id: int, days: int = 3, limit: int = 10):
    """
    Returns non-done tasks due in next X days, sorted by deadline ascending (FR-08), capped at limit rows.
    """
    now = datetime.now()
    limit_time = now + timedelta(days=days)

    all_tasks = get_user_tasks(user_id, 'all')
    upcoming = []
    for t in all_tasks:
        if t['status'] != 'done' and t['deadline_dt'] <= limit_time:
            upcoming.append(t)

    upcoming.sort(key=lambda x: x['deadline_dt'])
    if limit is not None:
        return upcoming[:limit]
    return upcoming


# ==========================================
# 6. PERSONAL FINANCE MODULE LOGIC
# ==========================================

EXPENSE_CATEGORIES = ['Food', 'Transport', 'Health', 'Entertainment', 'Other']

def log_expense(user_id: int, amount: float, category: str, description: str = "", expense_date: str = None):
    """
    Logs an expense entry (FR-29, FR-30).
    """
    if amount <= 0:
        return False, "Expense amount must be greater than zero."
    if category not in EXPENSE_CATEGORIES:
        return False, f"Category must be one of: {', '.join(EXPENSE_CATEGORIES)}"
    if not expense_date:
        expense_date = date.today().strftime('%Y-%m-%d')

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO expense_log (user_id, amount, category, description, expense_date)
        VALUES (?, ?, ?, ?, ?)
        """, (user_id, round(amount, 2), category, description.strip(), expense_date))
        conn.commit()
        log_audit(user_id, "", 'EXPENSE_LOGGED', 'Finance', f"Logged ₹{amount:.2f} for {category}")
        return True, "Expense recorded successfully."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def update_expense(user_id: int, expense_id: int, amount: float, category: str, description: str = "", expense_date: str = None):
    """
    Updates an existing expense record (FR-29, FR-30).
    """
    if amount <= 0:
        return False, "Expense amount must be greater than zero."
    if category not in EXPENSE_CATEGORIES:
        return False, f"Category must be one of: {', '.join(EXPENSE_CATEGORIES)}"
    if not expense_date:
        expense_date = date.today().strftime('%Y-%m-%d')

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        UPDATE expense_log
        SET amount = ?, category = ?, description = ?, expense_date = ?
        WHERE expense_id = ? AND user_id = ?
        """, (round(amount, 2), category, description.strip(), expense_date, expense_id, user_id))
        conn.commit()
        log_audit(user_id, "", 'EXPENSE_UPDATED', 'Finance', f"Updated expense #{expense_id} (₹{amount:.2f} for {category})")
        return True, "Expense updated successfully."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def delete_expense(user_id: int, expense_id: int):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM expense_log WHERE expense_id = ? AND user_id = ?", (expense_id, user_id))
        conn.commit()
        log_audit(user_id, "", 'EXPENSE_DELETED', 'Finance', f"Deleted expense #{expense_id}")
        return True, "Expense deleted."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_user_expenses(user_id: int, month: int = None, year: int = None, limit: int = 100):
    conn = get_db()
    cursor = conn.cursor()
    if month and year:
        month_str = f"{year:04d}-{month:02d}%"
        cursor.execute("""
        SELECT * FROM expense_log
        WHERE user_id = ? AND expense_date LIKE ?
        ORDER BY expense_date DESC, created_at DESC
        LIMIT ?
        """, (user_id, month_str, limit))
    else:
        cursor.execute("""
        SELECT * FROM expense_log
        WHERE user_id = ?
        ORDER BY expense_date DESC, created_at DESC
        LIMIT ?
        """, (user_id, limit))
    expenses = cursor.fetchall()
    conn.close()
    return expenses

def set_monthly_budget(user_id: int, monthly_limit: float, month: int = None, year: int = None):
    """
    Sets or updates monthly budget limit for given month & year (FR-31).
    """
    if monthly_limit <= 0:
        return False, "Budget limit must be greater than zero."
    today = date.today()
    if not month: month = today.month
    if not year: year = today.year

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO budget (user_id, category, monthly_limit, month, year)
        VALUES (?, 'Overall', ?, ?, ?)
        ON CONFLICT(user_id, month, year, category) DO UPDATE SET monthly_limit = excluded.monthly_limit
        """, (user_id, round(monthly_limit, 2), month, year))
        conn.commit()
        log_audit(user_id, "", 'BUDGET_SET', 'Finance', f"Set monthly budget to ₹{monthly_limit:.2f} for {month}/{year}")
        return True, "Monthly budget updated successfully."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_financial_summary(user_id: int, month: int = None, year: int = None):
    """
    Calculates monthly budget, total spent, percentage, savings, 80% warning and 100% alert (FR-31 to FR-38).
    """
    today = date.today()
    if not month: month = today.month
    if not year: year = today.year
    month_str = f"{year:04d}-{month:02d}%"

    conn = get_db()
    cursor = conn.cursor()

    # Get budget limit
    cursor.execute("""
    SELECT monthly_limit FROM budget
    WHERE user_id = ? AND month = ? AND year = ? AND category = 'Overall'
    """, (user_id, month, year))
    budget_row = cursor.fetchone()
    monthly_budget = budget_row['monthly_limit'] if budget_row else 15000.0

    # Get total spent in month
    cursor.execute("""
    SELECT COALESCE(SUM(amount), 0) AS total_spent, COUNT(*) as count
    FROM expense_log
    WHERE user_id = ? AND expense_date LIKE ?
    """, (user_id, month_str))
    expense_row = cursor.fetchone()
    total_spent = float(expense_row['total_spent'])
    expense_count = expense_row['count']

    conn.close()

    # Calculations
    percent_spent = round((total_spent / monthly_budget * 100.0), 1) if monthly_budget > 0 else 0
    savings = round(monthly_budget - total_spent, 2)
    is_over_budget = (savings < 0)
    is_warning = (percent_spent >= 80.0 and not is_over_budget)
    is_alert = (percent_spent >= 100.0 or is_over_budget)

    # Progress bar color class
    if is_alert:
        progress_class = "danger"
    elif is_warning:
        progress_class = "warning"
    else:
        progress_class = "success"

    return {
        'month': month,
        'year': year,
        'budget': monthly_budget,
        'spent': total_spent,
        'percent_spent': min(percent_spent, 100.0),
        'actual_percent': percent_spent,
        'savings': savings,
        'is_over_budget': is_over_budget,
        'over_budget_amount': abs(savings) if is_over_budget else 0,
        'is_warning': is_warning,
        'is_alert': is_alert,
        'progress_class': progress_class,
        'expense_count': expense_count
    }

def get_category_spending_chart_data(user_id: int, month: int = None, year: int = None):
    """
    Returns category-wise spending for current month for pie chart rendering (FR-35).
    """
    today = date.today()
    if not month: month = today.month
    if not year: year = today.year
    month_str = f"{year:04d}-{month:02d}%"

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT category, COALESCE(SUM(amount), 0) as total
    FROM expense_log
    WHERE user_id = ? AND expense_date LIKE ?
    GROUP BY category
    ORDER BY total DESC
    """, (user_id, month_str))
    rows = cursor.fetchall()
    conn.close()

    categories = [r['category'] for r in rows]
    amounts = [float(r['total']) for r in rows]

    # If empty, provide placeholder
    if not categories:
        categories = ['No Expenses Yet']
        amounts = [0]

    return {
        'categories': categories,
        'amounts': amounts,
        'labels': categories,
        'data': amounts
    }

def get_7day_spending_chart_data(user_id: int):
    """
    Returns daily spending for the last 7 days (FR-36).
    """
    today = date.today()
    labels = []
    amounts = []

    conn = get_db()
    cursor = conn.cursor()

    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        day_str = day.strftime('%Y-%m-%d')
        labels.append(day.strftime('%a (%d %b)'))

        cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) as total
        FROM expense_log
        WHERE user_id = ? AND expense_date = ?
        """, (user_id, day_str))
        row = cursor.fetchone()
        amounts.append(float(row['total']))

    conn.close()
    return {
        'labels': labels,
        'amounts': amounts
    }


# ==========================================
# 7. ADMIN CONTROL PANEL BUSINESS LOGIC
# ==========================================

def get_admin_system_stats():
    """
    Aggregates system-wide statistics (FR-40).
    """
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) AS count FROM users")
    total_users = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM workout_log")
    total_workouts = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count FROM tasks")
    total_tasks = cursor.fetchone()['count']

    cursor.execute("SELECT COUNT(*) AS count, COALESCE(SUM(amount), 0) AS total_amt FROM expense_log")
    exp_row = cursor.fetchone()
    total_expenses = exp_row['count']
    total_spent_system = exp_row['total_amt']

    cursor.execute("SELECT COUNT(*) AS count FROM audit_log")
    total_logs = cursor.fetchone()['count']

    conn.close()
    return {
        'total_users': total_users,
        'total_workouts': total_workouts,
        'total_tasks': total_tasks,
        'total_expenses': total_expenses,
        'total_spent_system': total_spent_system,
        'total_logs': total_logs
    }

def get_all_registered_users():
    """
    Lists all registered users (FR-41).
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT user_id, name, email, role, phone, age, created_at,
           (SELECT COUNT(*) FROM workout_log WHERE workout_log.user_id = users.user_id) AS workout_count,
           (SELECT COUNT(*) FROM tasks WHERE tasks.user_id = users.user_id) AS task_count,
           (SELECT COUNT(*) FROM expense_log WHERE expense_log.user_id = users.user_id) AS expense_count
    FROM users
    ORDER BY created_at DESC
    """)
    users = cursor.fetchall()
    conn.close()
    return users

def delete_user_by_admin(admin_id: int, target_user_id: int):
    """
    Deletes user and cascades all related data (FR-41). Prevents self-deletion.
    """
    if admin_id == target_user_id:
        return False, "Administrator cannot delete their own account."

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT email FROM users WHERE user_id = ?", (target_user_id,))
        u = cursor.fetchone()
        target_email = u['email'] if u else f"ID #{target_user_id}"

        cursor.execute("DELETE FROM users WHERE user_id = ?", (target_user_id,))
        conn.commit()
        log_audit(admin_id, "", 'ADMIN_USER_DELETE', 'Admin', f"Admin deleted user {target_email}")
        return True, f"User {target_email} deleted successfully."
    except Exception as e:
        conn.rollback()
        return False, str(e)
    finally:
        conn.close()

def get_audit_logs(limit: int = 50):
    """
    Retrieves the last 50 audit log entries (FR-43).
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT a.*, COALESCE(u.name, 'System') as user_name
    FROM audit_log a
    LEFT JOIN users u ON a.user_id = u.user_id
    ORDER BY a.timestamp DESC
    LIMIT ?
    """, (limit,))
    logs = cursor.fetchall()
    conn.close()
    return logs


# ==========================================
# 8. MONTHLY REPORTS GENERATOR LOGIC
# ==========================================

def generate_monthly_report_data(user_id: int, month: int = None, year: int = None):
    """
    Aggregates comprehensive health, task, and financial data for printable monthly report (Synopsis Section 5.5).
    """
    today = date.today()
    if not month: month = today.month
    if not year: year = today.year
    month_str = f"{year:04d}-{month:02d}%"
    month_name = datetime(year, month, 1).strftime('%B %Y')

    conn = get_db()
    cursor = conn.cursor()

    # 1. Health data
    cursor.execute("""
    SELECT COUNT(*) as workouts_count,
           COALESCE(SUM(calories), 0) as total_cals,
           COALESCE(SUM(duration_mins), 0) as total_mins
    FROM workout_log
    WHERE user_id = ? AND log_date LIKE ?
    """, (user_id, month_str))
    health_stat = cursor.fetchone()

    # Most active workout activity
    cursor.execute("""
    SELECT activity_type, COUNT(*) as count, SUM(calories) as cals
    FROM workout_log
    WHERE user_id = ? AND log_date LIKE ?
    GROUP BY activity_type
    ORDER BY count DESC
    LIMIT 1
    """, (user_id, month_str))
    top_act = cursor.fetchone()

    # Fetch individual workout logs for the month
    cursor.execute("""
    SELECT * FROM workout_log
    WHERE user_id = ? AND log_date LIKE ?
    ORDER BY log_date DESC
    """, (user_id, month_str))
    workout_rows = cursor.fetchall()

    # Habit stats for the month
    cursor.execute("""
    SELECT h.habit_name, COUNT(hl.log_id) as completions, h.streak_count
    FROM habit_tracker h
    LEFT JOIN habit_logs hl ON h.habit_id = hl.habit_id AND hl.completed_date LIKE ?
    WHERE h.user_id = ?
    GROUP BY h.habit_id
    """, (month_str, user_id))
    habit_rows = cursor.fetchall()

    # BMI records for the month
    cursor.execute("""
    SELECT * FROM bmi_records
    WHERE user_id = ? AND recorded_date LIKE ?
    ORDER BY recorded_date DESC
    """, (user_id, month_str))
    bmi_rows = cursor.fetchall()

    # 2. Task data
    cursor.execute("""
    SELECT * FROM tasks
    WHERE user_id = ? AND (created_at LIKE ? OR deadline LIKE ?)
    ORDER BY deadline ASC
    """, (user_id, month_str, month_str))
    task_rows = cursor.fetchall()
    total_tasks = len(task_rows)
    done_tasks = sum(1 for t in task_rows if t['status'] == 'done')
    pending_tasks = sum(1 for t in task_rows if t['status'] == 'pending')
    in_progress_tasks = sum(1 for t in task_rows if t['status'] == 'in_progress')
    high_tasks = sum(1 for t in task_rows if t['priority'] == 'high')
    task_comp_rate = round((done_tasks / total_tasks * 100.0), 1) if total_tasks > 0 else 0

    # 3. Finance data
    fin_summary = get_financial_summary(user_id, month, year)
    cursor.execute("""
    SELECT category, COALESCE(SUM(amount), 0) as total, COUNT(*) as count
    FROM expense_log
    WHERE user_id = ? AND expense_date LIKE ?
    GROUP BY category
    ORDER BY total DESC
    """, (user_id, month_str))
    fin_categories = cursor.fetchall()

    # Fetch individual expense records for the month
    cursor.execute("""
    SELECT * FROM expense_log
    WHERE user_id = ? AND expense_date LIKE ?
    ORDER BY expense_date DESC
    """, (user_id, month_str))
    expense_rows = cursor.fetchall()

    conn.close()

    # Calculate LifeScore snapshot
    lifescore_data = calculate_lifescore(user_id)

    return {
        'month_name': month_name,
        'month': month,
        'year': year,
        'lifescore': lifescore_data,
        'health': {
            'workouts_count': health_stat['workouts_count'],
            'total_calories': health_stat['total_cals'],
            'total_duration_mins': health_stat['total_mins'],
            'top_activity': top_act['activity_type'] if top_act else 'None',
            'workouts': workout_rows,
            'habits': habit_rows,
            'bmi_records': bmi_rows
        },
        'tasks': {
            'total': total_tasks,
            'done': done_tasks,
            'pending': pending_tasks,
            'in_progress': in_progress_tasks,
            'high_priority': high_tasks,
            'completion_rate': task_comp_rate,
            'task_list': task_rows
        },
        'finance': {
            'summary': fin_summary,
            'categories': fin_categories,
            'expenses': expense_rows
        }
    }


# ==========================================
# 9. AI VOICE & NATURAL LANGUAGE PARSER
# ==========================================

import re

def extract_voice_amount(text: str) -> float:
    """
    Robust extraction of monetary amounts from speech transcripts.
    Handles:
      - Space-separated thousands (e.g. "25 000" -> 25000.0)
      - Comma-separated numbers (e.g. "25,000" -> 25000.0)
      - Word multipliers (e.g. "25 thousand", "25k", "1.5 lakh", "2 lac", "500 rs", "rs 25000")
    """
    norm = text.lower().replace(',', '').replace('₹', ' rs ')
    # Normalize space-separated digits like "25 000", "1 50 000"
    norm = re.sub(r'(?<=\d)\s+(?=\d{2,3}\b)', '', norm)

    # 1. Multiplier keywords (thousand, k, grand, lakh, lac, crore, cr, hundred)
    multiplier_match = re.search(r'(\d+(?:\.\d+)?)\s*(k\b|thousand\b|grand\b|lakhs?\b|lacs?\b|crores?\b|cr\b|hundred\b)', norm)
    if multiplier_match:
        val = float(multiplier_match.group(1))
        unit = multiplier_match.group(2)
        if unit in ('k', 'thousand', 'grand'):
            return val * 1000.0
        elif unit in ('lakh', 'lakhs', 'lac', 'lacs'):
            return val * 100000.0
        elif unit in ('crore', 'crores', 'cr'):
            return val * 10000000.0
        elif unit == 'hundred':
            return val * 100.0

    # 2. Currency prefix or suffix with digits: e.g. "rs 25000", "25000 rupees", "25000 inr"
    amt_match = re.search(r'(?:rs\.?|rupees?|inr)\s*(\d+(?:\.\d{1,2})?)|(\d+(?:\.\d{1,2})?)\s*(?:rs\.?|rupees?|inr)', norm)
    if amt_match:
        amt_str = amt_match.group(1) or amt_match.group(2)
        if amt_str:
            return float(amt_str)

    # 3. Any contiguous numeric value
    nums = re.findall(r'\b\d+(?:\.\d{1,2})?\b', norm)
    if nums:
        return float(nums[0])

    return 0.0

def parse_and_execute_voice_command(user_id: int, speech_text: str):
    """
    Intelligently parses natural speech inputs from the microphone to instantly
    create Workouts, Tasks, Expenses, or Habits with sub-3-second latency.
    """
    if not speech_text or not speech_text.strip():
        return False, "No speech recognized. Please try speaking again.", None

    text = speech_text.strip().lower()
    today = date.today()
    now = datetime.now()

    # -------------------------------------------------------------
    # A. Detect HABIT Intent First (if 'habit' or 'routine' keyword present)
    # -------------------------------------------------------------
    if 'habit' in text or 'daily routine' in text:
        # Extract habit name
        clean_name = re.sub(r'^(?:add|create|new|track)?\s*habit\s*(?:called|named|to|for)?\s*', '', speech_text, flags=re.IGNORECASE).strip()
        if not clean_name:
            clean_name = speech_text.strip()
        
        clean_name = clean_name.capitalize()
        success, msg = add_habit(user_id, clean_name)
        return success, msg, {
            'module': 'Health & Fitness',
            'type': 'Habit',
            'action': f"Added Habit '{clean_name}'",
            'icon': 'fa-fire',
            'redirect': '/health'
        }

    # -------------------------------------------------------------
    # B. Detect EXPLICIT TASK Intent
    # -------------------------------------------------------------
    if text.startswith('task') or text.startswith('add task') or text.startswith('create task') or text.startswith('todo') or text.startswith('remind me to'):
        priority = 'medium'
        if any(w in text for w in ['high', 'urgent', 'critical', 'asap', 'important']):
            priority = 'high'
        elif any(w in text for w in ['low', 'minor']):
            priority = 'low'

        deadline_dt = now + timedelta(days=1)
        if 'tomorrow' in text:
            deadline_dt = now + timedelta(days=1)
        elif 'next week' in text:
            deadline_dt = now + timedelta(days=7)
        elif 'today' in text:
            deadline_dt = now

        deadline_str = deadline_dt.replace(hour=18, minute=0, second=0).strftime('%Y-%m-%d %H:%M:%S')

        task_title = re.sub(r'^(?:add|create|new|remind me to)?\s*(?:task|todo)?\s*', '', speech_text, flags=re.IGNORECASE).strip()
        task_title = re.sub(r'\s*(?:due|by|deadline|tomorrow|today|urgent|high priority|low priority|medium priority).*$', '', task_title, flags=re.IGNORECASE).strip()
        if not task_title: task_title = speech_text.strip()
        task_title = task_title.capitalize()

        success, msg = create_task(user_id, task_title, f"Voice Command: '{speech_text.strip()}'", priority, deadline_str)
        return success, msg, {
            'module': 'Schedule & Tasks',
            'type': 'Task',
            'action': f"Created Task '{task_title}' [Priority: {priority.upper()}]",
            'icon': 'fa-list-check',
            'redirect': '/tasks'
        }

    # -------------------------------------------------------------
    # C. Detect WORKOUT Intent
    # -------------------------------------------------------------
    workout_keywords = ['workout', 'running', 'run', 'ran', 'gym', 'cycling', 'cycle', 'cycled', 'swimming', 'swim', 'swam', 'yoga', 'walking', 'walk', 'walked', 'hiit', 'cardio', 'exercise']
    if any(k in text for k in workout_keywords):
        activity = "Gym"
        if 'run' in text or 'ran' in text or 'jog' in text: activity = "Running"
        elif 'cycl' in text or 'bike' in text or 'ride' in text: activity = "Cycling"
        elif 'swim' in text or 'swam' in text: activity = "Swimming"
        elif 'yoga' in text or 'stretch' in text: activity = "Yoga"
        elif 'walk' in text: activity = "Walking"
        elif 'hiit' in text or 'crossfit' in text: activity = "HIIT"
        elif 'sport' in text or 'badminton' in text or 'football' in text or 'cricket' in text: activity = "Sports"

        dur_match = re.search(r'(\d+)\s*(?:minutes?|mins?|m\b)', text)
        if dur_match:
            duration = int(dur_match.group(1))
        else:
            nums = re.findall(r'\b\d+\b', text)
            duration = int(nums[0]) if nums else 30

        cal_match = re.search(r'(\d+)\s*(?:calories?|cals?|kcal\b)', text)
        if cal_match:
            calories = int(cal_match.group(1))
        else:
            rate = {'Running': 10, 'Cycling': 8, 'Swimming': 9, 'Gym': 7, 'HIIT': 11, 'Yoga': 4, 'Walking': 4.5, 'Sports': 8}
            calories = int(duration * rate.get(activity, 7))

        notes = f"Logged via Voice: '{speech_text.strip()}'"
        success, msg = log_workout(user_id, activity, duration, calories, notes, today.strftime('%Y-%m-%d'))
        
        return success, msg, {
            'module': 'Health & Fitness',
            'type': 'Workout',
            'action': f"Logged {activity} ({duration} mins, {calories} kcal)",
            'icon': 'fa-dumbbell',
            'redirect': '/health'
        }

    # -------------------------------------------------------------
    # D. Detect EXPENSE Intent
    # -------------------------------------------------------------
    expense_keywords = ['spent', 'spend', 'expense', 'paid', 'cost', 'rupees', 'rs', 'inr', 'bought', 'purchase', 'bill', 'thousand', 'lakh', 'lac']
    if any(k in text for k in expense_keywords) and (re.search(r'\d+', text) or any(m in text for m in ['thousand', 'lakh', 'lac', 'k'])):
        amount = extract_voice_amount(speech_text)

        if amount > 0:
            category = "Other"
            if any(w in text for w in ['food', 'lunch', 'dinner', 'breakfast', 'pizza', 'burger', 'coffee', 'grocery', 'groceries', 'snack', 'restaurant', 'eating', 'swiggy', 'zomato', 'drink']):
                category = "Food"
            elif any(w in text for w in ['transport', 'metro', 'cab', 'uber', 'ola', 'auto', 'bus', 'fuel', 'petrol', 'diesel', 'travel', 'train', 'ticket']):
                category = "Transport"
            elif any(w in text for w in ['health', 'medicine', 'doctor', 'clinic', 'gym fee', 'supplement', 'protein', 'pharma', 'hospital']):
                category = "Health"
            elif any(w in text for w in ['movie', 'entertainment', 'cinema', 'game', 'netflix', 'party', 'show', 'concert', 'outing', 'shopping', 'clothes', 'rent', 'fee', 'fees']):
                category = "Entertainment"

            desc = speech_text.strip()
            success, msg = log_expense(user_id, amount, category, desc, today.strftime('%Y-%m-%d'))
            return success, msg, {
                'module': 'Personal Finance',
                'type': 'Expense',
                'action': f"Recorded ₹{amount:,.2f} for {category}",
                'icon': 'fa-indian-rupee-sign',
                'redirect': '/finance'
            }

    # -------------------------------------------------------------
    # E. Fallback to General Task
    # -------------------------------------------------------------
    priority = 'medium'
    deadline_str = (now + timedelta(days=1)).replace(hour=18, minute=0, second=0).strftime('%Y-%m-%d %H:%M:%S')
    task_title = speech_text.strip().capitalize()

    success, msg = create_task(user_id, task_title, f"Voice Command: '{speech_text.strip()}'", priority, deadline_str)
    return success, msg, {
        'module': 'Schedule & Tasks',
        'type': 'Task',
        'action': f"Created Task '{task_title}'",
        'icon': 'fa-list-check',
        'redirect': '/tasks'
    }


# ==========================================
# 10. LIFESCORE INDEX & AI BRIEFING ENGINE
# ==========================================

import csv
import io
import calendar

def calculate_lifescore(user_id: int):
    """
    Computes a composite daily wellness & productivity LifeScore (0 to 100).
    Combines:
      - Health (25%): Calories burned vs daily target (400 kcal)
      - Tasks (30%): Completion rate & on-track status
      - Habits (25%): Today's habit completions & active streaks
      - Finance (20%): Budget adherence & monthly savings buffer
    """
    today = date.today()
    today_str = today.strftime('%Y-%m-%d')

    # 1. Health Score (Max 25 pts)
    workouts = get_user_workouts(user_id, limit=20)
    today_workouts = [w for w in workouts if w['log_date'] == today_str]
    today_cals = sum(w['calories'] for w in today_workouts)
    health_score = min(25.0, round((today_cals / 400.0) * 25.0, 1))

    # 2. Tasks Score (Max 30 pts)
    task_summary = get_task_summary(user_id)
    total_tasks = task_summary['total']
    if total_tasks > 0:
        base_rate = (task_summary['done'] / total_tasks) * 30.0
        # Deduct 5 pts if overdue tasks exist
        penalty = min(10.0, task_summary['overdue'] * 3.0)
        tasks_score = max(5.0, round(base_rate - penalty, 1))
    else:
        tasks_score = 25.0 # Baseline if no tasks

    # 3. Habits Score (Max 25 pts)
    habits = get_user_habits(user_id)
    total_habits = len(habits)
    if total_habits > 0:
        done_count = sum(1 for h in habits if h['done_today'])
        habits_score = round((done_count / total_habits) * 20.0, 1)
        # Bonus up to 5 pts for streaks >= 3 days
        max_streak = max([h['streak_count'] for h in habits], default=0)
        streak_bonus = min(5.0, max_streak * 1.0)
        habits_score = min(25.0, habits_score + streak_bonus)
    else:
        habits_score = 20.0

    # 4. Finance Score (Max 20 pts)
    fin_summary = get_financial_summary(user_id, today.month, today.year)
    if fin_summary['is_over_budget']:
        finance_score = 0.0
    elif fin_summary['is_warning']:
        finance_score = 10.0
    else:
        # Buffer remaining ratio
        finance_score = 20.0

    total_lifescore = int(round(health_score + tasks_score + habits_score + finance_score))
    total_lifescore = max(0, min(100, total_lifescore))

    if total_lifescore >= 85:
        tier = "Peak Productivity"
        color = "#10b981" # Emerald
    elif total_lifescore >= 65:
        tier = "On Track & Strong"
        color = "#6366f1" # Indigo
    elif total_lifescore >= 45:
        tier = "Making Progress"
        color = "#f59e0b" # Amber
    else:
        tier = "Needs Attention"
        color = "#ef4444" # Rose

    return {
        'score': total_lifescore,
        'tier': tier,
        'color': color,
        'breakdown': {
            'health': health_score,
            'tasks': tasks_score,
            'habits': habits_score,
            'finance': finance_score
        }
    }

def get_ai_daily_briefing(user_id: int):
    """
    Synthesizes current day metrics into a personalized, actionable AI briefing card.
    """
    user = get_user_by_id(user_id)
    user_name = user['name'].split()[0] if user else 'Friend'
    now = datetime.now()
    hour = now.hour

    if hour < 12: greeting = "Good morning"
    elif hour < 17: greeting = "Good afternoon"
    else: greeting = "Good evening"

    habits = get_user_habits(user_id)
    pending_habits = sum(1 for h in habits if not h['done_today'])
    max_streak = max([h['streak_count'] for h in habits], default=0)

    task_summary = get_task_summary(user_id)
    upcoming_tasks = get_upcoming_tasks(user_id, days=2)
    fin_summary = get_financial_summary(user_id, now.month, now.year)

    insights = []
    if task_summary['overdue'] > 0:
        insights.append(f"⚠️ You have {task_summary['overdue']} overdue task requiring attention.")
    elif upcoming_tasks:
        insights.append(f"📋 {len(upcoming_tasks)} task{'s are' if len(upcoming_tasks) > 1 else ' is'} due within 48 hours.")
    else:
        insights.append("✨ All scheduled tasks are clear and on track!")

    if pending_habits > 0:
        insights.append(f"🔥 {pending_habits} habit{'s' if pending_habits > 1 else ''} pending today to protect your {max_streak}-day streak.")
    else:
        insights.append(f"🎉 Fantastic consistency! All daily habits checked off.")

    if fin_summary['is_over_budget']:
        insights.append(f"💳 Caution: Budget exceeded by ₹{fin_summary['over_budget_amount']:,.0f}.")
    else:
        insights.append(f"💰 ₹{fin_summary['savings']:,.0f} savings buffer remaining this month.")

    message = f"{greeting}, {user_name}! " + " ".join(insights[:2])
    return {
        'greeting': f"{greeting}, {user_name}",
        'message': message,
        'insights': insights
    }


# ==========================================
# 11. MULTI-DOMAIN CALENDAR & CSV EXPORT
# ==========================================

def get_calendar_events(user_id: int, month: int, year: int):
    """
    Aggregates Workouts, Tasks, and Expenses for a specific month/year,
    mapping them by calendar day for synchronized display.
    """
    month_str = f"{year:04d}-{month:02d}%"
    conn = get_db()
    cursor = conn.cursor()

    # 1. Fetch Workouts in month
    cursor.execute("""
    SELECT * FROM workout_log WHERE user_id = ? AND log_date LIKE ? ORDER BY log_date ASC
    """, (user_id, month_str))
    workouts = cursor.fetchall()

    # 2. Fetch Tasks in month (by deadline)
    cursor.execute("""
    SELECT * FROM tasks WHERE user_id = ? AND deadline LIKE ? ORDER BY deadline ASC
    """, (user_id, month_str))
    tasks = cursor.fetchall()

    # 3. Fetch Expenses in month
    cursor.execute("""
    SELECT * FROM expense_log WHERE user_id = ? AND expense_date LIKE ? ORDER BY expense_date ASC
    """, (user_id, month_str))
    expenses = cursor.fetchall()

    conn.close()

    # Map by day string YYYY-MM-DD
    events_by_day = {}
    
    for w in workouts:
        d = w['log_date']
        if d not in events_by_day: events_by_day[d] = {'workouts': [], 'tasks': [], 'expenses': []}
        events_by_day[d]['workouts'].append(dict(w))

    for t in tasks:
        d = t['deadline'][:10]
        if d not in events_by_day: events_by_day[d] = {'workouts': [], 'tasks': [], 'expenses': []}
        events_by_day[d]['tasks'].append(dict(t))

    for e in expenses:
        d = e['expense_date']
        if d not in events_by_day: events_by_day[d] = {'workouts': [], 'tasks': [], 'expenses': []}
        events_by_day[d]['expenses'].append(dict(e))

    # Build calendar matrix for the month
    cal = calendar.Calendar(firstweekday=0) # Monday first
    month_days = cal.monthdatescalendar(year, month)

    month_name = datetime(year, month, 1).strftime('%B %Y')

    return {
        'month': month,
        'year': year,
        'month_name': month_name,
        'calendar_matrix': month_days,
        'events_by_day': events_by_day
    }

def generate_csv_data(user_id: int, module_name: str):
    """
    Generates CSV spreadsheet text for Workouts, Tasks, or Expenses.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    if module_name == 'workouts':
        writer.writerow(['Workout ID', 'Activity Type', 'Duration (mins)', 'Calories (kcal)', 'Date', 'Notes', 'Logged At'])
        workouts = get_user_workouts(user_id, limit=2000)
        for w in workouts:
            writer.writerow([w['workout_id'], w['activity_type'], w['duration_mins'], w['calories'], w['log_date'], w['notes'] or '', w['created_at']])
        filename = f"lifeboard_workouts_{date.today().strftime('%Y%m%d')}.csv"

    elif module_name == 'tasks':
        writer.writerow(['Task ID', 'Title', 'Description', 'Priority', 'Status', 'Deadline', 'Completed At', 'Created At'])
        tasks = get_user_tasks(user_id, 'all')
        for t in tasks:
            writer.writerow([t['task_id'], t['title'], t['description'] or '', t['priority'], t['status'], t['deadline'], t['completed_at'] or '', t['created_at']])
        filename = f"lifeboard_tasks_{date.today().strftime('%Y%m%d')}.csv"

    elif module_name == 'finance':
        writer.writerow(['Expense ID', 'Amount (INR)', 'Category', 'Description', 'Date', 'Recorded At'])
        expenses = get_user_expenses(user_id, limit=5000)
        for e in expenses:
            writer.writerow([e['expense_id'], e['amount'], e['category'], e['description'] or '', e['expense_date'], e['created_at']])
        filename = f"lifeboard_expenses_{date.today().strftime('%Y%m%d')}.csv"
    else:
        return None, None

    return output.getvalue(), filename


# ==========================================
# 12. ADVANCED PRO SUITE ENGINE
# ==========================================

def get_activity_heatmap_data(user_id: int, num_weeks: int = 16):
    """
    Generates GitHub-style activity contribution matrix for the past N weeks.
    Aggregates Workouts, Habit Check-ins, Tasks Completed, and Expenses.
    """
    today = date.today()
    # Find start date: (num_weeks - 1) weeks ago Monday
    start_date = today - timedelta(days=(today.weekday() + (num_weeks - 1) * 7))

    conn = get_db()
    cursor = conn.cursor()

    start_str = start_date.strftime('%Y-%m-%d')
    end_str = today.strftime('%Y-%m-%d')

    # Query all events in range
    cursor.execute("""
    SELECT log_date, COUNT(*) as cnt FROM workout_log
    WHERE user_id = ? AND log_date BETWEEN ? AND ?
    GROUP BY log_date
    """, (user_id, start_str, end_str))
    workout_counts = {r['log_date']: r['cnt'] for r in cursor.fetchall()}

    cursor.execute("""
    SELECT completed_date as log_date, COUNT(*) as cnt FROM habit_logs
    WHERE user_id = ? AND completed_date BETWEEN ? AND ?
    GROUP BY completed_date
    """, (user_id, start_str, end_str))
    habit_counts = {r['log_date']: r['cnt'] for r in cursor.fetchall()}

    cursor.execute("""
    SELECT SUBSTR(completed_at, 1, 10) as c_date, COUNT(*) as cnt FROM tasks
    WHERE user_id = ? AND status = 'done' AND completed_at IS NOT NULL
      AND SUBSTR(completed_at, 1, 10) BETWEEN ? AND ?
    GROUP BY SUBSTR(completed_at, 1, 10)
    """, (user_id, start_str, end_str))
    task_counts = {r['c_date']: r['cnt'] for r in cursor.fetchall()}

    cursor.execute("""
    SELECT expense_date, COUNT(*) as cnt FROM expense_log
    WHERE user_id = ? AND expense_date BETWEEN ? AND ?
    GROUP BY expense_date
    """, (user_id, start_str, end_str))
    expense_counts = {r['expense_date']: r['cnt'] for r in cursor.fetchall()}

    conn.close()

    # Generate weeks list
    weeks = []
    current_day = start_date
    total_actions = 0
    active_days_count = 0

    while current_day <= today + timedelta(days=(6 - today.weekday())):
        week_days = []
        for _ in range(7):
            day_str = current_day.strftime('%Y-%m-%d')
            is_future = current_day > today
            
            if is_future:
                week_days.append({
                    'date': day_str,
                    'count': 0,
                    'level': 0,
                    'is_future': True,
                    'tooltip': ''
                })
            else:
                w_cnt = workout_counts.get(day_str, 0)
                h_cnt = habit_counts.get(day_str, 0)
                t_cnt = task_counts.get(day_str, 0)
                e_cnt = expense_counts.get(day_str, 0)
                day_total = w_cnt + h_cnt + t_cnt + e_cnt
                total_actions += day_total
                if day_total > 0:
                    active_days_count += 1

                # Intensity level 0 to 4
                if day_total == 0: level = 0
                elif day_total == 1: level = 1
                elif day_total <= 3: level = 2
                elif day_total <= 5: level = 3
                else: level = 4

                tooltip = f"{current_day.strftime('%a, %d %b %Y')}: {day_total} activities"
                if day_total > 0:
                    details = []
                    if w_cnt: details.append(f"{w_cnt} workouts")
                    if h_cnt: details.append(f"{h_cnt} habits")
                    if t_cnt: details.append(f"{t_cnt} tasks")
                    if e_cnt: details.append(f"{e_cnt} expenses")
                    tooltip += f" ({', '.join(details)})"

                week_days.append({
                    'date': day_str,
                    'count': day_total,
                    'level': level,
                    'is_future': False,
                    'tooltip': tooltip
                })
            current_day += timedelta(days=1)
        weeks.append(week_days)

    return {
        'weeks': weeks,
        'total_actions': total_actions,
        'active_days_count': active_days_count,
        'start_date': start_date.strftime('%b %Y'),
        'end_date': today.strftime('%b %Y')
    }


def get_user_achievements(user_id: int):
    """
    Computes unlockable gamification milestone badges.
    """
    conn = get_db()
    cursor = conn.cursor()

    # 1. Total workouts & calories
    cursor.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(calories), 0) as cals FROM workout_log WHERE user_id = ?", (user_id,))
    w_row = cursor.fetchone()
    workout_count = w_row['cnt']
    total_cals = float(w_row['cals'])

    # 2. Max habit streak
    cursor.execute("SELECT COALESCE(MAX(streak_count), 0) as max_s FROM habit_tracker WHERE user_id = ?", (user_id,))
    max_streak = cursor.fetchone()['max_s']

    # 3. Tasks completed
    cursor.execute("SELECT COUNT(*) as cnt FROM tasks WHERE user_id = ? AND status = 'done'", (user_id,))
    done_tasks = cursor.fetchone()['cnt']

    # 4. Expenses tracked
    cursor.execute("SELECT COUNT(*) as cnt FROM expense_log WHERE user_id = ?", (user_id,))
    expense_count = cursor.fetchone()['cnt']

    # 5. Audit logs for voice
    cursor.execute("SELECT COUNT(*) as cnt FROM audit_log WHERE user_id = ? AND action = 'VOICE_COMMAND'", (user_id,))
    voice_count = cursor.fetchone()['cnt']

    conn.close()

    badges = [
        {
            'id': 'streak_master',
            'title': 'Streak Master',
            'icon': 'fa-fire',
            'color': '#ef4444',
            'description': 'Achieve a 7-day habit streak',
            'current': max_streak,
            'target': 7,
            'progress': min(100, int((max_streak / 7) * 100)),
            'unlocked': max_streak >= 7
        },
        {
            'id': 'iron_athlete',
            'title': 'Iron Athlete',
            'icon': 'fa-dumbbell',
            'color': '#4f46e5',
            'description': 'Log 10 workouts',
            'current': workout_count,
            'target': 10,
            'progress': min(100, int((workout_count / 10) * 100)),
            'unlocked': workout_count >= 10
        },
        {
            'id': 'calorie_crusher',
            'title': 'Calorie Crusher',
            'icon': 'fa-bolt',
            'color': '#f59e0b',
            'description': 'Burn 2,500+ total calories',
            'current': int(total_cals),
            'target': 2500,
            'progress': min(100, int((total_cals / 2500) * 100)),
            'unlocked': total_cals >= 2500
        },
        {
            'id': 'task_titan',
            'title': 'Task Titan',
            'icon': 'fa-circle-check',
            'color': '#10b981',
            'description': 'Complete 15 daily tasks',
            'current': done_tasks,
            'target': 15,
            'progress': min(100, int((done_tasks / 15) * 100)),
            'unlocked': done_tasks >= 15
        },
        {
            'id': 'budget_guardian',
            'title': 'Budget Guardian',
            'icon': 'fa-shield-halved',
            'color': '#0284c7',
            'description': 'Track 10 expenses with financial discipline',
            'current': expense_count,
            'target': 10,
            'progress': min(100, int((expense_count / 10) * 100)),
            'unlocked': expense_count >= 10
        },
        {
            'id': 'ai_pioneer',
            'title': 'Voice AI Pioneer',
            'icon': 'fa-microphone-lines',
            'color': '#8b5cf6',
            'description': 'Use Natural Language Voice logger',
            'current': voice_count,
            'target': 1,
            'progress': 100 if voice_count >= 1 else 0,
            'unlocked': voice_count >= 1
        }
    ]

    unlocked_count = sum(1 for b in badges if b['unlocked'])
    level = "Bronze Master"
    if unlocked_count >= 5: level = "Diamond Legend 💎"
    elif unlocked_count >= 3: level = "Gold Champion 🥇"
    elif unlocked_count >= 1: level = "Silver Achiever 🥈"

    return {
        'badges': badges,
        'unlocked_count': unlocked_count,
        'total_badges': len(badges),
        'level': level,
        'completion_rate': int((unlocked_count / len(badges)) * 100)
    }


def get_financial_projection(user_id: int, month: int = None, year: int = None):
    """
    AI Predictive Financial Forecaster:
    Projects end-of-month spending based on velocity and calculates safe daily spend.
    """
    today = date.today()
    if not month: month = today.month
    if not year: year = today.year

    # Number of days in month
    num_days = calendar.monthrange(year, month)[1]
    day_of_month = today.day if (year == today.year and month == today.month) else num_days
    days_remaining = max(1, num_days - day_of_month)

    summary = get_financial_summary(user_id, month, year)
    spent = summary['spent']
    budget = summary['budget']

    daily_avg = spent / max(1, day_of_month)
    projected_spend = daily_avg * num_days

    safe_daily_spend = max(0.0, (budget - spent) / days_remaining)

    status = "on_track"
    message = f"At your current burn rate of ₹{daily_avg:,.0f}/day, your projected month-end total is ₹{projected_spend:,.0f}."
    
    if budget > 0 and projected_spend > budget:
        status = "danger"
        overage = projected_spend - budget
        message = f"⚠️ Spending Alert: At ₹{daily_avg:,.0f}/day, you are on pace to exceed your budget by ₹{overage:,.0f}. Keep remaining daily spending under ₹{safe_daily_spend:,.0f}/day to stay on track."
    elif budget > 0 and projected_spend > (budget * 0.85):
        status = "warning"
        message = f"⚡ Caution: Projected spending (₹{projected_spend:,.0f}) is nearing your limit. Recommended safe spending: ₹{safe_daily_spend:,.0f}/day for the next {days_remaining} days."
    else:
        status = "success"
        message = f"✅ Healthy Financial Pace: You are well within your ₹{budget:,.0f} budget. Safe daily spend limit: ₹{safe_daily_spend:,.0f}/day."

    return {
        'spent': spent,
        'budget': budget,
        'daily_avg': round(daily_avg, 2),
        'projected_spend': round(projected_spend, 2),
        'safe_daily_spend': round(safe_daily_spend, 2),
        'days_remaining': days_remaining,
        'day_of_month': day_of_month,
        'num_days': num_days,
        'status': status,
        'message': message
    }


def get_user_notifications(user_id: int):
    """
    Gathers high-priority real-time alerts for the notification bell center.
    """
    notifications = []
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    today_str = date.today().strftime('%Y-%m-%d')

    conn = get_db()
    cursor = conn.cursor()

    # 1. Overdue tasks
    cursor.execute("""
    SELECT task_id, title, deadline FROM tasks
    WHERE user_id = ? AND status != 'done' AND deadline < ?
    ORDER BY deadline ASC LIMIT 4
    """, (user_id, now_str))
    for t in cursor.fetchall():
        notifications.append({
            'id': f"task_overdue_{t['task_id']}",
            'type': 'danger',
            'icon': 'fa-triangle-exclamation',
            'title': 'Overdue Task',
            'text': f"Task '{t['title']}' passed its deadline ({t['deadline'][:16]}).",
            'link': '/tasks'
        })

    # 2. Tasks due today
    cursor.execute("""
    SELECT task_id, title, deadline FROM tasks
    WHERE user_id = ? AND status != 'done' AND deadline LIKE ?
    ORDER BY deadline ASC LIMIT 3
    """, (user_id, f"{today_str}%"))
    for t in cursor.fetchall():
        notifications.append({
            'id': f"task_due_{t['task_id']}",
            'type': 'warning',
            'icon': 'fa-clock',
            'title': 'Due Today',
            'text': f"Task '{t['title']}' is due today at {t['deadline'][11:16]}.",
            'link': '/tasks'
        })

    conn.close()

    # 3. Budget alerts
    fin = get_financial_summary(user_id)
    if fin['is_over_budget']:
        notifications.append({
            'id': f"budget_exceeded_{today_str[:7]}",
            'type': 'danger',
            'icon': 'fa-wallet',
            'title': 'Budget Exceeded',
            'text': f"Monthly spending (₹{fin['spent']:,.0f}) exceeded your ₹{fin['budget']:,.0f} limit.",
            'link': '/finance'
        })
    elif fin['is_warning']:
        notifications.append({
            'id': f"budget_warning_{today_str[:7]}",
            'type': 'warning',
            'icon': 'fa-wallet',
            'title': 'Budget Caution (80%)',
            'text': f"You have spent {fin['actual_percent']}% of your monthly budget.",
            'link': '/finance'
        })

    return notifications


def import_csv_data(user_id: int, module_name: str, csv_text: str):
    """
    Imports CSV spreadsheet rows into Workouts, Tasks, or Expenses.
    """
    reader = csv.reader(io.StringIO(csv_text.strip()))
    header = next(reader, None)
    if not header:
        return False, "CSV file is empty."

    count = 0
    conn = get_db()
    cursor = conn.cursor()

    try:
        if module_name == 'workouts':
            for row in reader:
                if len(row) >= 4 and row[1] and row[2]:
                    # Format: Workout ID, Activity Type, Duration, Calories, Date, Notes...
                    # Or simple format: Activity Type, Duration, Calories, Date
                    activity = row[1] if len(row) >= 6 else row[0]
                    duration = int(row[2]) if len(row) >= 6 else int(row[1])
                    cals = float(row[3]) if len(row) >= 6 else float(row[2])
                    log_d = row[4] if len(row) >= 6 and row[4] else date.today().strftime('%Y-%m-%d')
                    notes = row[5] if len(row) >= 6 else ''
                    cursor.execute("""
                    INSERT INTO workout_log (user_id, activity_type, duration_mins, calories, log_date, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """, (user_id, activity.strip(), duration, cals, log_d.strip(), notes.strip()))
                    count += 1

        elif module_name == 'tasks':
            for row in reader:
                if len(row) >= 2 and row[1]:
                    title = row[1] if len(row) >= 5 else row[0]
                    desc = row[2] if len(row) >= 5 else ''
                    priority = row[3] if len(row) >= 5 and row[3] in ['high', 'medium', 'low'] else 'medium'
                    deadline = row[5] if len(row) >= 6 and row[5] else (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute("""
                    INSERT INTO tasks (user_id, title, description, priority, deadline)
                    VALUES (?, ?, ?, ?, ?)
                    """, (user_id, title.strip(), desc.strip(), priority.strip(), deadline.strip()))
                    count += 1

        elif module_name == 'finance':
            for row in reader:
                if len(row) >= 2:
                    amount = float(row[1]) if len(row) >= 5 else float(row[0])
                    category = row[2] if len(row) >= 5 else (row[1] if len(row) >= 2 else 'Other')
                    desc = row[3] if len(row) >= 5 else (row[2] if len(row) >= 3 else '')
                    exp_d = row[4] if len(row) >= 5 and row[4] else date.today().strftime('%Y-%m-%d')
                    cursor.execute("""
                    INSERT INTO expense_log (user_id, amount, category, description, expense_date)
                    VALUES (?, ?, ?, ?, ?)
                    """, (user_id, amount, category.strip(), desc.strip(), exp_d.strip()))
                    count += 1
        else:
            conn.close()
            return False, "Invalid import module specified."

        conn.commit()
        log_audit(user_id, "", 'CSV_IMPORT', module_name.capitalize(), f"Imported {count} records from CSV.")
        return True, f"Successfully imported {count} records into {module_name.capitalize()}."
    except Exception as e:
        conn.rollback()
        return False, f"Failed to parse CSV: {str(e)}"
    finally:
        conn.close()
