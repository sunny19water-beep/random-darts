import os
import re
import tempfile
import unittest
from unittest.mock import patch

from flaskr import app, get_weakness_analysis
from flaskr.db import ensure_schema, get_db, save_result


class ResultSecurityTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = os.path.join(self.temp_directory.name, 'test.sqlite')
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
    def extract_token(html):
        match = re.search(r'name="target_token" value="([^"]+)"', html)
        if match is None:
            raise AssertionError('target token was not rendered')
        return match.group(1)

    @staticmethod
    def extract_target_number(html):
        match = re.search(r'data-target-number="([^"]+)"', html)
        if match is None:
            raise AssertionError('target number was not rendered')
        return match.group(1)

    def test_normal_target_cannot_be_changed_or_replayed(self):
        with patch('flaskr.draw_number', return_value=20):
            html = self.client.get('/next').get_data(as_text=True)

        self.assertNotIn('name="number"', html)
        token = self.extract_token(html)
        response = self.client.post(
            '/success',
            data={'target_token': token, 'number': '1', 'count': '2'},
        )
        self.assertEqual(response.status_code, 302)

        with app.app_context():
            result = get_db().execute(
                'SELECT number, success_count FROM throw_results'
            ).fetchone()
        self.assertEqual(tuple(result), ('20', 2))

        replay = self.client.post(
            '/success',
            data={'target_token': token, 'count': '2'},
        )
        self.assertEqual(replay.status_code, 400)

    def test_advanced_target_uses_server_values(self):
        with patch('flaskr.draw_advanced_numbers', return_value=(18, 'Triple')):
            html = self.client.get('/advanced').get_data(as_text=True)

        self.assertNotIn('name="number"', html)
        self.assertNotIn('name="bed"', html)
        token = self.extract_token(html)
        response = self.client.post(
            '/advanced/success',
            data={
                'target_token': token,
                'number': '1',
                'bed': 'Single',
                'count': '1',
            },
        )
        self.assertEqual(response.status_code, 302)

        with app.app_context():
            result = get_db().execute(
                'SELECT number, bed, success_count FROM throw_results'
            ).fetchone()
        self.assertEqual(tuple(result), ('18', 'Triple', 1))

    def test_weak_numbers_are_the_seven_lowest_rates_after_fifty_throws(self):
        with app.app_context():
            for number in range(1, 9):
                remaining_successes = number - 1
                for _ in range(3):
                    successes = min(3, remaining_successes)
                    save_result(number, successes, 'normal')
                    remaining_successes -= successes

            analysis = get_weakness_analysis()

        weak_numbers = [stat['number'] for stat in analysis['weak_numbers']]
        self.assertEqual(weak_numbers, [str(number) for number in range(1, 8)])

    def test_weakness_practice_requires_enough_data(self):
        page = self.client.get('/weakness').get_data(as_text=True)
        self.assertIn('あと 50 本', page)
        self.assertNotIn('name="target_token"', page)

    def test_weakness_practice_targets_and_saves_weak_number(self):
        with app.app_context():
            for _ in range(16):
                save_result(1, 1, 'normal')
            for _ in range(3):
                save_result(20, 0, 'normal')

        page = self.client.get('/weakness').get_data(as_text=True)
        self.assertIn('苦手ナンバーを練習しましょう', page)
        self.assertEqual(self.extract_target_number(page), '20')
        token = self.extract_token(page)

        response = self.client.post(
            '/weakness/success',
            data={'target_token': token, 'number': '1', 'count': '2'},
        )
        self.assertEqual(response.status_code, 302)

        with app.app_context():
            result = get_db().execute(
                'SELECT number, success_count FROM throw_results ORDER BY id DESC LIMIT 1'
            ).fetchone()
        self.assertEqual(tuple(result), ('20', 2))

        next_page = self.client.get('/weakness').get_data(as_text=True)
        self.assertEqual(self.extract_target_number(next_page), '1')


if __name__ == '__main__':
    unittest.main()
