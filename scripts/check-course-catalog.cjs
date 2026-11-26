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
const phase5Outline = '0063-phase5-agent-harness-outline.html';
const phase6Outline = '0069-phase6-langgraph-mcp-outline.html';
const phase7Outline = '0080-phase7-data-rag-outline.html';
const phase8Outline = '0091-phase8-agent-engineering-outline.html';
const phase9Outline = '0097-phase9-advanced-agent-outline.html';
const total = 84;
assert.equal(current.lessons().length, total, 'Outlines and planning pages must not count as lessons');
assert.equal(current.lessons()[0].lessonId, 'L01');
assert.equal(current.lessons().at(-1).lessonId, 'L84');
assert.equal(current.context('/lessons/0043-L38-phase3-capstone.html').next.file, phase4Outline);
assert.equal(current.context(`/lessons/${phase4Outline}`).isLesson, false);
assert.equal(current.context(`/lessons/${phase4Outline}`).next.file, '0047-L39-testable-task-contract.html');
assert.equal(current.context('/lessons/0046-phase5-to-11-planned-outlines.html'), null);
assert.equal(current.context('/qa/phase4-qa.html'), null);
assert.equal(current.context('/qa/phase5-qa.html'), null);
assert.equal(current.context('/lessons/0052-L44-project-acceptance-handoff.html').next.file, phase5Outline);
assert.equal(current.context(`/lessons/${phase5Outline}`).isLesson, false);
assert.equal(current.context(`/lessons/${phase5Outline}`).next.file, '0053-L45-function-workflow-agent.html');
assert.equal(current.context('/lessons/0062-L54-harness-acceptance.html').next.file, phase6Outline);
assert.equal(current.context(`/lessons/${phase6Outline}`).isLesson, false);
assert.equal(current.context(`/lessons/${phase6Outline}`).next.file, '0064-L55-langgraph-state-graph.html');
assert.equal(current.context('/qa/phase6-qa.html'), null);
assert.equal(current.context('/lessons/0068-L59-mcp-skill-authority.html').next.file, phase7Outline);
assert.equal(current.context(`/lessons/${phase7Outline}`).isLesson, false);
assert.equal(current.context(`/lessons/${phase7Outline}`).next.file, '0070-L60-rag-data-access.html');
assert.equal(current.context('/qa/phase7-qa.html'), null);
assert.equal(current.context('/lessons/0079-L69-rag-generation-evals.html').next.file, phase8Outline);
assert.equal(current.context(`/lessons/${phase8Outline}`).isLesson, false);
assert.equal(current.context(`/lessons/${phase8Outline}`).next.file, '0081-L70-agent-telemetry.html');
assert.equal(current.context('/qa/phase8-qa.html'), null);
assert.equal(current.context('/lessons/0090-L79-engineering-baseline-handoff.html').next.file, phase9Outline);
assert.equal(current.context(`/lessons/${phase9Outline}`).isLesson, false);
assert.equal(current.context(`/lessons/${phase9Outline}`).next.file, '0092-L80-reasoning-effort.html');
assert.equal(current.context('/qa/phase9-qa.html'), null);
const phases = [[39, 44, 4, phase4Outline], [45, 54, 5, phase5Outline],
  [55, 59, 6, phase6Outline], [60, 69, 7, phase7Outline], [70, 79, 8, phase8Outline],
  [80, 84, 9, phase9Outline]];
for (const [from, to, phase, outline] of phases) {
  const lessons = current.lessons().slice(from - 1, to);
  assert.deepEqual(Array.from(lessons, item => item.lessonId),
    Array.from({length: to - from + 1}, (_, i) => `L${from + i}`));
  for (const item of lessons) {
    const lesson = current.context(`/lessons/${item.file}`);
    assert.equal(lesson.outline.file, outline);
    assert.equal(lesson.phaseNumber, phase);
    assert.equal(lesson.total, total);
    assert.ok(fs.existsSync(path.join(__dirname, '../lessons', item.file)), `${item.file} is registered but missing`);
  }
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
assert.equal(future.total, total + 1);
assert.equal(futureCatalog.context('/lessons/0004-L01-dev-environment-setup.html').lessonId, 'L01');
console.log('Course catalog: published count and L100 compatibility passed');
