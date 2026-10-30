"""Run with: python -m unittest -v"""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import create_app


class CourseAPITests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'courses.json'
        self.app = create_app({'TESTING': True, 'COURSES_FILE': str(self.path)})
        self.client = self.app.test_client()
        self.course = {'name': 'Python Basics',
                       'description': 'Learn Python fundamentals',
                       'target_date': '2026-12-31', 'status': 'Not Started'}

    def test_missing_file_is_created_automatically(self):
        response = self.client.get('/api/courses')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['courses'], [])
        self.assertEqual(json.loads(self.path.read_text()), [])

    def test_complete_crud_flow_and_persistence(self):
        added = self.client.post('/api/courses', json=self.course)
        self.assertEqual(added.status_code, 201)
        self.assertEqual(added.json['course']['id'], 1)
        self.assertIn('created_at', added.json['course'])
        self.assertEqual(added.headers['Location'], '/api/courses/1')
        # A second app instance reads the same data from disk.
        other = create_app({'TESTING': True, 'COURSES_FILE': str(self.path)})
        response = other.test_client().get('/api/courses/1')
        self.assertEqual(response.json['course']['name'], 'Python Basics')
        updated = self.client.put('/api/courses/1', json={'status': 'In Progress'})
        self.assertEqual(updated.json['course']['status'], 'In Progress')
        self.assertEqual(updated.json['course']['created_at'],
                         added.json['course']['created_at'])
        self.assertEqual(self.client.get('/api/courses').json['count'], 1)
        self.assertEqual(self.client.delete('/api/courses/1').status_code, 200)
        self.assertEqual(self.client.get('/api/courses/1').status_code, 404)
        self.assertEqual(json.loads(self.path.read_text()), [])

    def test_identifiers_are_generated(self):
        for identifier in (1, 2, 3):
            response = self.client.post('/api/courses', json=self.course)
            self.assertEqual(response.json['course']['id'], identifier)
        self.client.delete('/api/courses/2')
        self.assertEqual(self.client.post('/api/courses', json=self.course)
                         .json['course']['id'], 4)

    def test_each_required_field(self):
        for field in self.course:
            with self.subTest(field=field):
                body = self.course.copy()
                del body[field]
                response = self.client.post('/api/courses', json=body)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json['error'],
                                 f'Missing required field: {field}')

    def test_invalid_values(self):
        invalid = [('name', ''), ('description', '   '), ('name', 3),
                   ('status', 'Finished'), ('target_date', '2026-02-30'),
                   ('target_date', '20261231'), ('target_date', None)]
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                body = {**self.course, field: value}
                self.assertEqual(self.client.post('/api/courses', json=body)
                                 .status_code, 400)

    def test_invalid_json_and_non_object_bodies(self):
        response = self.client.post('/api/courses', data='{broken',
                                    content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json['success'])
        self.assertEqual(self.client.post('/api/courses', json=[]).status_code,
                         400)

    def test_unknown_courses_and_methods(self):
        self.assertEqual(self.client.get('/api/courses/999').status_code, 404)
        self.assertEqual(self.client.put('/api/courses/999',
                                        json={'status': 'Completed'})
                         .status_code, 404)
        self.assertEqual(self.client.delete('/api/courses/999').status_code, 404)
        self.assertEqual(self.client.patch('/api/courses/1').status_code, 405)

    def test_update_validation_and_readonly_fields(self):
        self.client.post('/api/courses', json=self.course)
        for body in ({}, {'id': 2}, {'created_at': 'changed'},
                     {'status': 'Finished'}, {'target_date': 'invalid'}):
            with self.subTest(body=body):
                self.assertEqual(self.client.put('/api/courses/1', json=body)
                                 .status_code, 400)
        self.assertEqual(self.client.get('/api/courses/1').json['course']['id'], 1)

    def test_corrupt_file_is_preserved(self):
        self.path.write_text('{invalid json', encoding='utf-8')
        response = self.client.get('/api/courses')
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.json['success'])
        self.assertEqual(self.path.read_text(), '{invalid json')

    def test_invalid_stored_structure_is_rejected(self):
        for content in ('{}', '[{"id": 1}]', '[null]'):
            with self.subTest(content=content):
                self.path.write_text(content, encoding='utf-8')
                self.assertEqual(self.client.get('/api/courses').status_code, 500)
                self.assertEqual(self.path.read_text(), content)

    def test_write_failure_keeps_original_data(self):
        self.client.post('/api/courses', json=self.course)
        before = self.path.read_bytes()
        with patch('app.os.replace', side_effect=OSError('disk full')):
            response = self.client.put('/api/courses/1',
                                       json={'status': 'Completed'})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob('*.tmp')), [])

    def test_read_failure_returns_json_error(self):
        with patch('app.Path.open', side_effect=PermissionError('denied')):
            response = self.client.get('/api/courses')
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.json['success'])

    def test_search_and_statistics(self):
        self.client.post('/api/courses', json=self.course)
        self.client.post('/api/courses', json={**self.course, 'name': 'Java',
                                              'status': 'Completed'})
        result = self.client.get('/api/courses/search?q=PYTHON').json
        self.assertEqual(result['count'], 2)  # Both descriptions mention Python.
        self.assertEqual(self.client.get('/api/courses/search?q=unknown')
                         .json['count'], 0)
        stats = self.client.get('/api/courses/stats').json['statistics']
        self.assertEqual(stats, {'total_courses': 2, 'not_started': 1,
                                 'in_progress': 0, 'completed': 1})


if __name__ == '__main__':
    unittest.main()
