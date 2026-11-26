"use strict";

(() => {
  const { createPreviewController } = globalThis.L82Preview;
  const byId = (id) => document.getElementById(id);
  const stable = createPreviewController({ hasStableInterface: true });
  const queue = [];
  const legacy = createPreviewController({
    hasStableInterface: false,
    queueLegacy: (complete) => queue.push(complete),
  });

  const stableStart = byId("stable-start");
  const legacyStart = byId("legacy-start");
  const cancel = byId("legacy-cancel");
  const deliver = byId("legacy-deliver");
  const queueSize = byId("legacy-queue");
  const lastDelivery = byId("legacy-delivery");

  function renderReceipt(prefix, { attempt, status, preview }) {
    byId(`${prefix}-status`).textContent = `${status} · #${attempt}`;
    byId(`${prefix}-text`).textContent = preview?.text ?? "—";
    byId(`${prefix}-source`).textContent = preview?.source ?? "—";
  }

  function updateLegacyControls() {
    const pending = legacy.snapshot().status === "pending";
    legacyStart.disabled = pending;
    cancel.disabled = !pending;
    deliver.disabled = queue.length === 0;
    queueSize.textContent = String(queue.length);
  }

  stableStart.addEventListener("click", () => {
    stable.start();
    renderReceipt("stable", stable.snapshot());
  });
  legacyStart.addEventListener("click", () => {
    if (legacy.start()) renderReceipt("legacy", legacy.snapshot());
    updateLegacyControls();
  });
  cancel.addEventListener("click", () => {
    if (legacy.cancel()) renderReceipt("legacy", legacy.snapshot());
    updateLegacyControls();
  });
  deliver.addEventListener("click", () => {
    if (!queue.length) return;
    const accepted = queue.shift()();
    if (accepted) renderReceipt("legacy", legacy.snapshot());
    lastDelivery.textContent = accepted ? "已接受" : "已忽略";
    updateLegacyControls();
  });

  stableStart.disabled = false;
  updateLegacyControls();
})();
