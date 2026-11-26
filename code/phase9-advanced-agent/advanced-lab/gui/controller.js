"use strict";

(() => {
  const draft = Object.freeze({
    text: "导出文件生成后保留 7 天。",
    source: "EXPORT-POLICY/v1 §1（合成）",
  });

  function createPreviewController({ hasStableInterface, queueLegacy }) {
    const route = hasStableInterface ? "stable-interface" : "legacy-gui";
    let state = Object.freeze({ route, attempt: 0, status: "idle", preview: null });

    function start() {
      if (state.status === "pending") return false;
      const attempt = state.attempt + 1;
      if (hasStableInterface) {
        // The simulated stable app interface returns the draft directly.
        state = Object.freeze({ route, attempt, status: "previewed", preview: draft });
      } else {
        state = Object.freeze({ route, attempt, status: "pending", preview: null });
        queueLegacy(() => {
          // A pending retry does not authorize completion of the previous attempt.
          if (state.status !== "pending" || state.attempt !== attempt) return false;
          state = Object.freeze({ route, attempt, status: "previewed", preview: draft });
          return true;
        });
      }
      return true;
    }

    function cancel() {
      if (state.status !== "pending") return false;
      state = Object.freeze({ ...state, status: "cancelled" });
      return true;
    }

    return { start, cancel, snapshot: () => state };
  }

  const api = Object.freeze({ createPreviewController });
  if (typeof module === "object" && module.exports) module.exports = api;
  else globalThis.L82Preview = api;
})();
