const axios = require('axios');

const apiBase = 'http://127.0.0.1:8000';
const chat = document.getElementById('chat');
const input = document.getElementById('input');
const send = document.getElementById('send');
const apiStatus = document.getElementById('apiStatus');
const modeList = document.getElementById('modeList');
const modeTitle = document.getElementById('modeTitle');
const modeDescription = document.getElementById('modeDescription');

const modalOverlay = document.getElementById('modalOverlay');
const planModal = document.getElementById('planModal');
const planMessage = document.getElementById('planMessage');
const planApprove = document.getElementById('planApprove');
const planReject = document.getElementById('planReject');

const permissionModal = document.getElementById('permissionModal');
const permissionMessage = document.getElementById('permissionMessage');
const permissionAllow = document.getElementById('permissionAllow');
const permissionDeny = document.getElementById('permissionDeny');

let currentMode = 'general';
let pendingPlanId = null;
let pendingPermissionId = null;
let modes = [];

function addMessage(role, text) {
  const div = document.createElement('div');
  div.className = `message ${role}`;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

function setModalVisible(modal, visible) {
  modal.classList.toggle('hidden', !visible);
  modalOverlay.classList.toggle('hidden', !visible && planModal.classList.contains('hidden') && permissionModal.classList.contains('hidden'));
}

async function checkHealth() {
  try {
    const { data } = await axios.get(`${apiBase}/health`);
    apiStatus.textContent = `${data.status} / ${data.model_backend}`;
  } catch {
    apiStatus.textContent = 'offline';
  }
}

async function loadModes() {
  const { data } = await axios.get(`${apiBase}/modes`);
  modes = data;
  renderModes();
}

function renderModes() {
  modeList.innerHTML = '';
  for (const mode of modes) {
    const btn = document.createElement('button');
    btn.className = 'mode-item' + (mode.key === currentMode ? ' active' : '');
    btn.innerHTML = `<strong>${mode.icon || ''} ${mode.title}</strong><small>${mode.description}</small>`;
    btn.onclick = () => {
      currentMode = mode.key;
      modeTitle.textContent = mode.title;
      modeDescription.textContent = mode.description;
      [...modeList.children].forEach(el => el.classList.remove('active'));
      btn.classList.add('active');
      addMessage('system', `Режим переключён: ${mode.title}`);
    };
    modeList.appendChild(btn);
  }
}

async function sendMessage() {
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  addMessage('user', text);
  addMessage('system', 'Построение плана...');
  try {
    const { data } = await axios.post(`${apiBase}/chat`, { message: text, mode: currentMode });
    addMessage('assistant', data.response);
  } catch (error) {
    addMessage('assistant', 'Ошибка связи с backend. Проверьте запуск FastAPI.');
    console.error(error);
  }
}

send.onclick = sendMessage;
input.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') sendMessage();
});

planApprove.onclick = async () => {
  if (!pendingPlanId) return;
  await axios.post(`${apiBase}/plan_approval`, { original_msg_id: pendingPlanId, approved: true });
  pendingPlanId = null;
  setModalVisible(planModal, false);
};

planReject.onclick = async () => {
  if (!pendingPlanId) return;
  await axios.post(`${apiBase}/plan_approval`, { original_msg_id: pendingPlanId, approved: false });
  pendingPlanId = null;
  setModalVisible(planModal, false);
};

permissionAllow.onclick = async () => {
  if (!pendingPermissionId) return;
  await axios.post(`${apiBase}/permission_response`, { request_id: pendingPermissionId, allowed: true });
  pendingPermissionId = null;
  setModalVisible(permissionModal, false);
};

permissionDeny.onclick = async () => {
  if (!pendingPermissionId) return;
  await axios.post(`${apiBase}/permission_response`, { request_id: pendingPermissionId, allowed: false });
  pendingPermissionId = null;
  setModalVisible(permissionModal, false);
};

window.addEventListener('load', async () => {
  addMessage('assistant', 'Добро пожаловать в Проект Хель. Backend и frontend готовы к работе.');
  await checkHealth();
  await loadModes();
});
