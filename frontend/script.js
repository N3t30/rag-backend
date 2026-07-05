// Conexão simples com o backend local em FastAPI.
const BACKEND_URL = "http://localhost:8000";

const backendStatus = document.getElementById("backendStatus");
const ingestButton = document.getElementById("ingestButton");
const queryButton = document.getElementById("queryButton");
const pdfInput = document.getElementById("pdfInput");
const questionInput = document.getElementById("questionInput");
const ingestStatus = document.getElementById("ingestStatus");
const ingestResult = document.getElementById("ingestResult");
const queryStatus = document.getElementById("queryStatus");
const answerBox = document.getElementById("answerBox");
const sourcesBox = document.getElementById("sourcesBox");
const sourcesList = document.getElementById("sourcesList");
const queryHint = document.getElementById("queryHint");

function setBackendStatus(message, isOnline) {
  backendStatus.textContent = message;
  backendStatus.style.background = isOnline ? "#e6f7ea" : "#fdeaea";
}

function setBusy(button, isBusy) {
  button.disabled = isBusy;
}

function showError(element, message) {
  element.hidden = false;
  element.textContent = message;
}

function clearResult(element) {
  element.hidden = true;
  element.textContent = "";
}

async function checkHealth() {
  setBackendStatus("Verificando backend...", false);

  try {
    const response = await fetch(`${BACKEND_URL}/health`, {
      method: "GET",
    });

    if (!response.ok) {
      throw new Error("Backend indisponível");
    }

    const data = await response.json();
    const modelsText = data.models && data.models.length
      ? `Modelos: ${data.models.join(", ")}`
      : "Sem modelos listados";
    setBackendStatus(`Backend online • ${modelsText}`, true);
  } catch (error) {
    setBackendStatus("Backend offline • verifique se o servidor está rodando", false);
  }
}

async function uploadPdf() {
  const file = pdfInput.files[0];

  if (!file) {
    showError(ingestStatus, "Selecione um arquivo PDF antes de indexar.");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  setBusy(ingestButton, true);
  setBusy(queryButton, true);
  ingestStatus.textContent = "Processando... isso pode levar alguns minutos.";
  clearResult(ingestResult);

  try {
    const response = await fetch(`${BACKEND_URL}/ingest`, {
      method: "POST",
      body: formData,
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const detail = data.detail || data.error || "Erro ao indexar o PDF.";
      throw new Error(detail);
    }

    ingestResult.hidden = false;
    ingestResult.innerHTML = `
      <strong>PDF indexado com sucesso!</strong><br />
      Textos indexados: ${data.textos_indexados ?? data.texts_indexed ?? 0}<br />
      Tabelas indexadas: ${data.tabelas_indexadas ?? data.tables_indexed ?? 0}
    `;
    queryHint.textContent = "Conteúdo pronto para consulta.";
    ingestStatus.textContent = "Upload concluído.";
  } catch (error) {
    showError(ingestStatus, error.message || "Não foi possível conectar ao backend.");
  } finally {
    setBusy(ingestButton, false);
    setBusy(queryButton, false);
  }
}

async function askQuestion() {
  const question = questionInput.value.trim();

  if (!question) {
    showError(queryStatus, "Digite uma pergunta antes de continuar.");
    return;
  }

  setBusy(ingestButton, true);
  setBusy(queryButton, true);
  queryStatus.textContent = "Pensando... modelo local pode demorar.";
  clearResult(answerBox);
  sourcesBox.hidden = true;

  try {
    const response = await fetch(`${BACKEND_URL}/query`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ pergunta: question }),
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      const detail = data.detail || data.error || "Erro ao consultar o backend.";
      throw new Error(detail);
    }

    answerBox.hidden = false;
    answerBox.textContent = data.resposta || "Nenhuma resposta retornada.";

    if (Array.isArray(data.fontes) && data.fontes.length) {
      sourcesList.innerHTML = "";
      data.fontes.forEach((source) => {
        const item = document.createElement("li");
        item.textContent = source;
        sourcesList.appendChild(item);
      });
      sourcesBox.hidden = false;
    } else {
      sourcesBox.hidden = true;
    }

    queryStatus.textContent = "Resposta pronta.";
  } catch (error) {
    showError(queryStatus, error.message || "Não foi possível conectar ao backend.");
  } finally {
    setBusy(ingestButton, false);
    setBusy(queryButton, false);
  }
}

ingestButton.addEventListener("click", uploadPdf);
queryButton.addEventListener("click", askQuestion);

checkHealth();
