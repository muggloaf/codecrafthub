"""Run real cURL requests against the server and save commands and responses."""
import argparse
import json
from pathlib import Path
import shlex
import shutil
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://127.0.0.1:5000')
args = parser.parse_args()
base = args.url.rstrip('/')
root = Path(__file__).resolve().parent
curl = shutil.which('curl.exe') or shutil.which('curl')
if not curl:
    raise SystemExit('Install cURL before running the smoke test.')
evidence = root / 'evidence'
evidence.mkdir(exist_ok=True)
transcript = []


def call(label, method, endpoint, expected, payload=None):
    command = [curl, '-sS', '-X', method, base + endpoint]
    if payload:
        command += ['-H', 'Content-Type: application/json',
                    '--data-binary', '@examples/' + payload]
    command += ['-w', '\n%{http_code}']
    result = subprocess.run(command, cwd=root, capture_output=True,
                            text=True, check=True, timeout=15)
    body, status = result.stdout.rsplit('\n', 1)
    parsed = json.loads(body)
    transcript.extend([label, shlex.join(command), body, 'HTTP ' + status, ''])
    assert int(status) == expected, f'{label}: expected {expected}, got {status}'
    print(f'{label}: HTTP {status}, passed')
    return parsed


try:
    created = call('Create course', 'POST', '/api/courses', 201,
                   'create_course.json')
    identifier = created['course']['id']
    call('List courses', 'GET', '/api/courses', 200)
    call('Retrieve course', 'GET', f'/api/courses/{identifier}', 200)
    updated = call('Update course', 'PUT', f'/api/courses/{identifier}', 200,
                   'update_course.json')
    assert updated['course']['status'] == 'In Progress'
    call('Missing required fields', 'POST', '/api/courses', 400,
         'missing_fields.json')
    call('Invalid status', 'POST', '/api/courses', 400, 'invalid_status.json')
    call('Delete test course', 'DELETE', f'/api/courses/{identifier}', 200)
    call('Deleted course not found', 'GET', f'/api/courses/{identifier}', 404)
    call('Course statistics', 'GET', '/api/courses/stats', 200)
finally:
    (evidence / 'curl-output.txt').write_text('\n'.join(transcript),
                                           encoding='utf-8')
