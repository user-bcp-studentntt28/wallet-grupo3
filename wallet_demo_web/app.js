const tabs = Array.from(document.querySelectorAll('[role="tab"]'));

async function requestJson(path, options = {}) {
  const response = await fetch(path, options);
  const responseText = await response.text();
  let payload;

  try {
    payload = JSON.parse(responseText);
  } catch {
    throw new Error(`El servidor devolvió una respuesta no JSON (HTTP ${response.status}).`);
  }

  if (!response.ok) {
    const detail = payload.message || payload.error || "Error del proveedor";
    throw new Error(`HTTP ${response.status}: ${detail}`);
  }
  return payload;
}

for (const tab of tabs) {
  tab.addEventListener("click", () => {
    for (const item of tabs) {
      const selected = item === tab;
      item.classList.toggle("is-active", selected);
      item.setAttribute("aria-selected", String(selected));
      item.tabIndex = selected ? 0 : -1;
      document.getElementById(item.dataset.panel).hidden = !selected;
    }
  });
}

const checkButton = document.getElementById("check-mock");
const mockStatus = document.getElementById("mock-status");

checkButton.addEventListener("click", async () => {
  checkButton.disabled = true;
  mockStatus.className = "connection-status";
  mockStatus.textContent = "Consultando el mock del grupo 3…";

  try {
    const payload = await requestJson("/api/scenarios", {
      headers: { Accept: "application/json" },
    });

    const scenarioGroups = Object.values(payload).filter(Array.isArray);
    const scenarioCount = scenarioGroups.reduce(
      (total, group) => total + group.length,
      0,
    );
    const summary =
      scenarioGroups.length === 0
        ? "Mock grupo 3 conectado; respuesta recibida."
        : `Mock grupo 3 conectado; ${scenarioCount} escenarios en ${scenarioGroups.length} categorías.`;
    mockStatus.className = "connection-status is-success";
    mockStatus.textContent = summary;
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    mockStatus.className = "connection-status is-error";
    mockStatus.textContent = `No se pudo verificar la conexión: ${detail}`;
  } finally {
    checkButton.disabled = false;
  }
});

const kycForm = document.getElementById("kyc-form");
const kycDocument = document.getElementById("kyc-document");
const kycScenario = document.getElementById("kyc-scenario");
const kycMessage = document.getElementById("kyc-message");
const kycResult = document.getElementById("kyc-result");

kycForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const documentValue = kycDocument.value.trim();

  if (!documentValue.startsWith("TEST-") || documentValue.length > 200) {
    kycMessage.className = "form-message is-error";
    kycMessage.textContent = "Ingresa un identificador ficticio que empiece con TEST-.";
    kycDocument.focus();
    return;
  }

  const submitButton = kycForm.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  kycMessage.className = "form-message";
  kycMessage.textContent = "Consultando la verificación simulada…";
  kycResult.textContent = "Esperando respuesta del mock grupo 3.";

  try {
    const result = await requestJson("/api/kyc", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        documentType: "TEST",
        document: documentValue,
        scenario: kycScenario.value,
      }),
    });
    const statusLabels = {
      ACTIVE: "Wallet activa según el mock",
      PENDING: "Revisión pendiente; requiere decisión humana",
      REJECTED: "KYC rechazado según el mock",
    };
    const details = [
      `Escenario devuelto: ${result.scenario}`,
      `Estado devuelto: ${result.status} · ${statusLabels[result.status] || "estado del mock"}`,
      result.id ? `ID KYC: ${result.id}` : null,
      result.wallet_id ? `ID wallet: ${result.wallet_id}` : null,
    ].filter(Boolean);
    kycResult.textContent = details.join("\n");
    onKycResult(result);
    kycMessage.className = "form-message is-success";
    kycMessage.textContent = "Respuesta recibida del mock. No se guardó el documento en la evidencia.";
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    kycResult.textContent = "No se creó una cuenta local. Consulta el error del proveedor antes de continuar.";
    kycMessage.className = "form-message is-error";
    kycMessage.textContent = `No se completó el KYC: ${detail}`;
  } finally {
    submitButton.disabled = false;
  }
});

const policyLabels = {
  ALLOW: ["Permitida", "policy-allow"],
  CONFIRM: ["Requiere confirmación", "policy-confirm"],
  DENY: ["Prohibida", "policy-deny"],
};

async function loadGuardrailMap() {
  const summary = document.getElementById("guardrail-summary");
  const rows = document.getElementById("guardrail-rows");

  try {
    const { features } = await requestJson("/api/guardrails", {
      headers: { Accept: "application/json" },
    });
    const counts = { ALLOW: 0, CONFIRM: 0, DENY: 0 };

    for (const feature of features) {
      counts[feature.policy] += 1;
      const [label, cssClass] = policyLabels[feature.policy];
      const row = rows.insertRow();

      const badge = document.createElement("span");
      badge.className = `policy-badge ${cssClass}`;
      badge.textContent = label;
      row.insertCell().append(badge);

      row.insertCell().textContent = `${feature.method} ${feature.path}`;
      row.insertCell().textContent = feature.note
        ? `${feature.functionality} · ${feature.note}`
        : feature.functionality;
      row.insertCell().textContent = feature.criteria;
      row.insertCell().textContent = feature.task;
    }

    summary.textContent =
      `${features.length} operaciones clasificadas: ${counts.ALLOW} permitidas, ` +
      `${counts.CONFIRM} con confirmación humana, ${counts.DENY} prohibidas. ` +
      "Cualquier operación no listada se deniega por defecto.";
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    summary.textContent = `No se pudo cargar el mapa: ${detail}`;
  }
}

loadGuardrailMap();

/* ---------- Utilidades compartidas ---------- */
const state = { kyc: null, qr: null, payment: null, key: null, request: null, eventId: null };
const $ = (id) => document.getElementById(id);

const STORAGE_KEY = "walletDemoState";
const RUNS_KEY = "walletDemoReconciliations";
const sessionId = (() => {
  let id = sessionStorage.getItem("walletDemoSession");
  if (!id) {
    id = crypto.randomUUID().replaceAll("-", "");
    sessionStorage.setItem("walletDemoSession", id);
  }
  return id;
})();

function saveState() {
  const { payment, key, request, qr } = state;
  localStorage.setItem(STORAGE_KEY, JSON.stringify({ payment, key, request, qr }));
}

function trace(step, walletId) {
  const body = walletId ? { step, walletId } : { step };
  fetch("/api/trace", {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Demo-Session": sessionId },
    body: JSON.stringify(body),
  }).catch(() => {});
}

const STATUS_LABELS = {
  PENDING: "Pendiente",
  SUCCEEDED: "Exitoso",
  REJECTED: "Rechazado",
  REVERSED: "Revertido (estado reportado por el mock)",
  ACTIVE: "Activa",
  OPEN: "Abierto",
  RESOLVED: "Resuelto",
  MATCHED: "Sin diferencias",
  DIFFERENCES: "Con diferencias",
};
const statusText = (status) => `${status} · ${STATUS_LABELS[status] || "estado del mock"}`;
const money = (cents) => `S/ ${(cents / 100).toFixed(2)}`;
const localNow = () => new Date().toLocaleString("es-PE");

function parseSoles(text) {
  const clean = String(text).trim().replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(clean)) return null;
  const cents = Math.round(parseFloat(clean) * 100);
  return cents >= 1 && cents <= 100000000 ? cents : null;
}

async function callApi(path, method = "GET", body) {
  const options = { method, headers: { Accept: "application/json", "X-Demo-Session": sessionId } };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  try {
    const response = await fetch(path, options);
    const text = await response.text();
    let data = null;
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
    return { ok: response.ok, status: response.status, data };
  } catch {
    return { ok: false, status: 0, data: { error: "NETWORK_ERROR", message: "Sin conexión con el backend local." } };
  }
}

function describeError(res) {
  const data = res.data || {};
  const parts = [`HTTP ${res.status || "—"}`, data.error || "ERROR"];
  if (data.ruleCode) parts.push(`[${data.ruleCode}]`);
  const head = parts.join(" ");
  return data.message ? `${head}: ${data.message}` : head;
}

function show(element, lines, hidden = false) {
  element.hidden = hidden;
  element.textContent = lines.filter(Boolean).join("\n");
}

function renderTable(container, rows, { hide = [], moneyColumns = [], statusColumns = [] } = {}) {
  container.replaceChildren();
  container.hidden = false;
  if (!Array.isArray(rows) || rows.length === 0) {
    const empty = document.createElement("p");
    empty.className = "form-help";
    empty.textContent = "Sin registros devueltos por el mock.";
    container.append(empty);
    return;
  }
  const columns = [...new Set(rows.flatMap((row) => Object.keys(row)))].filter((c) => !hide.includes(c));
  const table = document.createElement("table");
  table.className = "guardrail-table";
  const headRow = table.createTHead().insertRow();
  for (const column of columns) {
    const th = document.createElement("th");
    th.scope = "col";
    th.textContent = column;
    headRow.append(th);
  }
  const body = table.createTBody();
  for (const row of rows) {
    const tr = body.insertRow();
    for (const column of columns) {
      const value = row[column];
      let text = value === null || value === undefined ? "" : String(value);
      if (moneyColumns.includes(column) && Number.isFinite(value)) text = money(value);
      if (statusColumns.includes(column) && value) text = statusText(value);
      tr.insertCell().textContent = text;
    }
  }
  container.append(table);
}

function describeObject(data, moneyKeys = []) {
  return Object.entries(data || {})
    .filter(([, value]) => value === null || ["string", "number", "boolean"].includes(typeof value))
    .map(([key, value]) => `${key}: ${moneyKeys.includes(key) && Number.isFinite(value) ? money(value) : value}`);
}

/* ---------- W1: wallet y decisión humana ---------- */
function setStep(current, nextText) {
  for (const item of document.querySelectorAll("#onboarding-steps li")) {
    const step = Number(item.dataset.step);
    item.classList.toggle("is-done", step < current);
    if (step === current) item.setAttribute("aria-current", "step");
    else item.removeAttribute("aria-current");
  }
  $("onboarding-next").textContent = nextText;
}

function onKycResult(result) {
  state.kyc = result;
  syncAccess(result);
  $("kyc-actions").hidden = false;
  $("kyc-decision-box").hidden = result.status !== "PENDING";
  $("wallet-result").hidden = true;
  trace("ONBOARDING_STEP_COMPLETED", result.wallet_id);
  if (result.status === "PENDING") {
    setStep(2, "Siguiente acción: un facilitador debe decidir la revisión manual (ACTIVE o REJECTED).");
  } else if (result.status === "ACTIVE") {
    setStep(3, "Siguiente acción: consulta la wallet en el mock para confirmar su estado.");
  } else {
    setStep(2, "El mock no activó la cuenta. Revisa el resultado o inicia otro KYC de prueba.");
  }
}

async function showWalletInto(walletId, element, note = "") {
  const res = await callApi(`/api/wallets/${encodeURIComponent(walletId)}`);
  if (!res.ok) {
    show(element, [`No se pudo consultar la wallet: ${describeError(res)}`]);
    return null;
  }
  const w = res.data;
  show(element, [
    `Wallet: ${w.id}`,
    `Estado: ${statusText(w.status)}`,
    `Saldo contable: ${money(w.balance)} · Reservado: ${money(w.reserved)} · Disponible: ${money(w.available)}`,
    w.balance === 0 ? "Wallet sin fondos: el alta no la financia." : note,
    `Consultado ${localNow()} (hora local de captura de la demo)`,
  ]);
  return w;
}

$("btn-kyc-wallet").addEventListener("click", async () => {
  if (!state.kyc || !state.kyc.wallet_id) return;
  const wallet = await showWalletInto(state.kyc.wallet_id, $("wallet-result"));
  if (wallet && wallet.status === "ACTIVE") {
    setStep(3, "Onboarding completo: la wallet está ACTIVE en el mock. Para pagar con fondos usa wallet-demo en «Pagos y QR».");
    document.querySelector('#onboarding-steps li[data-step="3"]').classList.add("is-done");
    trace("ONBOARDING_COMPLETED", wallet.id);
  }
});

async function decideKyc(decision) {
  const message = $("kyc-message");
  if (!state.kyc) return;
  if (!$("kyc-decision-confirm").checked) {
    message.className = "form-message is-error";
    message.textContent = "Confirma que eres el facilitador antes de decidir. No se envió ninguna solicitud.";
    return;
  }
  const res = await callApi(`/api/kyc/${encodeURIComponent(state.kyc.id)}/decision`, "POST", {
    decision,
    confirmed: true,
  });
  if (!res.ok) {
    message.className = "form-message is-error";
    message.textContent = `No se registró la decisión: ${describeError(res)}`;
    return;
  }
  state.kyc = { ...state.kyc, ...res.data };
  kycResult.textContent = [
    `Decisión humana registrada: ${decision}`,
    `Estado devuelto: ${statusText(res.data.status)}`,
    `ID KYC: ${state.kyc.id}`,
    `ID wallet: ${state.kyc.wallet_id}`,
  ].join("\n");
  onKycResult(state.kyc);
  message.className = "form-message is-success";
  message.textContent = "Decisión enviada al mock; el estado mostrado es el que devolvió.";
  await showWalletInto(state.kyc.wallet_id, $("wallet-result"));
}

$("btn-kyc-active").addEventListener("click", () => decideKyc("ACTIVE"));
$("btn-kyc-rejected").addEventListener("click", () => decideKyc("REJECTED"));

/* ---------- W2/W3: wallet, QR ---------- */
function renderQr(text) {
  const image = $("qr-image");
  try {
    const qr = qrcode(0, "M");
    qr.addData(text);
    qr.make();
    image.src = qr.createDataURL(4, 8);
    image.hidden = false;
  } catch {
    image.hidden = true;
  }
}
$("btn-wallet").addEventListener("click", async () => {
  const id = $("wallet-id").value.trim();
  await showWalletInto(id, $("pay-wallet-result"), "Datos compartidos del grupo 3.");
});

$("btn-qr-create").addEventListener("click", async () => {
  const amountText = $("qr-amount").value.trim();
  const body = { expiresInSeconds: Number($("qr-ttl").value) };
  if (amountText) {
    const cents = parseSoles(amountText);
    if (cents === null) {
      show($("qr-result"), ["Monto inválido. Usa un valor como 15.00 o déjalo vacío para monto abierto."]);
      return;
    }
    body.amountCents = cents;
  }
  const res = await callApi("/api/qrs", "POST", body);
  if (!res.ok) {
    show($("qr-result"), [`No se creó el QR: ${describeError(res)}`]);
    return;
  }
  $("qr-payload").value = res.data.payload;
  renderQr(res.data.payload);
  state.qr = null;
  show($("qr-result"), [
    "QR del mock creado (no es un documento de deuda).",
    `ID: ${res.data.id}`,
    `Monto: ${res.data.amountCents === null ? "abierto" : money(res.data.amountCents)}`,
    "Pulsa «Resolver QR» para revisar comercio y monto antes de pagar.",
  ]);
});

$("btn-qr-resolve").addEventListener("click", async () => {
  const payload = $("qr-payload").value.trim();
  const res = await callApi("/api/qrs/resolve", "POST", { payload });
  if (!res.ok) {
    state.qr = null;
    const expired = res.data && res.data.error === "QR_EXPIRED";
    show($("qr-result"), [
      `No se pudo resolver el QR: ${describeError(res)}`,
      expired ? "El QR venció. Es un error del QR, no un estado de pago: genera uno nuevo." : "",
    ]);
    updateConfirmText();
    return;
  }
  const data = res.data;
  const fixed = data.amountCents !== null && data.amountCents !== undefined;
  state.qr = {
    id: data.id || data.qrId || payload.replace(/^qrmock:/, ""),
    amountCents: fixed ? data.amountCents : null,
  };
  saveState();
  renderQr(payload);
  if (fixed) $("pay-amount").value = (data.amountCents / 100).toFixed(2);
  $("pay-amount").disabled = fixed;
  show($("qr-result"), [
    "QR resuelto por el mock:",
    ...describeObject(data, ["amountCents"]),
    fixed ? "Monto fijo: no se puede cambiar." : "Monto abierto: ingresa el monto a pagar.",
  ]);
  updateConfirmText();
});

/* ---------- W2/W3/W4/W5: pago ---------- */
function updateConfirmText() {
  const cents = state.qr && state.qr.amountCents !== null ? state.qr.amountCents : parseSoles($("pay-amount").value);
  const amount = cents ? money(cents) : "el monto indicado";
  $("pay-confirm-text").textContent = `Confirmo pagar ${amount} a ${$("pay-recipient").value} (pago de prueba)`;
}
$("pay-amount").addEventListener("input", updateConfirmText);
$("pay-recipient").addEventListener("change", updateConfirmText);

function setPaymentActions(enabled) {
  for (const id of ["btn-status", "btn-resolve", "btn-receipt", "btn-conflict", "btn-complete", "btn-complete-rej", "btn-deliver", "btn-deliver-dup"]) {
    $(id).disabled = !enabled;
  }
}

function paymentRequestFromForm() {
  const fixed = state.qr && state.qr.amountCents !== null;
  const cents = fixed ? state.qr.amountCents : parseSoles($("pay-amount").value);
  if (cents === null) return null;
  const request = {
    walletId: $("wallet-id").value.trim(),
    recipient: $("pay-recipient").value,
    amountCents: cents,
  };
  if (state.qr && state.qr.id) request.qrId = state.qr.id;
  if ($("pay-scenario").value) request.scenario = $("pay-scenario").value;
  return request;
}

function guidanceFor(res) {
  const error = res.data && res.data.error;
  if (res.status === 0) {
    return "Sin respuesta de red: el resultado es incierto y el intento se conserva. Reintenta con la misma clave (no se crea otro cobro) o consulta el estado.";
  }
  if (res.status === 503) {
    return "El mock confirma que no hubo operación ni reserva. Puedes iniciar un nuevo intento con una clave nueva.";
  }
  if (res.status === 504) {
    return "El resultado es incierto: el pago pudo crearse. No pagues de nuevo; usa «Consultar estado» o «Resolver con proveedor».";
  }
  if (res.status === 410) return "El QR venció (error del QR, no estado de pago). Genera un QR nuevo.";
  if (res.status === 409 && error === "IDEMPOTENCY_CONFLICT") {
    return "Misma clave con datos distintos: el mock lo rechazó y no se generó otra clave automáticamente.";
  }
  return "";
}

async function sendPayment(request, key, label) {
  const res = await callApi("/api/payments", "POST", { ...request, idempotencyKey: key, confirmed: true });
  const data = res.data || {};
  const paymentId = data.id || data.paymentId;
  if (paymentId) {
    state.payment = { id: paymentId, walletId: request.walletId };
    setPaymentActions(true);
  }
  $("btn-retry").disabled = false;
  $("btn-new-attempt").disabled = false;
  saveState();
  if (!res.ok && !paymentId) {
    show($("pay-result"), [`${label}: ${describeError(res)}`]);
  } else {
    show($("pay-result"), [
      label,
      `HTTP ${res.status}${res.status === 200 ? " · el mock devolvió el pago existente (misma clave y contenido)" : ""}`,
      data.error ? `Error devuelto: ${data.error}` : `Estado devuelto: ${statusText(data.status)}`,
      data.error && data.status ? `Estado informado por el mock junto al error: ${statusText(data.status)}` : null,
      paymentId ? `ID del pago: ${paymentId}` : null,
      `Capturado ${localNow()} (hora local de la demo)`,
    ]);
  }
  $("pay-guidance").textContent = guidanceFor(res);
  if (paymentId && res.status === 202 && !request.scenario) {
    // Escenario normal: el proveedor ya terminó; resolver aplica su resultado sin crear otro cobro.
    await callApi(`/api/payments/${encodeURIComponent(paymentId)}/resolve`, "POST", { confirmed: true });
  }
  if (paymentId && (res.ok || res.status === 504)) await refreshPayment();
  return res;
}

$("btn-pay").addEventListener("click", async () => {
  if (!$("pay-confirm").checked) {
    show($("pay-result"), ["Confirma el pago antes de continuar. No se envió ninguna solicitud."]);
    return;
  }
  const request = paymentRequestFromForm();
  if (!request) {
    show($("pay-result"), ["Ingresa un monto válido (por ejemplo 15.00, máximo dos decimales). No se envió ninguna solicitud."]);
    return;
  }
  trace("CHECKOUT_STARTED", request.walletId);
  const wallet = await callApi(`/api/wallets/${encodeURIComponent(request.walletId)}`);
  if (!wallet.ok) {
    show($("pay-result"), [`No se pudo consultar la wallet; no se envió el pago: ${describeError(wallet)}`]);
    return;
  }
  if (wallet.data.status !== "ACTIVE") {
    show($("pay-result"), [`La wallet está ${statusText(wallet.data.status)}: no se puede pagar. No se envió ninguna solicitud.`]);
    return;
  }
  if (request.amountCents > wallet.data.available) {
    show($("pay-result"), [
      `El monto (${money(request.amountCents)}) supera el disponible consultado (${money(wallet.data.available)}). No se envió ninguna solicitud.`,
    ]);
    return;
  }
  state.request = request;
  state.key = crypto.randomUUID();
  saveState();
  trace("CHECKOUT_CONFIRMED", request.walletId);
  await sendPayment(request, state.key, "Pago solicitado");
});

$("btn-retry").addEventListener("click", async () => {
  if (!state.request || !state.key) return;
  await sendPayment(state.request, state.key, "Reintento con la misma clave y contenido");
});

$("btn-new-attempt").addEventListener("click", async () => {
  if (!state.request) return;
  state.key = crypto.randomUUID();
  saveState();
  await sendPayment(state.request, state.key, "Nuevo intento con una clave nueva");
});

$("btn-conflict").addEventListener("click", async () => {
  if (!state.request || !state.key) return;
  if (!$("fac-confirm").checked) {
    show($("pay-detail"), ["Confirma el control de facilitador. No se envió ninguna solicitud."]);
    return;
  }
  const changed = { ...state.request, amountCents: state.request.amountCents + 100 };
  const res = await callApi("/api/payments", "POST", { ...changed, idempotencyKey: state.key, confirmed: true });
  show($("pay-detail"), [
    "Prueba de conflicto: misma clave, monto distinto (+S/ 1.00).",
    `Respuesta del mock: ${res.ok ? "aceptada" : describeError(res)}`,
    guidanceFor(res),
  ]);
});

async function refreshPayment(preface = []) {
  if (!state.payment) return;
  const res = await callApi(`/api/payments/${encodeURIComponent(state.payment.id)}`);
  if (!res.ok) {
    show($("pay-detail"), [...preface, `Resultado no verificado: ${describeError(res)}`, "No se muestra éxito ni saldo local."]);
    return;
  }
  const p = res.data;
  const lines = [
    ...preface,
    "Estado confirmado consultando el mock:",
    `ID: ${p.id} · Destinatario: ${p.recipient} · Monto: ${money(p.amount)}`,
    `Estado: ${statusText(p.status)}`,
  ];
  if (p.status === "PENDING") lines.push("Sigue pendiente: no es un pago exitoso todavía.");
  if (p.status === "REVERSED") lines.push("Estado ya reportado por el mock; la demo no inicia reversos.");
  show($("pay-detail"), lines);
  setBanner(p);
  await showWalletInto(state.payment.walletId, $("pay-wallet-result"), "Datos compartidos del grupo 3.");
}

function setBanner(p) {
  const banner = $("pay-banner");
  const views = {
    SUCCEEDED: ["is-success", `Pago exitoso: ${money(p.amount)} a ${p.recipient}`],
    PENDING: ["is-pending", `Pago pendiente: ${money(p.amount)} a ${p.recipient} (aún no es exitoso)`],
    REJECTED: ["is-failed", `Pago rechazado: ${money(p.amount)} a ${p.recipient}. No se cobró.`],
    REVERSED: ["is-failed", `El mock reporta este pago como revertido: ${money(p.amount)} a ${p.recipient}`],
  };
  const [cssClass, text] = views[p.status] || ["is-pending", `Estado del mock: ${p.status}`];
  banner.className = `pay-banner ${cssClass}`;
  banner.textContent = text;
  banner.hidden = false;
}

$("btn-status").addEventListener("click", refreshPayment);

$("btn-resolve").addEventListener("click", async () => {
  if (!state.payment) return;
  const res = await callApi(`/api/payments/${encodeURIComponent(state.payment.id)}/resolve`, "POST", { confirmed: true });
  if (!res.ok && res.status !== 202) {
    show($("pay-detail"), [`No se pudo resolver: ${describeError(res)}`]);
    return;
  }
  const escalated = res.data && res.data.escalated;
  show($("pay-detail"), [
    escalated
      ? "El proveedor sigue PENDING: el mock abrió un caso de soporte (sin crear otro cobro)."
      : "El mock consultó al proveedor sin crear otro cobro.",
    ...describeObject(res.data, ["amount"]),
  ]);
  if (!escalated) await refreshPayment();
});

$("btn-receipt").addEventListener("click", async () => {
  if (!state.payment) return;
  const res = await callApi(`/api/payments/${encodeURIComponent(state.payment.id)}/receipt`);
  if (!res.ok) {
    show($("pay-detail"), [`Sin comprobante: ${describeError(res)}`, "Solo hay comprobante para pagos SUCCEEDED."]);
    return;
  }
  show($("pay-detail"), ["Comprobante devuelto por el mock:", ...describeObject(res.data, ["amountCents"])]);
});

$("btn-history").addEventListener("click", async () => {
  const wallet = $("wallet-id").value.trim();
  const res = await callApi(`/api/payments?walletId=${encodeURIComponent(wallet)}`);
  if (!res.ok) {
    show($("pay-detail"), [`No se pudo obtener el historial: ${describeError(res)}`]);
    return;
  }
  renderTable($("history-box"), res.data, {
    hide: ["fingerprint", "idem", "wallet_id"],
    moneyColumns: ["amount"],
    statusColumns: ["status"],
  });
  show($("pay-detail"), [`Historial de ${wallet}: registros del grupo 3 (datos compartidos). Capturado ${localNow()}.`]);
});

/* ---------- W4/W5: controles de facilitador ---------- */
function requireFacilitator() {
  if ($("fac-confirm").checked && state.payment) return true;
  show($("pay-detail"), ["Confirma el control de facilitador y crea un pago primero. No se envió ninguna solicitud."]);
  return false;
}

async function completeProvider(status) {
  if (!requireFacilitator()) return;
  const res = await callApi(`/api/control/provider/${encodeURIComponent(state.payment.id)}/complete`, "POST", {
    status,
    confirmed: true,
  });
  if (!res.ok) {
    const already = res.data && res.data.error === "PROVIDER_ALREADY_FINAL";
    show($("pay-detail"), [
      `No se pudo completar el proveedor: ${describeError(res)}`,
      already ? "El proveedor ya había finalizado este pago; usa «Entregar evento» para aplicarlo a la wallet." : null,
    ]);
    return;
  }
  state.eventId = res.data.eventId || null;
  show($("pay-detail"), [
    `Proveedor finalizado como ${status}. La wallet aún no cambia hasta entregar el evento.`,
    state.eventId ? `Evento: ${state.eventId}` : null,
  ]);
}

async function deliverEvent(repeat) {
  if (!requireFacilitator()) return;
  if (!state.eventId) {
    const events = await callApi("/api/events");
    const own = events.ok ? events.data.filter((e) => e.payment_id === state.payment.id) : [];
    state.eventId = own.length ? own[own.length - 1].id : null;
  }
  if (!state.eventId) {
    show($("pay-detail"), ["El mock no tiene un evento para este pago todavía."]);
    return;
  }
  const res = await callApi(`/api/control/events/${encodeURIComponent(state.eventId)}/deliver`, "POST", { confirmed: true });
  if (!res.ok) {
    show($("pay-detail"), [`No se pudo entregar el evento: ${describeError(res)}`]);
    return;
  }
  const duplicate = res.data && res.data.duplicate === true;
  await refreshPayment([
    duplicate
      ? "Entrega duplicada detectada por el mock: no se aplica otro movimiento ni otro pago."
      : "Evento entregado por primera vez.",
    repeat && !duplicate ? "Pulsa «Repetir entrega» de nuevo para ver la respuesta duplicada." : null,
  ]);
}

$("btn-complete").addEventListener("click", () => completeProvider("SUCCEEDED"));
$("btn-complete-rej").addEventListener("click", () => completeProvider("REJECTED"));
$("btn-deliver").addEventListener("click", () => deliverEvent(false));
$("btn-deliver-dup").addEventListener("click", () => deliverEvent(true));

/* ---------- W5/W6: operaciones ---------- */
$("btn-support").addEventListener("click", async () => {
  const res = await callApi("/api/support/cases");
  if (!res.ok) {
    show($("support-result"), [`No se pudieron leer los casos: ${describeError(res)}`]);
    return;
  }
  show($("support-result"), [`${res.data.length} caso(s) devueltos por el mock (solo lectura). Capturado ${localNow()}.`]);
  renderTable($("ops-table"), res.data, { statusColumns: ["status"] });
});

$("btn-reversal").addEventListener("click", async () => {
  const id = $("reversal-id").value.trim();
  const res = await callApi(`/api/reversals/${encodeURIComponent(id)}`);
  show($("support-result"), res.ok
    ? ["Reverso ya existente, mostrado solo como estado del mock:", ...describeObject(res.data, ["amount"])]
    : [`Sin reverso: ${describeError(res)}`]);
});

async function listInto(path, options) {
  const res = await callApi(path);
  if (!res.ok) {
    show($("recon-summary"), [`No se pudo consultar: ${describeError(res)}`]);
    return null;
  }
  renderTable($("ops-table"), res.data, options);
  return res.data;
}

$("btn-settlements").addEventListener("click", async () => {
  const rows = await listInto("/api/settlements", { moneyColumns: ["amount"], statusColumns: ["status"] });
  if (rows) show($("recon-summary"), [`Liquidaciones del grupo 3: ${rows.length} pago(s). Reporte completo, sin corte diario.`]);
});
$("btn-ledger").addEventListener("click", async () => {
  const rows = await listInto("/api/ledger", { moneyColumns: ["amount"] });
  if (rows) show($("recon-summary"), [`Ledger del mock: ${rows.length} asiento(s) (solo lectura).`]);
});
$("btn-incidents").addEventListener("click", async () => {
  const rows = await listInto("/api/incidents", { statusColumns: ["status"] });
  if (rows) show($("recon-summary"), [`Incidencias devueltas por el mock: ${rows.length}.`]);
});

$("btn-reconcile").addEventListener("click", async () => {
  const res = await callApi("/api/reconciliations", "POST", {});
  if (!res.ok) {
    show($("recon-summary"), [`No se pudo conciliar: ${describeError(res)}`]);
    return;
  }
  const settlements = await callApi("/api/settlements");
  const incidents = await callApi("/api/incidents");
  const paymentCount = settlements.ok ? settlements.data.length : "no disponible";
  const incidentRows = incidents.ok ? incidents.data : [];
  const summaryLines = [];
  if (settlements.ok && incidents.ok) {
    const paymentIds = new Set(settlements.data.map((row) => row.id));
    const open = incidentRows.filter((row) => row.status === "OPEN");
    const withDifferences = new Set(open.filter((row) => paymentIds.has(row.payment_id)).map((row) => row.payment_id));
    const walletRows = open.filter((row) => row.reason === "BALANCE_MISMATCH");
    const orphans = open.filter((row) => row.reason !== "BALANCE_MISMATCH" && !paymentIds.has(row.payment_id));
    summaryLines.push(
      `Pagos con diferencias: ${withDifferences.size} · Pagos sin diferencias: ${paymentIds.size - withDifferences.size}`,
      `Incidencias abiertas: ${open.length} · Resueltas: ${incidentRows.length - open.length}`,
      `Diferencias de wallet: ${walletRows.length} · Recursos huérfanos: ${orphans.length} (separados de los pagos)`,
    );
  }
  show($("recon-summary"), [
    `Resultado: ${statusText(res.data.status)}`,
    `Diferencias devueltas: ${res.data.differences.length}`,
    `Pagos del grupo: ${paymentCount} · Incidencias históricas: ${incidents.ok ? incidentRows.length : "no disponible"} (conteos separados)`,
    ...summaryLines,
    "Alcance: todo el grupo 3, no una conciliación diaria ni bancaria.",
    `Hora local de captura: ${localNow()} (no es fecha del proveedor)`,
  ]);
  if (incidents.ok) renderTable($("ops-table"), incidentRows, { statusColumns: ["status"] });
  logRun({
    status: res.data.status,
    differences: res.data.differences.length,
    payments: settlements.ok ? settlements.data.length : null,
    incidents: incidents.ok ? incidentRows.length : null,
  });
});

$("alt-mode").addEventListener("change", () => {
  $("alt-amount").disabled = $("alt-mode").value === "CLEAR";
});

$("btn-alter").addEventListener("click", async () => {
  const output = $("alter-result");
  if (!$("alt-confirm").checked) {
    show(output, ["Confirma la acción de facilitador. No se envió ninguna solicitud."]);
    return;
  }
  const paymentId = $("alt-payment").value.trim() || (state.payment && state.payment.id) || "";
  const mode = $("alt-mode").value;
  const body = { paymentId, mode, confirmed: true };
  if (mode === "AMOUNT") {
    const cents = parseSoles($("alt-amount").value);
    if (cents === null) {
      show(output, ["Monto inválido para AMOUNT."]);
      return;
    }
    body.amountCents = cents;
  }
  const res = await callApi("/api/control/settlements", "POST", body);
  show(output, res.ok
    ? [`Reporte alterado (${mode}) solo en el mock; wallet y ledger no cambian.`, "Ejecuta la conciliación para ver la incidencia o su resolución."]
    : [`No se aplicó: ${describeError(res)}`]);
});

$("alt-amount").disabled = false;
updateConfirmText();

/* ---------- W6: registro local de conciliaciones ---------- */
const localDate = (date = new Date()) => date.toLocaleDateString("en-CA");

function logRun(summary) {
  const runs = JSON.parse(localStorage.getItem(RUNS_KEY) || "[]");
  runs.push({ date: localDate(), localTime: localNow(), ...summary });
  localStorage.setItem(RUNS_KEY, JSON.stringify(runs.slice(-50)));
  renderRuns();
}

function renderRuns() {
  const filter = $("runs-date").value;
  const runs = JSON.parse(localStorage.getItem(RUNS_KEY) || "[]").filter((run) => !filter || run.date === filter);
  renderTable(
    $("runs-table"),
    runs.map(({ localTime, status, differences, payments, incidents }) => ({
      hora_local_de_captura: localTime,
      resultado_del_mock: status,
      diferencias: differences,
      pagos_del_grupo: payments,
      incidencias: incidents,
    })),
  );
}
$("btn-runs").addEventListener("click", renderRuns);

/* ---------- W3: vista de comercio (sesión) ---------- */
$("btn-merchant").addEventListener("click", async () => {
  const note = $("merchant-note");
  const exported = await callApi("/api/evidence/export");
  if (!exported.ok) {
    note.textContent = `No se pudo leer la evidencia local: ${describeError(exported)}`;
    return;
  }
  const ref = $("mv-ref").value.trim();
  const date = $("mv-date").value;
  const attempts = new Map();
  for (const event of exported.data.events) {
    if (event.eventType !== "PAYMENT_REQUESTED" || !event.paymentId || !event.qrId) continue;
    if (event.sessionId && event.sessionId !== sessionId) continue;
    if (!attempts.has(event.paymentId)) attempts.set(event.paymentId, event);
  }
  const rows = [];
  for (const [paymentId, event] of attempts) {
    const capturedDate = event.capturedAtLocal.slice(0, 10);
    if (ref && !paymentId.includes(ref) && !event.qrId.includes(ref)) continue;
    if (date && capturedDate !== date) continue;
    const res = await callApi(`/api/payments/${encodeURIComponent(paymentId)}`);
    const status = res.ok ? res.data.status : null;
    rows.push({
      referencia_pago: paymentId,
      qr: event.qrId,
      captura_local: event.capturedAtLocal,
      estado_del_mock: status ? statusText(status) : "no verificado",
      entrega: status === "SUCCEEDED" ? "Pago confirmado" : "No entregar el producto todavía",
    });
  }
  renderTable($("merchant-table"), rows);
  note.textContent =
    `${rows.length} intento(s) QR de esta sesión. Referencia y fecha son evidencia local de la demo, no datos del proveedor. Un QR no equivale a una deuda (W3 completo es POSTERIOR).`;
});

/* ---------- Restauración tras recargar ---------- */
async function restoreState() {
  renderRuns();
  const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
  if (!saved) return;
  Object.assign(state, { payment: saved.payment, key: saved.key, request: saved.request, qr: saved.qr });
  if (state.request) {
    $("btn-retry").disabled = false;
    $("btn-new-attempt").disabled = false;
    $("wallet-id").value = state.request.walletId;
  }
  if (state.payment) {
    setPaymentActions(true);
    show($("pay-result"), [
      "Intento restaurado tras recargar (clave y contenido conservados en este navegador).",
      `ID del pago: ${state.payment.id}`,
    ]);
    await refreshPayment();
  }
  if (state.qr && state.qr.amountCents !== null) {
    $("pay-amount").value = (state.qr.amountCents / 100).toFixed(2);
    $("pay-amount").disabled = true;
    updateConfirmText();
  }
  $("btn-history").click();
}

/* ---------- Login / registro de usuarios TEST- (con clave de 6 dígitos) ---------- */
const USER_SESSION_KEY = "walletDemoUserRecord";
let currentUser = null;
let loginMode = "login";

function setMode(mode) {
  loginMode = mode;
  const register = mode === "register";
  $("mode-login").classList.toggle("is-active", !register);
  $("mode-register").classList.toggle("is-active", register);
  $("mode-login").setAttribute("aria-pressed", String(!register));
  $("mode-register").setAttribute("aria-pressed", String(register));
  $("register-extra").hidden = !register;
  $("btn-login").textContent = register ? "Registrarme" : "Ingresar";
  $("login-intro").textContent = register
    ? "Crea tu usuario de prueba TEST- y una clave de 6 dígitos. Si ya estás registrado, usa Ingresar."
    : "Ingresa con tu usuario de prueba TEST- y tu clave de 6 dígitos.";
  $("login-message").textContent = "";
  $("login-password").value = "";
  $("login-password2").value = "";
}
$("mode-login").addEventListener("click", () => setMode("login"));
$("mode-register").addEventListener("click", () => setMode("register"));
$("tab-pagos").addEventListener("click", () => $("btn-wallet").click());

function applyAccess(status) {
  const active = status === "ACTIVE";
  for (const id of ["tab-pagos", "tab-operaciones"]) {
    $(id).disabled = !active;
    $(id).title = active ? "" : "Disponible cuando el mock active tu wallet (KYC ACTIVE).";
  }
  if (!active) $("tab-registro").click();
}

function syncAccess(result) {
  if (!currentUser || result.id !== currentUser.record.kycId) return;
  currentUser.record.status = result.status;
  sessionStorage.setItem(USER_SESSION_KEY, JSON.stringify(currentUser.record));
  $("user-chip").textContent = userLabel(currentUser.record);
  applyAccess(result.status);
}

const userLabel = (record) => `Usuario ${record.alias} · ${record.walletId} · ${record.status}`;

function enterApp(record) {
  currentUser = { record };
  sessionStorage.setItem(USER_SESSION_KEY, JSON.stringify(record));
  $("login-screen").hidden = true;
  $("app-main").hidden = false;
  $("user-chip").hidden = false;
  $("btn-logout").hidden = false;
  $("user-chip").textContent = userLabel(record);
  const kyc = { id: record.kycId, wallet_id: record.walletId, status: record.status };
  kycResult.textContent = [
    `Usuario de prueba: ${record.alias}`,
    `Estado devuelto: ${statusText(record.status)}`,
    `ID KYC: ${record.kycId}`,
    `ID wallet: ${record.walletId}`,
  ].join("\n");
  onKycResult(kyc);
  applyAccess(record.status);
  restoreState();
  if (record.status === "ACTIVE") $("tab-pagos").click();
}

function loginError(text) {
  $("login-message").className = "form-message is-error";
  $("login-message").textContent = text;
}

$("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const doc = $("login-document").value.trim();
  const password = $("login-password").value;
  if (!doc.startsWith("TEST-") || doc.length > 200) {
    loginError("Ingresa un usuario ficticio que empiece con TEST-. No se envió ninguna solicitud.");
    $("login-document").focus();
    return;
  }
  if (!/^\d{6}$/.test(password)) {
    loginError("La clave debe tener exactamente 6 dígitos. No se envió ninguna solicitud.");
    $("login-password").focus();
    return;
  }
  const register = loginMode === "register";
  if (register && password !== $("login-password2").value) {
    loginError("Las dos claves no coinciden. No se envió ninguna solicitud.");
    return;
  }
  const button = $("btn-login");
  button.disabled = true;
  $("login-message").className = "form-message";
  $("login-message").textContent = register ? "Registrando con el mock…" : "Verificando…";
  try {
    const body = { document: doc, password };
    if (register) body.scenario = $("login-scenario").value;
    const res = await callApi(register ? "/api/auth/register" : "/api/auth/login", "POST", body);
    if (!res.ok) {
      const code = res.data && res.data.error;
      if (code === "USER_EXISTS") setMode("login");
      if (code === "USER_NOT_FOUND") {
        loginError("No estás registrado: toca «Registrarme» para crear tu usuario.");
        return;
      }
      loginError(code === "USER_EXISTS" ? "Ya estás registrado: ingresa con tu clave." : describeError(res));
      return;
    }
    if (register && res.data.registered === false) {
      loginError(`El mock no activó el usuario (${statusText(res.data.status)}). No quedó registrado; puedes reintentar.`);
      return;
    }
    $("login-password").value = "";
    $("login-password2").value = "";
    enterApp({ alias: res.data.alias, kycId: res.data.kycId, walletId: res.data.walletId, status: res.data.status });
  } finally {
    button.disabled = false;
  }
});

$("btn-logout").addEventListener("click", () => {
  sessionStorage.removeItem(USER_SESSION_KEY);
  location.reload();
});

function initLogin() {
  let record = null;
  try {
    record = JSON.parse(sessionStorage.getItem(USER_SESSION_KEY) || "null");
  } catch {
    record = null;
  }
  if (record && record.kycId) {
    enterApp(record);
    return;
  }
  trace("ONBOARDING_STARTED");
  $("login-document").focus();
}

initLogin();
