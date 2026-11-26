"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const { createPreviewController } = require("./controller.js");

const expectedPreview = {
  text: "导出文件生成后保留 7 天。",
  source: "EXPORT-POLICY/v1 §1（合成）",
};

test("a stable application interface returns the draft and source without queuing GUI work", () => {
  const controller = createPreviewController({
    hasStableInterface: true,
    queueLegacy() { assert.fail("the stable route must not queue a GUI callback"); },
  });
  assert.equal(controller.start(), true);
  assert.deepEqual(controller.snapshot(), {
    route: "stable-interface", attempt: 1, status: "previewed", preview: expectedPreview,
  });
});

test("the legacy route has no draft until its queued callback runs", () => {
  const queued = [];
  const controller = createPreviewController({
    hasStableInterface: false,
    queueLegacy: (complete) => queued.push(complete),
  });
  assert.equal(controller.start(), true);
  assert.equal(controller.start(), false, "only one attempt can be pending");
  assert.deepEqual(controller.snapshot(), {
    route: "legacy-gui", attempt: 1, status: "pending", preview: null,
  });
  assert.equal(queued.length, 1);
  assert.equal(queued[0](), true);
  assert.deepEqual(controller.snapshot(), {
    route: "legacy-gui", attempt: 1, status: "previewed", preview: expectedPreview,
  });
});

test("a callback actually delivered after cancellation cannot publish a draft", () => {
  const queued = [];
  const controller = createPreviewController({
    hasStableInterface: false,
    queueLegacy: (complete) => queued.push(complete),
  });
  assert.equal(controller.cancel(), false);
  controller.start();
  assert.equal(controller.cancel(), true);
  const cancelled = controller.snapshot();
  assert.deepEqual(cancelled, {
    route: "legacy-gui", attempt: 1, status: "cancelled", preview: null,
  });
  assert.equal(queued[0](), false);
  assert.deepEqual(controller.snapshot(), cancelled);
  assert.equal(controller.cancel(), false);
});

test("a retry accepts only its own completion, even if the old callback arrives first", () => {
  const queued = [];
  const controller = createPreviewController({
    hasStableInterface: false,
    queueLegacy: (complete) => queued.push(complete),
  });
  controller.start();
  controller.cancel();
  controller.start();
  assert.equal(queued[0](), false);
  assert.deepEqual(controller.snapshot(), {
    route: "legacy-gui", attempt: 2, status: "pending", preview: null,
  });
  assert.equal(queued[1](), true);
  const previewed = controller.snapshot();
  assert.deepEqual(previewed, {
    route: "legacy-gui", attempt: 2, status: "previewed", preview: expectedPreview,
  });
  assert.equal(queued[1](), false, "duplicate completion cannot publish again");
  assert.equal(controller.cancel(), false, "cancellation is not undo");
  assert.deepEqual(controller.snapshot(), previewed);
});
