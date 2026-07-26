(() => {
  "use strict";

  const endpoint = "/api/manual/unattended-control";
  const state = {
    csrfToken: null,
    generationDigest: null,
    reviewedFilesDigest: null,
    revision: 0,
    busy: false,
  };

  const label = document.querySelector("#unattended-control-state");
  const reason = document.querySelector("#unattended-control-reason");
  const onButton = document.querySelector("#unattended-control-on");
  const offButton = document.querySelector("#unattended-control-off");

  function render(payload) {
    state.generationDigest = payload.generation_digest;
    state.reviewedFilesDigest = payload.reviewed_files_digest;
    state.revision = payload.revision;
    if (payload.csrf_token) state.csrfToken = payload.csrf_token;
    const effective = payload.effective_state || "HALTED";
    label.textContent = effective;
    reason.textContent =
      `${payload.reason_label} · ${payload.entries_today ?? "—"} / ` +
      `${payload.maximum_entries_per_day} attempts`;
    const armed = payload.desired_state === "ARMED";
    onButton.disabled =
      state.busy || armed || !payload.unattended_live_supported || !state.csrfToken;
    offButton.disabled = state.busy || !armed || !state.csrfToken;
    document.querySelector("#unattended-control").dataset.state = effective;
  }

  async function load() {
    try {
      const response = await fetch(endpoint, {
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
      render(payload);
    } catch (error) {
      label.textContent = "HALTED";
      reason.textContent = String(
        error.message || "UNATTENDED_CONTROL_STATUS_UNAVAILABLE"
      );
      onButton.disabled = true;
      offButton.disabled = !(
        state.csrfToken &&
        state.generationDigest &&
        state.reviewedFilesDigest
      );
    }
  }

  async function change(target) {
    if (
      state.busy ||
      !state.csrfToken ||
      !state.generationDigest ||
      !state.reviewedFilesDigest
    ) return;
    if (
      target === "on" &&
      !window.confirm(
        "USD_JPY・1,000通貨・最大30 attempts/日の自動売買をONにします。"
      )
    ) {
      return;
    }
    state.busy = true;
    onButton.disabled = true;
    offButton.disabled = true;
    try {
      const response = await fetch(`${endpoint}/${target}`, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-H11-V4-Control-CSRF": state.csrfToken,
        },
        body: JSON.stringify({
          expected_revision: state.revision,
          expected_generation_digest: state.generationDigest,
          expected_reviewed_files_digest: state.reviewedFilesDigest,
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
      render(payload);
    } catch (error) {
      label.textContent = "HALTED";
      reason.textContent = String(error.message || "UNATTENDED_CONTROL_CHANGE_FAILED");
    } finally {
      state.busy = false;
      await load();
    }
  }

  onButton.addEventListener("click", () => change("on"));
  offButton.addEventListener("click", () => change("off"));
  load();
  window.setInterval(load, 5000);
})();
