"""
LifeBoard - Automated Test Suite
Verifies all functional requirements (FR-01 to FR-43), business logic,
database integrity, and Flask routes.
Academic Project: IGNOU BCA BCSP-064
Author: Aayush
"""

import unittest
import os
import sqlite3
from datetime import datetime, date, timedelta
from app import app
import database
import models

class LifeBoardTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test_secret_key'

    def setUp(self):
        self.client = app.test_client()
        # Re-initialize DB
        database.init_db()
        database.seed_initial_data()
        # Reset standard demo passwords to baseline for consistent testing
        conn = database.get_db()
        conn.execute("UPDATE users SET password_hash = ? WHERE email = ?", (database.hash_password('user123'), 'aayush@lifeboard.com'))
        conn.execute("UPDATE users SET password_hash = ? WHERE email = ?", (database.hash_password('admin123'), 'admin@lifeboard.com'))
        conn.commit()
        conn.close()

    # -------------------------------------------------------------
    # 1. Database & Security Tests (FR-01, FR-02, FR-03)
    # -------------------------------------------------------------
    def test_01_password_hashing(self):
        raw_pw = "mySecretPassword123"
        hashed = database.hash_password(raw_pw)
        self.assertNotEqual(raw_pw, hashed)
        self.assertEqual(len(hashed), 64) # SHA-256 hex digest length
        self.assertEqual(hashed, database.hash_password(raw_pw))

    def test_02_user_registration_and_uniqueness(self):
        # Test unique email registration
        test_email = f"test_{int(datetime.now().timestamp())}@example.com"
        success, uid = models.register_user("Test User", test_email, "securepass", phone="+91 9999999999", age=22)
        self.assertTrue(success)
        self.assertIsInstance(uid, int)

        # Test duplicate registration rejection (FR-03)
        dup_success, dup_msg = models.register_user("Duplicate User", test_email, "anotherpass")
        self.assertFalse(dup_success)
        self.assertIn("already exists", dup_msg)

    # -------------------------------------------------------------
    # 2. Authentication & Access Control (FR-04, FR-05, FR-06, FR-39)
    # -------------------------------------------------------------
    def test_03_login_and_logout_flow(self):
        # Valid login with demo user
        response = self.client.post('/login', data={
            'email': 'aayush@lifeboard.com',
            'password': 'user123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Dashboard', response.data)

        # Logout (FR-06)
        logout_resp = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(logout_resp.status_code, 200)
        self.assertIn(b'Sign In', logout_resp.data)

    def test_04_protected_routes_unauthenticated_redirect(self):
        # Accessing protected routes without session should redirect to /login (FR-05)
        routes = ['/dashboard', '/health', '/tasks', '/finance', '/profile', '/reports', '/admin']
        for r in routes:
            resp = self.client.get(r)
            self.assertEqual(resp.status_code, 302, f"Route {r} did not redirect")
            self.assertIn('/login', resp.headers['Location'])

    def test_05_admin_route_authorization(self):
        # Regular user accessing /admin should get 403 Forbidden (FR-39)
        with self.client.session_transaction() as sess:
            sess['user_id'] = 2
            sess['name'] = 'Aayush Sharma'
            sess['email'] = 'aayush@lifeboard.com'
            sess['role'] = 'user'

        resp = self.client.get('/admin')
        self.assertEqual(resp.status_code, 403)

        # Admin user accessing /admin should succeed (200 OK)
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['name'] = 'System Administrator'
            sess['email'] = 'admin@lifeboard.com'
            sess['role'] = 'admin'

        admin_resp = self.client.get('/admin')
        self.assertEqual(admin_resp.status_code, 200)
        self.assertIn(b'Administrator Control Panel', admin_resp.data)

    # -------------------------------------------------------------
    # 3. Health & Activity Module Tests (FR-12 to FR-20)
    # -------------------------------------------------------------
    def test_06_workout_logging_and_weekly_calories(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        # Log a workout (FR-12)
        success, msg = models.log_workout(uid, 'Gym', 45, 350, 'Back & Biceps')
        self.assertTrue(success)

        # Verify weekly calories calculation (FR-14)
        stats = models.get_weekly_calories(uid)
        self.assertGreater(stats['total_calories'], 0)
        self.assertGreater(stats['workout_count'], 0)

        # Test invalid inputs
        bad_success, _ = models.log_workout(uid, 'Running', -10, 0)
        self.assertFalse(bad_success)

    def test_07_habit_streak_logic(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        h_name = f'Test Unique Streak Habit {datetime.now().timestamp()}'
        # Add a new habit (FR-15)
        success, msg = models.add_habit(uid, h_name)
        self.assertTrue(success)

        habits = models.get_user_habits(uid)
        target = [h for h in habits if h['habit_name'] == h_name][0]

        # First completion today -> Streak should become 1
        t_success, t_msg = models.toggle_habit_today(uid, target['habit_id'])
        self.assertTrue(t_success)

        updated_habits = models.get_user_habits(uid)
        updated_target = [h for h in updated_habits if h['habit_id'] == target['habit_id']][0]
        self.assertEqual(updated_target['streak_count'], 1)
        self.assertEqual(updated_target['done_today'], 1)

        # Cleanup
        models.delete_habit(uid, target['habit_id'])

    def test_08_bmi_calculation_and_classification(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        # Height 175cm, Weight 70kg -> BMI ~ 22.9 (Normal) (FR-18, FR-19)
        success, msg, data = models.calculate_and_save_bmi(uid, 175.0, 70.0)
        self.assertTrue(success)
        self.assertEqual(data['bmi'], 22.9)
        self.assertEqual(data['category'], 'Normal')

        # Test Obese category (Height 170cm, Weight 100kg -> BMI ~ 34.6)
        _, _, data_obese = models.calculate_and_save_bmi(uid, 170.0, 100.0)
        self.assertEqual(data_obese['category'], 'Obese')

        # Test history retrieval
        history = models.get_user_bmi_history(uid, limit=50)
        self.assertGreater(len(history), 0)

        # Test delete BMI record
        del_success, del_msg = models.delete_bmi_record(uid, history[0]['bmi_id'])
        self.assertTrue(del_success)

        # Test health route rendering
        with self.client.session_transaction() as sess:
            sess['user_id'] = uid
            sess['email'] = user['email']
            sess['name'] = user['name']
            sess['role'] = user['role']

        res = self.client.get('/health')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'BMI History Log', res.data)

    # -------------------------------------------------------------
    # 4. Tasks & Schedule Module Tests (FR-21 to FR-28)
    # -------------------------------------------------------------
    def test_09_task_crud_and_status_transitions(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        # Create Task (FR-21)
        deadline = (datetime.now() + timedelta(days=2)).strftime('%Y-%m-%d %H:%M:%S')
        success, msg = models.create_task(uid, 'Test Task Title', 'Test description', 'high', deadline)
        self.assertTrue(success)

        tasks = models.get_user_tasks(uid, 'all')
        task = [t for t in tasks if t['title'] == 'Test Task Title'][0]
        self.assertEqual(task['priority'], 'high')
        self.assertEqual(task['status'], 'pending')

        # Inline status update to in_progress and done (FR-27)
        models.update_task_status(uid, task['task_id'], 'in_progress')
        t_prog = [t for t in models.get_user_tasks(uid, 'all') if t['task_id'] == task['task_id']][0]
        self.assertEqual(t_prog['status'], 'in_progress')

        models.update_task_status(uid, task['task_id'], 'done')
        t_done = [t for t in models.get_user_tasks(uid, 'all') if t['task_id'] == task['task_id']][0]
        self.assertEqual(t_done['status'], 'done')
        self.assertIsNotNone(t_done['completed_at'])

        # Task summary verification (FR-26)
        summary = models.get_task_summary(uid)
        self.assertGreater(summary['total'], 0)
        self.assertGreater(summary['done'], 0)

    # -------------------------------------------------------------
    # 5. Personal Finance Module Tests (FR-29 to FR-38)
    # -------------------------------------------------------------
    def test_10_finance_budget_and_overspending_alerts(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']
        today = date.today()

        # Set budget to ₹10,000 (FR-31)
        models.set_monthly_budget(uid, 10000.0, today.month, today.year)

        # Log an expense of ₹2,500 for Food (FR-29, FR-30)
        success, msg = models.log_expense(uid, 2500.0, 'Food', 'Groceries')
        self.assertTrue(success)

        # Check financial summary
        summary = models.get_financial_summary(uid, today.month, today.year)
        self.assertEqual(summary['budget'], 10000.0)
        self.assertGreater(summary['spent'], 0)

        # Check category restriction (FR-30)
        bad_cat_success, _ = models.log_expense(uid, 500.0, 'InvalidCategory')
        self.assertFalse(bad_cat_success)

        # Test 80% warning and 100% overspending alert calculation (FR-33, FR-34, FR-38)
        # Set small budget of ₹1000 to trigger over-budget
        models.set_monthly_budget(uid, 1000.0, today.month, today.year)
        over_summary = models.get_financial_summary(uid, today.month, today.year)
        self.assertTrue(over_summary['is_over_budget'])
        self.assertGreater(over_summary['over_budget_amount'], 0)
        self.assertEqual(over_summary['progress_class'], 'danger')

    # -------------------------------------------------------------
    # 6. "You" Profile Tab & Reports Tests
    # -------------------------------------------------------------
    def test_11_profile_update_and_password_change(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        # Update profile (You Tab)
        success, msg = models.update_user_profile(uid, 'Aayush S. (Updated)', '+91 9888877777', 22, 'Passionate Software Developer')
        self.assertTrue(success)

        updated_user = models.get_user_by_id(uid)
        self.assertEqual(updated_user['name'], 'Aayush S. (Updated)')
        self.assertEqual(updated_user['age'], 22)

        # Change password with valid old password
        pw_success, _ = models.change_user_password(uid, 'user123', 'newSecret456')
        self.assertTrue(pw_success)

        # Check bad old password fails
        bad_pw, _ = models.change_user_password(uid, 'wrongoldpass', 'anotherSecret')
        self.assertFalse(bad_pw)

    def test_12_monthly_report_generation(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']
        today = date.today()

        # 1. Model data structure test
        report = models.generate_monthly_report_data(uid, today.month, today.year)
        self.assertIn('health', report)
        self.assertIn('tasks', report)
        self.assertIn('finance', report)
        self.assertIn('lifescore', report)
        self.assertIn('task_list', report['tasks'])
        self.assertIn('workouts', report['health'])
        self.assertIn('expenses', report['finance'])
        self.assertGreaterEqual(report['health']['workouts_count'], 0)

        # 2. End-to-end HTTP template rendering test
        with self.client.session_transaction() as sess:
            sess['user_id'] = uid
            sess['email'] = user['email']
            sess['name'] = user['name']
            sess['role'] = user['role']

        response = self.client.get('/reports')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Monthly Performance Report', response.data)
        self.assertIn(b'Health, Physical Activity & BMI Analysis', response.data)
        self.assertIn(b'Monthly Task Roster', response.data)
        self.assertIn(b'Personal Financial Report', response.data)

    # -------------------------------------------------------------
    # 7. Admin Control Panel & Audit Logs (FR-40 to FR-43)
    # -------------------------------------------------------------
    # -------------------------------------------------------------
    # 8. AI Voice Command & NLP Parsing Tests
    # -------------------------------------------------------------
    def test_14_voice_command_nlp(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        # Test Voice Workout Parsing
        w_success, w_msg, w_info = models.parse_and_execute_voice_command(uid, "Gym workout for 50 minutes burned 420 calories")
        self.assertTrue(w_success)
        self.assertEqual(w_info['type'], 'Workout')
        self.assertEqual(w_info['module'], 'Health & Fitness')

        # Test Voice Task Parsing
        t_success, t_msg, t_info = models.parse_and_execute_voice_command(uid, "Add task complete project documentation high priority tomorrow")
        self.assertTrue(t_success)
        self.assertEqual(t_info['type'], 'Task')

        # Test Voice Expense Parsing
        e_success, e_msg, e_info = models.parse_and_execute_voice_command(uid, "Record expense 450 rupees on food for lunch")
        self.assertTrue(e_success)
        self.assertEqual(e_info['type'], 'Expense')

        # Test Voice Expense with space-separated thousand: "spend 25 000 rupees"
        e2_success, e2_msg, e2_info = models.parse_and_execute_voice_command(uid, "spend 25 000 rupees on shopping")
        self.assertTrue(e2_success)
        self.assertIn("25,000.00", e2_info['action'])

        # Test Voice Expense with multiplier words: "paid 15 thousand for rent"
        e3_success, e3_msg, e3_info = models.parse_and_execute_voice_command(uid, "paid 15 thousand for rent")
        self.assertTrue(e3_success)
        self.assertIn("15,000.00", e3_info['action'])

        # Test Voice Expense with k suffix: "spent 2.5k on dinner"
        e4_success, e4_msg, e4_info = models.parse_and_execute_voice_command(uid, "spent 2.5k on dinner")
        self.assertTrue(e4_success)
        self.assertIn("2,500.00", e4_info['action'])

        # Test Voice Habit Parsing
        h_success, h_msg, h_info = models.parse_and_execute_voice_command(uid, "Add habit drink 4 liters of water daily")
        self.assertTrue(h_success)
        self.assertEqual(h_info['type'], 'Habit')

    # -------------------------------------------------------------
    # 9. Admin Security Verification Checkpoint Tests
    # -------------------------------------------------------------
    def test_15_admin_verification_security(self):
        # Accessing /admin as a normal user returns 403 Forbidden (FR-39)
        with self.client.session_transaction() as sess:
            sess['user_id'] = 2
            sess['name'] = 'Aayush Sharma'
            sess['email'] = 'aayush@lifeboard.com'
            sess['role'] = 'user'

        resp = self.client.get('/admin')
        self.assertEqual(resp.status_code, 403)

        # Submitting wrong admin password to /admin/verify fails
        bad_post = self.client.post('/admin/verify', data={
            'email': 'admin@lifeboard.com',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        self.assertIn(b'Access Denied', bad_post.data)

        # Submitting correct admin credentials to /admin/verify succeeds
        good_post = self.client.post('/admin/verify', data={
            'email': 'admin@lifeboard.com',
            'password': 'admin123'
        }, follow_redirects=True)
        self.assertIn(b'Administrator Control Panel', good_post.data)

    # -------------------------------------------------------------
    # 10. Next-Gen LifeScore & AI Daily Briefing Tests
    # -------------------------------------------------------------
    def test_16_lifescore_and_ai_briefing(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        score_data = models.calculate_lifescore(uid)
        self.assertIsInstance(score_data['score'], int)
        self.assertGreaterEqual(score_data['score'], 0)
        self.assertLessEqual(score_data['score'], 100)
        self.assertIn('tier', score_data)
        self.assertIn('breakdown', score_data)

        briefing = models.get_ai_daily_briefing(uid)
        self.assertIn('greeting', briefing)
        self.assertIn('message', briefing)
        self.assertIn('forecast', briefing)
        self.assertIn('ai-link', briefing['message'])
        self.assertGreater(len(briefing['message']), 10)

        # Test Dashboard HTTP rendering with unified briefing
        with self.client.session_transaction() as sess:
            sess['user_id'] = uid
            sess['email'] = user['email']
            sess['name'] = user['name']
            sess['role'] = user['role']

        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'AI Daily Briefing', resp.data)
        self.assertIn(b'LifeScore', resp.data)

    # -------------------------------------------------------------
    # 11. Multi-Domain Calendar Integration Tests
    # -------------------------------------------------------------
    def test_17_calendar_events_aggregation(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']
        today = date.today()

        cal_events = models.get_calendar_events(uid, today.month, today.year)
        self.assertEqual(cal_events['month'], today.month)
        self.assertEqual(cal_events['year'], today.year)
        self.assertIn('events_by_day', cal_events)
        self.assertIn('calendar_matrix', cal_events)

        with self.client.session_transaction() as sess:
            sess['user_id'] = uid
            sess['name'] = 'Aayush Sharma'
            sess['email'] = 'aayush@lifeboard.com'
            sess['role'] = 'user'

        resp = self.client.get('/calendar')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Life Calendar', resp.data)

    # -------------------------------------------------------------
    # 12. CSV Data Export Tests
    # -------------------------------------------------------------
    def test_18_csv_data_exports(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 2
            sess['name'] = 'Aayush Sharma'
            sess['email'] = 'aayush@lifeboard.com'
            sess['role'] = 'user'

        for mod in ['workouts', 'tasks', 'finance']:
            resp = self.client.get(f'/export/csv/{mod}')
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.headers['Content-Type'], 'text/csv; charset=utf-8')
            self.assertIn('attachment;', resp.headers['Content-Disposition'])

    # -------------------------------------------------------------
    # 13. PWA Static Files Tests
    # -------------------------------------------------------------
    def test_19_pwa_static_routes(self):
        man_resp = self.client.get('/manifest.json')
        self.assertEqual(man_resp.status_code, 200)
        self.assertIn(b'LifeBoard', man_resp.data)

        sw_resp = self.client.get('/sw.js')
        self.assertEqual(sw_resp.status_code, 200)
        self.assertIn(b'CACHE_NAME', sw_resp.data)

    # -------------------------------------------------------------
    # 14. Activity Heatmap & Achievements Tests
    # -------------------------------------------------------------
    def test_20_activity_heatmap_generation(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        heatmap = models.get_activity_heatmap_data(uid, num_weeks=16)
        self.assertIn('weeks', heatmap)
        self.assertEqual(len(heatmap['weeks']), 16)
        self.assertGreaterEqual(heatmap['total_actions'], 0)
        self.assertGreaterEqual(heatmap['active_days_count'], 0)

    def test_21_user_achievements_and_leveling(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        achievements = models.get_user_achievements(uid)
        self.assertIn('badges', achievements)
        self.assertEqual(len(achievements['badges']), 6)
        self.assertIn('level', achievements)
        self.assertIsInstance(achievements['unlocked_count'], int)

    # -------------------------------------------------------------
    # 15. Predictive Financial Forecaster Tests
    # -------------------------------------------------------------
    def test_22_predictive_budget_forecasting(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        forecast = models.get_financial_projection(uid)
        self.assertIn('daily_avg', forecast)
        self.assertIn('projected_spend', forecast)
        self.assertIn('safe_daily_spend', forecast)
        self.assertIn('status', forecast)
        self.assertIn('message', forecast)

    # -------------------------------------------------------------
    # 16. In-App Notification Center Tests
    # -------------------------------------------------------------
    def test_23_in_app_notifications_center(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        notifications = models.get_user_notifications(uid)
        self.assertIsInstance(notifications, list)
        for n in notifications:
            self.assertIn('title', n)
            self.assertIn('text', n)
            self.assertIn('type', n)

    # -------------------------------------------------------------
    # 17. CSV Data Import Tests
    # -------------------------------------------------------------
    def test_24_csv_data_import(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        # Import sample workouts CSV
        csv_workouts = "Activity Type,Duration,Calories,Date,Notes\nCycling,40,320,2026-08-20,Evening ride\n"
        success, msg = models.import_csv_data(uid, 'workouts', csv_workouts)
        self.assertTrue(success)
        self.assertIn('Successfully imported', msg)

        # Import sample tasks CSV
        csv_tasks = "Title,Description,Priority,Deadline\nFinish Synopsis,Complete BCA Project,high,2026-08-25 18:00:00\n"
        task_success, task_msg = models.import_csv_data(uid, 'tasks', csv_tasks)
        self.assertTrue(task_success)

        # Import sample finance CSV
        csv_finance = "Amount,Category,Description,Date\n450.0,Food,Dinner with team,2026-08-21\n"
        fin_success, fin_msg = models.import_csv_data(uid, 'finance', csv_finance)
        self.assertTrue(fin_success)

    # -------------------------------------------------------------
    # 18. Admin Database Backup Download Tests
    # -------------------------------------------------------------
    def test_25_admin_database_backup_download(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1
            sess['name'] = 'System Administrator'
            sess['email'] = 'admin@lifeboard.com'
            sess['role'] = 'admin'

        resp = self.client.get('/admin/backup/download')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('attachment;', resp.headers['Content-Disposition'])
        self.assertIn('lifeboard_backup_', resp.headers['Content-Disposition'])

    # -------------------------------------------------------------
    # 19. Profile Email Update & Uniqueness Tests
    # -------------------------------------------------------------
    def test_26_profile_email_update_and_validation(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        # Duplicate email check against admin
        dup_success, dup_msg = models.update_user_profile(uid, 'Aayush S', '9999999999', 24, 'Bio', email='admin@lifeboard.com')
        self.assertFalse(dup_success)
        self.assertIn('already in use', dup_msg)

        # Valid email update
        success, msg = models.update_user_profile(uid, 'Aayush Sharma', '9876543210', 23, 'Developer', email='aayush.updated@lifeboard.com')
        self.assertTrue(success)
        updated_user = models.get_user_by_id(uid)
        self.assertEqual(updated_user['email'], 'aayush.updated@lifeboard.com')

        # Revert back
        models.update_user_profile(uid, 'Aayush Sharma', '9876543210', 23, 'Developer', email='aayush@lifeboard.com')

    # -------------------------------------------------------------
    # 20. Upcoming Tasks 10-Row Restriction Tests
    # -------------------------------------------------------------
    def test_27_upcoming_tasks_limit_to_10(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        # Query upcoming tasks with default limit 10
        upcoming = models.get_upcoming_tasks(uid, days=3, limit=10)
        self.assertLessEqual(len(upcoming), 10)

    # -------------------------------------------------------------
    # 21. Recurring Tasks Creation & Auto-Rescheduling Tests
    # -------------------------------------------------------------
    def test_28_recurring_task_creation_and_reschedule(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        # 1. Create a daily recurring task
        dl = (datetime.now() + timedelta(hours=5)).strftime('%Y-%m-%d %H:%M:%S')
        success, msg = models.create_task(uid, "Daily Water Refill", "Drink water", "medium", dl, recurring="daily")
        self.assertTrue(success)

        # 2. Verify task has recurring='daily'
        tasks = [t for t in models.get_user_tasks(uid, 'all') if t['title'] == "Daily Water Refill"]
        self.assertTrue(len(tasks) > 0)
        task = tasks[0]
        self.assertEqual(task['recurring'], 'daily')

        # 3. Marking task as 'done' automatically advances deadline by +1 day and resets status to 'pending'
        old_dl = task['deadline_dt']
        status_success, status_msg = models.update_task_status(uid, task['task_id'], 'done')
        self.assertTrue(status_success)
        self.assertIn("Daily Repeat", status_msg)

        # 4. Verify the task rescheduled
        updated_tasks = [t for t in models.get_user_tasks(uid, 'all') if t['task_id'] == task['task_id']]
        updated_task = updated_tasks[0]
        self.assertEqual(updated_task['status'], 'pending')
        self.assertGreater(updated_task['deadline_dt'], old_dl)

        # Cleanup
        models.delete_task(uid, task['task_id'])

    # -------------------------------------------------------------
    # 22. Personal Finance Expense Update & Edit Route Tests
    # -------------------------------------------------------------
    def test_29_expense_update_and_edit_flow(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 2
            sess['name'] = 'Aayush Sharma'
            sess['email'] = 'aayush@lifeboard.com'
            sess['role'] = 'user'

        # 1. Log a test expense
        log_succ, log_msg = models.log_expense(2, 250.0, "Food", "Initial Snack", date.today().strftime('%Y-%m-%d'))
        self.assertTrue(log_succ)

        expenses = models.get_user_expenses(2, limit=10)
        test_exp = [e for e in expenses if e['description'] == "Initial Snack"][0]
        exp_id = test_exp['expense_id']

        # 2. Edit the expense via POST route
        post_resp = self.client.post(f'/finance/expense/edit/{exp_id}', data={
            'amount': '350.50',
            'category': 'Transport',
            'description': 'Updated Metro Card',
            'expense_date': date.today().strftime('%Y-%m-%d')
        }, follow_redirects=True)
        self.assertEqual(post_resp.status_code, 200)

        # 3. Verify updated details in database
        updated_expenses = models.get_user_expenses(2, limit=10)
        updated_exp = [e for e in updated_expenses if e['expense_id'] == exp_id][0]
        self.assertEqual(updated_exp['amount'], 350.50)
        self.assertEqual(updated_exp['category'], 'Transport')
        self.assertEqual(updated_exp['description'], 'Updated Metro Card')

        # Cleanup
        models.delete_expense(2, exp_id)

    # -------------------------------------------------------------
    # 23. Database Integrity & Foreign Key Cascade Tests
    # -------------------------------------------------------------
    def test_30_database_integrity_and_cascades(self):
        # 1. Create a dummy user
        test_email = f"cascade_test_{int(datetime.now().timestamp())}@lifeboard.com"
        success, uid = models.register_user("Cascade User", test_email, "pass123")
        self.assertTrue(success)

        # 2. Add records across all tables for this user
        models.log_workout(uid, "Gym", 30, 200, date.today().strftime('%Y-%m-%d'))
        models.create_task(uid, "Cascade Task", "desc", "medium", (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S'))
        models.add_habit(uid, "Cascade Habit")
        models.log_expense(uid, 500, "Food", "desc", date.today().strftime('%Y-%m-%d'))
        models.calculate_and_save_bmi(uid, 175, 70)

        # Verify records exist
        self.assertEqual(len(models.get_user_workouts(uid)), 1)
        self.assertEqual(len(models.get_user_tasks(uid, 'all')), 1)
        self.assertEqual(len(models.get_user_habits(uid)), 1)
        self.assertEqual(len(models.get_user_expenses(uid)), 1)
        self.assertEqual(len(models.get_user_bmi_history(uid)), 1)

        # 3. Delete user via admin cascade function
        del_succ, del_msg = models.delete_user_by_admin(1, uid)
        self.assertTrue(del_succ)

        # Verify all child records were cleanly cascaded
        self.assertEqual(len(models.get_user_workouts(uid)), 0)
        self.assertEqual(len(models.get_user_tasks(uid, 'all')), 0)
        self.assertEqual(len(models.get_user_habits(uid)), 0)
        self.assertEqual(len(models.get_user_expenses(uid)), 0)
        self.assertEqual(len(models.get_user_bmi_history(uid)), 0)

    # -------------------------------------------------------------
    # 24. System Error Handling & Boundary Condition Tests
    # -------------------------------------------------------------
    def test_31_error_handling_and_boundary_conditions(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        with self.client.session_transaction() as sess:
            sess['user_id'] = uid
            sess['email'] = user['email']
            sess['name'] = user['name']
            sess['role'] = user['role']

        # 1. 404 Route handling
        resp_404 = self.client.get('/nonexistent-route-xyz')
        self.assertEqual(resp_404.status_code, 404)

        # 2. Deleting non-existent task returns error or safe redirect without crashing
        del_fake_task = self.client.post('/tasks/delete/999999', follow_redirects=True)
        self.assertEqual(del_fake_task.status_code, 200)

        # 3. Deleting non-existent expense returns safe redirect without crashing
        del_fake_exp = self.client.post('/finance/expense/delete/999999', follow_redirects=True)
        self.assertEqual(del_fake_exp.status_code, 200)

        # 4. Zero/Empty month report generation does not raise ZeroDivisionError
        empty_report = models.generate_monthly_report_data(uid, 1, 2010)
        self.assertEqual(empty_report['health']['workouts_count'], 0)
        self.assertEqual(empty_report['health']['total_calories'], 0)
        self.assertEqual(empty_report['finance']['summary']['spent'], 0)
        self.assertIsInstance(empty_report['lifescore'], dict)

    # -------------------------------------------------------------
    # 25. BMI Persistence & AJAX API Endpoint Tests
    # -------------------------------------------------------------
    def test_32_bmi_unlimited_persistence_and_ajax_api(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        with self.client.session_transaction() as sess:
            sess['user_id'] = uid
            sess['email'] = user['email']
            sess['name'] = user['name']
            sess['role'] = user['role']

        # 1. Direct model test: calculate & save BMI
        succ, msg, res = models.calculate_and_save_bmi(uid, 180.0, 75.0)
        self.assertTrue(succ)
        self.assertIn('bmi', res)
        self.assertAlmostEqual(res['bmi'], 23.1, places=1)
        self.assertEqual(res['category'], 'Normal')
        self.assertIn('bmi_id', res)
        self.assertIn('recorded_date', res)

        # 2. Verify all BMI records are fetched without limit caps
        history = models.get_user_bmi_history(uid)
        self.assertIsInstance(history, list)
        self.assertGreater(len(history), 0)

        # 3. Test AJAX JSON Endpoint
        ajax_resp = self.client.post('/health/bmi/calculate', data={
            'height_cm': '175',
            'weight_kg': '68'
        }, headers={'X-Requested-With': 'XMLHttpRequest'})
        self.assertEqual(ajax_resp.status_code, 200)
        json_data = ajax_resp.get_json()
        self.assertTrue(json_data['success'])
        self.assertEqual(json_data['data']['category'], 'Normal')
        self.assertGreaterEqual(len(models.get_user_bmi_history(uid)), 1)

    # -------------------------------------------------------------
    # 26. Habit Creation Date & Streak Logic Tests
    # -------------------------------------------------------------
    def test_33_habit_creation_date_and_streak_logic(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        # 1. Add new habit
        succ, msg = models.add_habit(uid, "Read Scientific Literature")
        self.assertTrue(succ)

        habits = models.get_user_habits(uid)
        matching = [h for h in habits if h['habit_name'] == "Read Scientific Literature"]
        self.assertTrue(len(matching) > 0)
        habit = matching[0]

        # Verify created_at is present
        self.assertIn('created_at', habit)
        self.assertTrue(len(str(habit['created_at'])) >= 10)

        # 2. Complete habit today
        c_succ, c_msg = models.toggle_habit_today(uid, habit['habit_id'])
        self.assertTrue(c_succ)

        # Verify streak incremented to 1
        updated_habits = models.get_user_habits(uid)
        updated_habit = [h for h in updated_habits if h['habit_id'] == habit['habit_id']][0]
        self.assertEqual(updated_habit['streak_count'], 1)
        self.assertTrue(updated_habit['done_today'])

        # Cleanup
        models.delete_habit(uid, habit['habit_id'])

    # -------------------------------------------------------------
    # 27. Security & Parameterized Query Injection Prevention Tests
    # -------------------------------------------------------------
    def test_34_sql_injection_and_input_sanitization(self):
        user = models.get_user_by_email('aayush@lifeboard.com')
        uid = user['user_id']

        # 1. Attempt SQL injection in Task creation
        sqli_payload = "Normal Task'); DROP TABLE tasks; --"
        dl = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        succ, msg = models.create_task(uid, sqli_payload, "desc", "medium", dl)
        self.assertTrue(succ)

        # Verify tasks table still exists and data was stored safely as plain text
        tasks = models.get_user_tasks(uid, 'all')
        self.assertTrue(any(t['title'] == sqli_payload for t in tasks))

        # Cleanup
        for t in tasks:
            if t['title'] == sqli_payload:
                models.delete_task(uid, t['task_id'])

        # 2. Attempt SQL injection in Expense description
        exp_payload = "' OR 1=1 --"
        log_succ, log_msg = models.log_expense(uid, 100.0, "Other", exp_payload, date.today().strftime('%Y-%m-%d'))
        self.assertTrue(log_succ)

        expenses = models.get_user_expenses(uid, limit=10)
        matching_exp = [e for e in expenses if e['description'] == exp_payload]
        self.assertTrue(len(matching_exp) > 0)
        models.delete_expense(uid, matching_exp[0]['expense_id'])


if __name__ == '__main__':
    unittest.main()



