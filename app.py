"""CodeCraftHub: a small Flask REST API backed by a JSON file."""
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from threading import RLock

from flask import Flask, current_app, jsonify, request, send_file
from werkzeug.exceptions import HTTPException


STATUSES = ('Not Started', 'In Progress', 'Completed')
COURSE_FIELDS = ('name', 'description', 'target_date', 'status')
# This lock protects a read/change/write operation within one server process.
STORAGE_LOCK = RLock()


class StorageError(Exception):
    """A storage problem that the API can report without losing existing data."""


def save_courses(courses):
    """Write a temporary file, then replace the original only after a full write."""
    path = Path(current_app.config['COURSES_FILE'])
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8', dir=path.parent,
                prefix=path.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(courses, stream, indent=2, ensure_ascii=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except (OSError, TypeError, ValueError) as error:
        raise StorageError('Unable to save course data') from error
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                current_app.logger.warning('Unable to remove temporary data file')


def load_courses():
    """Load fresh data for each request; automatically initialize a missing file."""
    path = Path(current_app.config['COURSES_FILE'])
    try:
        if not path.exists():
            save_courses([])
        with path.open(encoding='utf-8') as stream:
            courses = json.load(stream)
    except (OSError, ValueError) as error:
        raise StorageError('Unable to read course data') from error
    # Refuse to overwrite a corrupt or unexpected storage structure.
    if not isinstance(courses, list):
        raise StorageError('Course data must be a JSON array')
    identifiers = set()
    for course in courses:
        if (not isinstance(course, dict) or
                type(course.get('id')) is not int or course['id'] < 1 or
                course['id'] in identifiers or
                not isinstance(course.get('created_at'), str) or
                validate_course(course, stored=True) is not None):
            raise StorageError('Course data contains an invalid record')
        identifiers.add(course['id'])
    return courses


def get_next_id(courses):
    """Start at 1 and otherwise choose one above the largest stored ID."""
    return max((course['id'] for course in courses), default=0) + 1


def validate_course(data, partial=False, stored=False):
    """Return a readable error message, or None when the values are valid."""
    if not isinstance(data, dict):
        return 'Request body must be a JSON object'
    if not stored and set(data) - set(COURSE_FIELDS):
        return 'Only name, description, target_date, and status can be supplied'
    if partial and not data:
        return 'Provide at least one course field to update'
    for field in COURSE_FIELDS:
        if field not in data:
            if not partial:
                return f'Missing required field: {field}'
            continue
        if not isinstance(data[field], str) or not data[field].strip():
            return f'{field} must be a non-empty string'
    if 'target_date' in data:
        value = data['target_date']
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) is None:
            return 'target_date must be a valid date in YYYY-MM-DD format'
        try:
            date.fromisoformat(value)
        except ValueError:
            return 'target_date must be a valid date in YYYY-MM-DD format'
    if 'status' in data and data['status'] not in STATUSES:
        return 'status must be Not Started, In Progress, or Completed'
    return None


def create_app(config=None):
    """Allow tests to use temporary JSON files instead of changing real courses."""
    app = Flask(__name__)
    app.config['COURSES_FILE'] = os.getenv(
        'COURSES_FILE', str(Path(__file__).with_name('courses.json')))
    if config:
        app.config.update(config)

    @app.after_request
    def allow_local_dashboard(response):
        # Live Server uses another origin. Allow its default local ports only.
        allowed_origins = {
            f'http://{host}:{port}' for host in ('localhost', '127.0.0.1')
            for port in (5000, 5500, 5501)
        }
        origin = request.headers.get('Origin')
        if origin in allowed_origins:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            response.headers['Access-Control-Allow-Methods'] = (
                'GET, POST, PUT, DELETE, OPTIONS')
            response.vary.add('Origin')
        return response

    @app.get('/dashboard')
    @app.get('/index.html')
    def dashboard():
        return send_file(Path(__file__).with_name('index.html'))

    @app.errorhandler(StorageError)
    def storage_error(error):
        app.logger.error('Course storage error: %s', error)
        return jsonify(success=False, error=str(error)), 500

    @app.errorhandler(HTTPException)
    def http_error(error):
        # Invalid JSON, unknown URLs, and unsupported methods also return JSON.
        return jsonify(success=False, error=error.description), error.code

    @app.get('/')
    def home():
        return jsonify(
            success=True, message='Welcome to the CodeCraftHub API',
            endpoints={
                'courses': '/api/courses',
                'course': '/api/courses/<id>',
                'statistics': '/api/courses/stats',
                'search': '/api/courses/search?q=python'})

    @app.get('/api/courses')
    def get_courses():
        with STORAGE_LOCK:
            courses = load_courses()
        return jsonify(success=True, count=len(courses), courses=courses)

    @app.post('/api/courses')
    def add_course():
        data = request.get_json()
        error = validate_course(data)
        if error:
            return jsonify(success=False, error=error), 400
        with STORAGE_LOCK:
            courses = load_courses()
            course = {field: data[field].strip() for field in COURSE_FIELDS}
            course['id'] = get_next_id(courses)
            course['created_at'] = datetime.now(timezone.utc).strftime(
                '%Y-%m-%d %H:%M:%S')
            courses.append(course)
            save_courses(courses)
        response = jsonify(success=True, message='Course added successfully',
                           course=course)
        response.headers['Location'] = f"/api/courses/{course['id']}"
        return response, 201

    @app.get('/api/courses/<int:course_id>')
    def get_course(course_id):
        with STORAGE_LOCK:
            courses = load_courses()
        course = next((item for item in courses if item['id'] == course_id), None)
        if course is None:
            return jsonify(success=False, error='Course not found'), 404
        return jsonify(success=True, course=course)

    @app.put('/api/courses/<int:course_id>')
    def update_course(course_id):
        data = request.get_json()
        error = validate_course(data, partial=True)
        if error:
            return jsonify(success=False, error=error), 400
        with STORAGE_LOCK:
            courses = load_courses()
            course = next((item for item in courses
                           if item['id'] == course_id), None)
            if course is None:
                return jsonify(success=False, error='Course not found'), 404
            course.update({field: value.strip() for field, value in data.items()})
            save_courses(courses)
        return jsonify(success=True, message='Course updated successfully',
                       course=course)

    @app.delete('/api/courses/<int:course_id>')
    def delete_course(course_id):
        with STORAGE_LOCK:
            courses = load_courses()
            remaining = [item for item in courses if item['id'] != course_id]
            if len(remaining) == len(courses):
                return jsonify(success=False, error='Course not found'), 404
            save_courses(remaining)
        return jsonify(success=True, message='Course deleted successfully')

    @app.get('/api/courses/stats')
    def get_statistics():
        with STORAGE_LOCK:
            courses = load_courses()
        return jsonify(success=True, statistics={
            'total_courses': len(courses),
            'not_started': sum(item['status'] == 'Not Started' for item in courses),
            'in_progress': sum(item['status'] == 'In Progress' for item in courses),
            'completed': sum(item['status'] == 'Completed' for item in courses)})

    @app.get('/api/courses/search')
    def search_courses():
        query = request.args.get('q', '').strip().casefold()
        with STORAGE_LOCK:
            courses = load_courses()
        matches = [item for item in courses if
                   query in item['name'].casefold() or
                   query in item['description'].casefold()]
        return jsonify(success=True, count=len(matches), courses=matches)

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.getenv('PORT', '5000'))
    with app.app_context(), STORAGE_LOCK:
        load_courses()
    print('CodeCraftHub API is starting...')
    print('Data will be stored in:', app.config['COURSES_FILE'])
    print(f'API will be available at: http://localhost:{port}')
    app.run(host='127.0.0.1', port=port, debug=False)
