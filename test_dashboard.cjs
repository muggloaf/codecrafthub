// DOM integration test: use jsdom and a separate, empty test API instance.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM } = require('jsdom');

async function waitFor(condition, description) {
  const deadline = Date.now() + 10000;
  while (!condition()) {
    if (Date.now() > deadline) throw new Error('Timed out: ' + description);
    await new Promise(resolve => setTimeout(resolve, 20));
  }
}

(async () => {
  const api = process.env.TEST_API_URL;
  if (!api) throw new Error('Set TEST_API_URL to an isolated test API, not personal course data.');
  const initial = await fetch(api + '/api/courses').then(response => response.json());
  assert.equal(initial.count, 0, 'Test API must have an empty, temporary data file.');
  const dom = new JSDOM(fs.readFileSync('index.html', 'utf8'), {
    url: 'http://localhost:5000/dashboard', runScripts: 'dangerously',
    beforeParse(window) {
      window.fetch = (url, options) => fetch(url.replace('http://localhost:5000', api), options);
      window.confirm = () => true;
      window.HTMLElement.prototype.scrollIntoView = () => {};
    }
  });
  const { window } = dom;
  const document = window.document;
  const form = document.getElementById('course-form');
  const message = document.getElementById('message');
  const rows = () => document.querySelectorAll('#course-list tr');
  const ready = () => document.getElementById('loading').hidden;
  const submit = () => form.dispatchEvent(new window.Event('submit', { bubbles: true, cancelable: true }));
  try {
    await waitFor(ready, 'initial course load');
    assert.equal(document.title, 'CodeCraftHub: Your Learning Management Platform');
    assert.equal(window.getComputedStyle(document.getElementById('refresh-button')).backgroundColor,
      'rgb(139, 92, 246)');
    assert.equal(window.getComputedStyle(document.getElementById('save-button')).backgroundColor,
      'rgb(245, 158, 11)');
    assert.equal(document.getElementById('empty-state').hidden, false);
    console.log('Initial load, title, theme colors, and empty state passed');

    form.elements.namedItem('name').value = 'DOM integration course';
    form.elements.namedItem('description').value = '<img src=x onerror=alert(1)> Learn safely';
    form.elements.namedItem('target_date').value = '2026-12-31';
    submit();
    await waitFor(() => ready() && rows().length === 1, 'course creation');
    assert.match(message.textContent, /added successfully/);
    assert.equal(document.querySelector('#course-list img'), null);
    const remove = document.querySelector('#course-list .btn-danger');
    assert.equal(remove.textContent, 'Remove');
    assert.equal(window.getComputedStyle(remove).backgroundColor, 'rgb(239, 68, 68)');
    console.log('Create, safe text rendering, and red Remove button passed');

    document.querySelector('#course-list .btn-primary').click();
    await waitFor(() => ready() && !document.getElementById('cancel-button').hidden,
      'editing form load');
    form.elements.namedItem('status').value = 'Completed';
    submit();
    await waitFor(() => ready() && document.querySelector('#course-list .status').textContent === 'Completed',
      'course update');
    assert.match(message.textContent, /updated successfully/);
    assert.equal(document.getElementById('completed-count').textContent, '1');
    console.log('Read-one, edit, update, and summary counters passed');

    window.confirm = () => false;
    document.querySelector('#course-list .btn-danger').click();
    assert.equal(rows().length, 1);
    window.confirm = () => true;
    document.querySelector('#course-list .btn-danger').click();
    await waitFor(() => ready() && rows().length === 0, 'course removal');
    assert.match(message.textContent, /removed successfully/);
    console.log('Cancel removal and confirmed deletion passed');

    window.fetch = async () => { throw new Error('Simulated offline API'); };
    document.getElementById('refresh-button').click();
    await waitFor(() => ready() && message.className === 'error', 'offline error');
    assert.match(message.textContent, /Cannot reach the API/);
    assert.equal(document.getElementById('refresh-button').disabled, false);
    console.log('API failure message and loading-state recovery passed');
  } finally {
    dom.window.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
