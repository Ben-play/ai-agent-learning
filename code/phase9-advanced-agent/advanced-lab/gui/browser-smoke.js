"use strict";

// Run only this fixed fixture's button sequence, never on a hosted page.
if (location.protocol === "file:" && location.hash === "#browser-smoke") {
  (() => {
    const byId = (id) => document.getElementById(id);
    const result = byId("browser-smoke");
    const text = "导出文件生成后保留 7 天。";
    const source = "EXPORT-POLICY/v1 §1（合成）";

    function expect(id, value) {
      if (byId(id).textContent !== value) throw new Error(`${id}: expected ${value}`);
    }

    function click(id) {
      const button = byId(id);
      if (button.disabled) throw new Error(`${id}: unexpectedly disabled`);
      button.click();
    }

    function legacyState(status, draft = "—", citation = "—") {
      expect("legacy-status", status);
      expect("legacy-text", draft);
      expect("legacy-source", citation);
    }

    result.hidden = false;
    try {
      click("stable-start");
      expect("stable-status", "previewed · #1");
      expect("stable-text", text);
      expect("stable-source", source);
      expect("legacy-queue", "0");

      click("legacy-start");
      legacyState("pending · #1");
      click("legacy-cancel");
      legacyState("cancelled · #1");
      expect("legacy-queue", "1");
      click("legacy-deliver");
      legacyState("cancelled · #1");
      expect("legacy-delivery", "已忽略");
      expect("legacy-queue", "0");

      click("legacy-start");
      click("legacy-cancel");
      click("legacy-start");
      legacyState("pending · #3");
      expect("legacy-queue", "2");
      click("legacy-deliver");
      legacyState("pending · #3");
      expect("legacy-delivery", "已忽略");
      click("legacy-deliver");
      legacyState("previewed · #3", text, source);
      expect("legacy-delivery", "已接受");
      expect("legacy-queue", "0");
      if (!byId("legacy-cancel").disabled) throw new Error("terminal state can still be cancelled");

      result.textContent = "L82 BROWSER SMOKE PASSED";
    } catch (error) {
      result.textContent = `L82 BROWSER SMOKE FAILED: ${error.message}`;
    }
  })();
}
