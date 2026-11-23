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
const phase4Outline = '0045-phase4-prompt-context-outline.html';
assert.equal(current.lessons().length, 44, 'Outlines and planning pages must not count as lessons');
assert.equal(current.lessons()[0].lessonId, 'L01');
assert.equal(current.lessons().at(-1).lessonId, 'L44');
assert.equal(current.context('/lessons/0043-L38-phase3-capstone.html').next.file, phase4Outline);
assert.equal(current.context(`/lessons/${phase4Outline}`).isLesson, false);
assert.equal(current.context(`/lessons/${phase4Outline}`).next.file, '0047-L39-testable-task-contract.html');
assert.equal(current.context('/lessons/0046-phase5-to-11-planned-outlines.html'), null);
assert.equal(current.context('/qa/phase4-qa.html'), null);
assert.deepEqual(Array.from(current.lessons().slice(-6), item => item.lessonId),
  ['L39', 'L40', 'L41', 'L42', 'L43', 'L44']);
for (const item of current.lessons().slice(-6)) {
  const lesson = current.context(`/lessons/${item.file}`);
  assert.equal(lesson.outline.file, phase4Outline);
  assert.equal(lesson.phaseNumber, 4);
  assert.equal(lesson.total, 44);
}

// Add a fixture to the catalog data, leaving the actual published list untouched.
const fixture = `{ file: '0100-L100-catalog-fixture.html', title: 'Test fixture', phase: '第十一阶段' },`;
const withFuture = source.replace('var ITEMS = [', `var ITEMS = [\n    ${fixture}`);
assert.notEqual(withFuture, source, 'Catalog fixture must be inserted');
const futureCatalog = loadCatalog(withFuture);
const future = futureCatalog.context('/ai-agent-learning/lessons/0100-L100-catalog-fixture.html');
assert.equal(future.isLesson, true);
assert.equal(future.lessonId, 'L100');
assert.equal(future.phaseNumber, 11);
assert.equal(future.total, 45);
assert.equal(futureCatalog.context('/lessons/0004-L01-dev-environment-setup.html').lessonId, 'L01');
console.log('Course catalog: published count and L100 compatibility passed');
