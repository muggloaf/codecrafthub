# CodeCraftHub Learning Management System

A beginner-friendly Python Flask REST API for tracking developers' learning
goals. Courses are stored in a JSON text file; no database, accounts, or API keys
are needed. This implements the supplied **Part 1, Option B (Python)** lab.

## Features

- Add, list, retrieve, update, and delete courses.
- Track a name, description, target completion date, and learning status.
- Generate numeric IDs and UTC creation timestamps automatically.
- Create `courses.json` automatically when it is first needed.
- Validate required fields, real calendar dates, statuses, and JSON bodies.
- Return JSON errors for missing courses, invalid data, and storage failures.
- Preserve the previous file if writing fails; never reset corrupt data silently.
- Bonus endpoints for course statistics and case-insensitive search.

## Install and run on Windows

Open PowerShell in this directory. Python 3.10 or newer is recommended.

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

The lab's dependency versions are pinned in `requirements.txt`. Using the
virtual environment's Python directly avoids PowerShell activation-policy issues.
The API runs at <http://127.0.0.1:5000>. Leave that terminal running and use a
second terminal for cURL requests.

On Linux or macOS, the equivalent commands are:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

## Course format

```json
{
  "id": 1,
  "name": "Python Basics",
  "description": "Learn Python fundamentals",
  "target_date": "2026-12-31",
  "status": "Not Started",
  "created_at": "2026-10-30 12:00:00"
}
```

The timestamp above is an illustrative format. The server generates the actual
UTC timestamp. Valid status values are exactly `Not Started`, `In Progress`, and
`Completed`. `target_date` must be a real date formatted as `YYYY-MM-DD`.

## API endpoints

| Method | Path | Result |
| --- | --- | --- |
| POST | `/api/courses` | Create a course; 201 with the new course |
| GET | `/api/courses` | List courses and count; 200 |
| GET | `/api/courses/<id>` | Retrieve one course; 200 or 404 |
| PUT | `/api/courses/<id>` | Update supplied editable fields; 200 or 404 |
| DELETE | `/api/courses/<id>` | Delete one course; 200 or 404 |
| GET | `/api/courses/stats` | Count total courses and each status; 200 |
| GET | `/api/courses/search?q=term` | Search names and descriptions; 200 |

POST requires all four editable fields: `name`, `description`, `target_date`, and
`status`. PUT supports the lab's partial-update example; provide at least one of
those fields. The generated `id` and `created_at` cannot be overwritten.

Successful responses include `"success": true`. Error responses include
`"success": false` and a readable `error`. Invalid fields return 400; unknown
courses return 404; file errors return 500. Unknown routes, unsupported methods,
and malformed JSON also receive JSON error responses.

## cURL examples

Run these from the project directory in a second PowerShell terminal. JSON files
avoid Windows command-line quoting problems. On Linux/macOS, replace `curl.exe`
with `curl`.

```powershell
# Create: expect 201. Note the returned ID.
curl.exe -i -X POST http://localhost:5000/api/courses -H "Content-Type: application/json" --data-binary "@examples/create_course.json"

# List: expect 200 and a courses array.
curl.exe -i http://localhost:5000/api/courses

# Retrieve: replace 1 with the returned ID; expect 200.
curl.exe -i http://localhost:5000/api/courses/1

# Partial update: expect 200 with status In Progress.
curl.exe -i -X PUT http://localhost:5000/api/courses/1 -H "Content-Type: application/json" --data-binary "@examples/update_course.json"

# Missing description: expect 400.
curl.exe -i -X POST http://localhost:5000/api/courses -H "Content-Type: application/json" --data-binary "@examples/missing_fields.json"

# Invalid status: expect 400.
curl.exe -i -X POST http://localhost:5000/api/courses -H "Content-Type: application/json" --data-binary "@examples/invalid_status.json"

# Delete the course you created: expect 200.
curl.exe -i -X DELETE http://localhost:5000/api/courses/1

# Retrieve the deleted course: expect 404.
curl.exe -i http://localhost:5000/api/courses/1
```

For example, a request missing `description` returns:

```json
{"success": false, "error": "Missing required field: description"}
```

## Automated testing

Unit tests use temporary files and do not change your saved courses:

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

They cover CRUD, persistence across app instances, ID generation, missing fields,
invalid types/dates/statuses, malformed JSON, unknown courses, immutable fields,
corrupt files, read/write failures, search, and statistics.

With the API running, perform actual cURL requests and save their responses:

```powershell
.\.venv\Scripts\python.exe smoke_test.py
```

This creates one test course, exercises it, then deletes that test course. It
saves the commands, actual JSON responses, and HTTP status codes in
`evidence/curl-output.txt`. Existing courses are not deleted.

## JSON storage

The file contains a JSON array of course objects. Each request reads current
data from disk. Each successful write first produces a temporary file and then
atomically replaces `courses.json`. A process lock keeps simultaneous requests
in this one server process from overwriting each other.

This is a local teaching application. Run one server process; the lock does not
coordinate multiple server processes. Personal course data is ignored by Git.
Set `COURSES_FILE` to use another storage path.

## Troubleshooting

- **Flask is missing:** install requirements using the same virtual environment
  Python that starts the app.
- **Port 5000 is occupied:** set `$env:PORT='5002'`, start the app, and use port
  5002 in your requests. The smoke test accepts `--url http://localhost:5002`.
- **400 response:** read `error` and check the four required fields, exact status,
  and date format.
- **415 response:** add `Content-Type: application/json` to POST/PUT requests.
- **404 response:** use a course ID returned by a successful POST.
- **500 storage error:** verify the directory is writable. If the file is
  malformed, back it up and repair its JSON; the app will not erase it.
- **cURL cannot find a payload file:** run the command from this project directory.

## Project structure

```text
codecrafthub/
  app.py                 Flask application, validation, and JSON helpers
  requirements.txt       Lab-specified dependencies
  test_app.py            Isolated automated unit tests
  smoke_test.py          Real cURL checks and evidence capture
  examples/              Copyable POST/PUT and error payloads
  GENAI_NOTES.md         AI-assisted development and validation notes
  README.md              Setup, API, testing, and troubleshooting
  courses.json           Automatically generated; ignored by Git
  evidence/              Actual local command output; ignored by Git
```

## Scope of the four submission questions

The supplied Part 1 Python lab and its linked exemplar do not include a frontend.
They therefore define no title tag, `.btn-primary`, `.btn-success`, or delete
button markup. Those answers require the separate Part 2 dashboard instructions.
This project does not claim to have completed or submitted that missing part.
