import os
import re
import tempfile
import unittest

from werkzeug.security import check_password_hash

from flaskr import app
from flaskr.db import create_user, ensure_schema, get_db, get_rankings, save_result


class AuthenticationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = os.path.join(self.temp_directory.name, 'auth.sqlite')
        app.config.update(
            DATABASE=database_path,
            SECRET_KEY='test-secret',
            TESTING=True,
        )
        with app.app_context():
            ensure_schema()
        self.client = app.test_client()

    def tearDown(self):
        self.temp_directory.cleanup()

    @staticmethod
    def extract_csrf(html):
        match = re.search(r'name="csrf_token" value="([^"]+)"', html)
        if match is None:
            raise AssertionError('CSRF token was not rendered')
        return match.group(1)

    @staticmethod
    def extract_target_token(html):
        match = re.search(r'name="target_token" value="([^"]+)"', html)
        if match is None:
            raise AssertionError('target token was not rendered')
        return match.group(1)

    def register(self, email='new@example.com', username='new-player', password='password123'):
        csrf_token = self.extract_csrf(self.client.get('/auth').get_data(as_text=True))
        return self.client.post(
            '/register',
            data={
                'csrf_token': csrf_token,
                'email': email,
                'username': username,
                'password': password,
            },
        )

    def test_register_hashes_password_and_logs_user_in(self):
        response = self.register()
        self.assertEqual(response.status_code, 302)

        with app.app_context():
            user = get_db().execute(
                'SELECT * FROM users WHERE email = ?',
                ('new@example.com',),
            ).fetchone()
        self.assertIsNotNone(user)
        self.assertNotEqual(user['password_hash'], 'password123')
        self.assertTrue(check_password_hash(user['password_hash'], 'password123'))

        index = self.client.get('/').get_data(as_text=True)
        self.assertIn('new-player でログイン中', index)

        csrf_token = self.extract_csrf(index)
        self.assertEqual(
            self.client.post(
                '/logout',
                data={'csrf_token': csrf_token},
            ).status_code,
            302,
        )
        self.assertIn('認証・ログイン', self.client.get('/').get_data(as_text=True))

    def test_duplicate_registration_and_missing_csrf_are_rejected(self):
        self.assertEqual(self.register().status_code, 302)
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.register(username='another-name').status_code, 400)
        self.assertEqual(
            self.client.post(
                '/register',
                data={
                    'email': 'other@example.com',
                    'username': 'other',
                    'password': 'password123',
                },
            ).status_code,
            400,
        )

    def test_login_uses_email_and_password(self):
        with app.app_context():
            from werkzeug.security import generate_password_hash

            create_user(
                'login@example.com',
                'login-player',
                generate_password_hash('password123'),
            )

        csrf_token = self.extract_csrf(self.client.get('/auth').get_data(as_text=True))
        bad_login = self.client.post(
            '/login',
            data={
                'csrf_token': csrf_token,
                'email': 'login@example.com',
                'password': 'wrong-password',
            },
        )
        self.assertEqual(bad_login.status_code, 400)

        good_login = self.client.post(
            '/login',
            data={
                'csrf_token': csrf_token,
                'email': 'login@example.com',
                'password': 'password123',
            },
        )
        self.assertEqual(good_login.status_code, 302)
        self.assertIn('login-player でログイン中', self.client.get('/').get_data(as_text=True))

    def test_anonymous_practice_is_not_saved(self):
        page = self.client.get('/darts-random-number').get_data(as_text=True)
        token = self.extract_target_token(page)
        response = self.client.post(
            '/success',
            data={'target_token': token, 'count': '2'},
        )
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            count = get_db().execute('SELECT COUNT(*) FROM throw_results').fetchone()[0]
        self.assertEqual(count, 0)

    def test_health_check_and_security_headers(self):
        response = self.client.get('/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'status': 'ok'})
        self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response.headers['X-Frame-Options'], 'DENY')

    def test_public_page_urls_and_legacy_redirects(self):
        current_paths = [
            '/darts-practice',
            '/darts-random-number',
            '/darts-cricket-practice',
            '/darts-weak-number',
            '/darts-success-rate',
        ]
        for path in current_paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

        legacy_paths = {
            '/advanced': '/darts-practice',
            '/next': '/darts-random-number',
            '/cricket': '/darts-cricket-practice',
            '/weakness': '/darts-weak-number',
            '/result': '/darts-success-rate',
        }
        for old_path, current_path in legacy_paths.items():
            with self.subTest(path=old_path):
                response = self.client.get(old_path)
                self.assertEqual(response.status_code, 301)
                self.assertEqual(response.headers['Location'], current_path)

    def test_weekly_and_all_time_rankings_are_calculated(self):
        with app.app_context():
            first = create_user('first@example.com', 'first', 'hash')
            second = create_user('second@example.com', 'second', 'hash')
            save_result(20, 3, 'normal', user_id=first)
            save_result(20, 1, 'normal', user_id=second)
            save_result(19, 3, 'normal', user_id=second)

            first_result_id = get_db().execute(
                'SELECT result_id FROM user_results WHERE user_id = ?',
                (first,),
            ).fetchone()['result_id']
            get_db().execute(
                "UPDATE throw_results SET created_at = '1999-01-01 00:00:00' WHERE id = ?",
                (first_result_id,),
            )
            get_db().commit()

            rankings = get_rankings()
            weekly = get_rankings('2000-01-01 00:00:00')

        self.assertEqual([row['username'] for row in rankings], ['first', 'second'])
        self.assertEqual([row['username'] for row in weekly], ['second'])
        self.assertEqual(rankings[0]['success_rate'], 100.0)
        self.assertEqual(rankings[1]['success_rate'], 66.7)


if __name__ == '__main__':
    unittest.main()
