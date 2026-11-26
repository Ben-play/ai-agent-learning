"use strict";

const { createPreviewController } = require("./controller.js");

function fixture(hasStableInterface) {
  const queued = [];
  return {
    queued,
    controller: createPreviewController({
      hasStableInterface,
      queueLegacy: (complete) => queued.push(complete),
    }),
  };
}

function worked() {
  const stable = fixture(true);
  stable.controller.start();

  const { controller, queued } = fixture(false);
  controller.start();
  const pending = controller.snapshot();
  const completionAccepted = queued.shift()();
  const terminal = controller.snapshot();

  controller.start();
  controller.cancel();
  const beforeLate = controller.snapshot();
  const lateAccepted = queued.shift()();

  return {
    stable: { terminal: stable.controller.snapshot(), queued: stable.queued.length },
    legacy: { pending, completionAccepted, terminal },
    cancelled: { beforeLate, lateAccepted, afterLate: controller.snapshot() },
  };
}

function transfer() {
  const { controller, queued } = fixture(false);
  controller.start();
  controller.cancel();
  const cancelled = controller.snapshot();
  controller.start();
  const retryPending = controller.snapshot();

  const staleAccepted = queued[0]();
  const afterStale = controller.snapshot();
  const currentAccepted = queued[1]();
  const terminal = controller.snapshot();
  const duplicateAccepted = queued[1]();
  const cancelAfterCompletion = controller.cancel();

  return {
    cancelled, retryPending, staleAccepted, afterStale, currentAccepted, terminal,
    duplicateAccepted, cancelAfterCompletion, afterDuplicate: controller.snapshot(),
  };
}

const mode = process.argv[2];
if (process.argv.length === 3 && (mode === "worked" || mode === "transfer")) {
  const result = mode === "worked" ? worked() : transfer();
  console.log(JSON.stringify({ fixture: "l82-export-preview/v1", ...result }));
} else {
  console.error("Usage: node run.cjs worked|transfer");
  process.exitCode = 1;
}
