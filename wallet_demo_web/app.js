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
