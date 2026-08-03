const timeline = document.querySelector("#timeline");
const runButton = document.querySelector("#run-proof");

const labels = {
  server_error: ["503", "Server error", "Transient failure classified for retry"],
  success: ["2xx", "Delivered", "Destination returned a successful receipt"],
  client_error: ["422", "Client error", "Permanent rejection moved to dead letter"],
};

function setText(id, value) {
  document.querySelector(`#${id}`).textContent = String(value);
}

function receiptClass(item) {
  if (item.classification === "success") return "success";
  return item.retryable ? "retry" : "terminal";
}

function showReceipt(item, button) {
  document.querySelectorAll(".attempt").forEach((node) => node.classList.remove("selected"));
  button.classList.add("selected");
  const [status, title] = labels[item.classification] ?? [item.http_status ?? "—", item.classification];
  setText("receipt-state", item.retryable ? "RETRYABLE" : item.classification === "success" ? "DELIVERED" : "TERMINAL");
  setText("receipt-index", String(item.sequence).padStart(2, "0"));
  setText("receipt-title", title);
  setText("receipt-http", item.http_status ?? status);
  setText("receipt-cycle", `${item.cycle} / ${item.attempt}`);
  setText("receipt-correlation", item.correlation_id);
  document.querySelector("#receipt-json").textContent = JSON.stringify({request: item.request, response: item.response, error: item.error}, null, 2);
}

function render(data) {
  setText("gate-label", data.gate === "PASS" ? "proof complete" : "proof failed");
  setText("gate-score", data.gate);
  setText("attempt-total", data.summary.transport_attempts);
  setText("duplicate-calls", data.summary.duplicate_transport_calls);
  setText("secret-state", data.secret_value_persisted ? "YES" : "NO");
  setText("dedupe-proof", data.summary.duplicate_transport_calls);
  setText("replay-proof", data.summary.replayed_cycles);
  setText("redaction-proof", data.secret_value_persisted ? "YES" : "NO");

  timeline.replaceChildren();
  data.timeline.forEach((item, index) => {
    const [status, title, detail] = labels[item.classification] ?? [item.http_status ?? "—", item.classification, "Normalized outcome"];
    const button = document.createElement("button");
    button.className = `attempt ${receiptClass(item)}`;
    button.type = "button";
    button.innerHTML = `<span class="attempt-no">${String(index + 1).padStart(2, "0")}</span><b>${status}</b><strong>${title}</strong><small>${detail}</small><em>cycle ${item.cycle} · attempt ${item.attempt}</em>`;
    button.addEventListener("click", () => showReceipt(item, button));
    timeline.append(button);
  });
  const duplicate = document.createElement("div");
  duplicate.className = "attempt duplicate";
  duplicate.innerHTML = `<span class="attempt-no">D</span><b>0</b><strong>Duplicate suppressed</strong><small>Existing terminal action reused; no transport call</small><em>stable idempotency key</em>`;
  timeline.insertBefore(duplicate, timeline.children[2]);
  showReceipt(data.timeline[2], timeline.querySelectorAll("button")[2]);
}

async function load(method = "GET") {
  runButton.disabled = true;
  runButton.firstChild.textContent = "Running proof… ";
  try {
    const staticMode = window.location.hostname.endsWith("github.io")
      || new URLSearchParams(window.location.search).has("static");
    const endpoint = staticMode ? "./delivery-run.json" : "/api/demo";
    const response = await fetch(endpoint, {method: endpoint.startsWith(".") ? "GET" : method});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    render(await response.json());
  } catch (error) {
    setText("gate-label", "proof unavailable");
    setText("gate-score", "FAIL");
    document.querySelector("#receipt-json").textContent = String(error);
  } finally {
    runButton.disabled = false;
    runButton.firstChild.textContent = "Run reliability proof ";
  }
}

runButton.addEventListener("click", () => load("POST"));
load();
