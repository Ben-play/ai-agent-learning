const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../assets/course-catalog.js'), 'utf8');

function loadCatalog(script) {
  const context = { window: {} };
  vm.runInNewContext(script, context, { filename: 'course-catalog.js' });
  return context.window.CourseCatalog;
}

const current = loadCatalog(source);
assert.equal(current.lessons().length, 38, 'Planning pages must not become completed lessons');
assert.equal(current.lessons()[0].lessonId, 'L01');
assert.equal(current.lessons().at(-1).lessonId, 'L38');
assert.equal(current.context('/lessons/0043-L38-phase3-capstone.html').total, 38);

// Add a fixture to the catalog data, leaving the actual published list untouched.
const fixture = `{ file: '0100-L100-catalog-fixture.html', title: 'Test fixture', phase: '第十一阶段' },`;
const withFuture = source.replace('var ITEMS = [', `var ITEMS = [\n    ${fixture}`);
assert.notEqual(withFuture, source, 'Catalog fixture must be inserted');
const futureCatalog = loadCatalog(withFuture);
const future = futureCatalog.context('/ai-agent-learning/lessons/0100-L100-catalog-fixture.html');
assert.equal(future.isLesson, true);
assert.equal(future.lessonId, 'L100');
assert.equal(future.phaseNumber, 11);
assert.equal(future.total, 39);
assert.equal(futureCatalog.context('/lessons/0004-L01-dev-environment-setup.html').lessonId, 'L01');
console.log('Course catalog: published count and L100 compatibility passed');
