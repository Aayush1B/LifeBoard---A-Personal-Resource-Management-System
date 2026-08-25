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

        # Add a new habit (FR-15)
        success, msg = models.add_habit(uid, 'Test Streak Habit')
        self.assertTrue(success)

        habits = models.get_user_habits(uid)
        target = [h for h in habits if h['habit_name'] == 'Test Streak Habit'][0]

        # First completion today -> Streak should become 1
        t_success, t_msg = models.toggle_habit_today(uid, target['habit_id'])
        self.assertTrue(t_success)

        updated_habits = models.get_user_habits(uid)
        updated_target = [h for h in updated_habits if h['habit_id'] == target['habit_id']][0]
        self.assertEqual(updated_target['streak_count'], 1)
        self.assertEqual(updated_target['done_today'], 1)

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

        # Test history limit (FR-20)
        history = models.get_user_bmi_history(uid, limit=10)
        self.assertGreater(len(history), 0)
        self.assertLessEqual(len(history), 10)

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

        report = models.generate_monthly_report_data(uid, today.month, today.year)
        self.assertIn('health', report)
        self.assertIn('tasks', report)
        self.assertIn('finance', report)
        self.assertGreaterEqual(report['health']['workouts_count'], 0)

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
        self.assertGreater(len(briefing['message']), 10)

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

if __name__ == '__main__':
    unittest.main()


