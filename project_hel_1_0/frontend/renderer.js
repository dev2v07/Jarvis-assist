const apiBase = 'http://127.0.0.1:8000';
const chat = document.getElementById('chat');
const input = document.getElementById('input');
const send = document.getElementById('send');
const modeList = document.getElementById('modeList');
const historyList = document.getElementById('historyList');
const modeTitle = document.getElementById('modeTitle');
const modeDescription = document.getElementById('modeDescription');
const apiStatus = document.getElementById('apiStatus');
const providerStatus = document.getElementById('providerStatus');
const refreshApp = document.getElementById('refreshApp');
const statusDot = document.querySelector('.status-dot');
const overlay = document.getElementById('modalOverlay');
const planModal = document.getElementById('planModal');
const planMessage = document.getElementById('planMessage');
const planApprove = document.getElementById('planApprove');
const planReject = document.getElementById('planReject');
const permissionModal = document.getElementById('permissionModal');
const permissionMessage = document.getElementById('permissionMessage');
const permissionAllow = document.getElementById('permissionAllow');
const permissionDeny = document.getElementById('permissionDeny');
const settingsModal = document.getElementById('settingsModal');
const openSettings = document.getElementById('openSettings');
const closeSettings = document.getElementById('closeSettings');
const providerSelect = document.getElementById('providerSelect');
const ollamaBaseUrl = document.getElementById('ollamaBaseUrl');
const ollamaModel = document.getElementById('ollamaModel');
const openaiBaseUrl = document.getElementById('openaiBaseUrl');
const openaiModel = document.getElementById('openaiModel');
const openaiApiKey = document.getElementById('openaiApiKey');
const llmTimeout = document.getElementById('llmTimeout');
const llmRetries = document.getElementById('llmRetries');
const runtimeEnvPath = document.getElementById('runtimeEnvPath');
const settingsTestResult = document.getElementById('settingsTestResult');
const testSettingsBtn = document.getElementById('testSettings');
const saveSettingsBtn = document.getElementById('saveSettings');
const fallbackModes = [
  { key: 'general', title: 'Общий', description: 'Универсальный режим ассистента', icon: '●' },
  { key: 'file', title: 'Файлы', description: 'Работа с файлами в workspace', icon: '▣' },
  { key: 'sysadmin', title: 'Система', description: 'Диагностика CPU, RAM и диска', icon: '◫' },
  { key: 'network', title: 'Сеть', description: 'Проверка URL и HTTP-запросы', icon: '◌' },
  { key: 'backup', title: 'Резервные копии', description: 'Создание backup локальных данных', icon: '◍' },
];
let pollingTimer = null, activeRequestId = null, pendingPlanId = null, pendingPermissionId = null, seenEvents = new Set(), modes = [...fallbackModes], currentMode = 'general', onboardingShown = false, lastHistory = [];
function setModalVisible(modal, visible){modal.classList.toggle('hidden',!visible);const anyVisible=[planModal,permissionModal,settingsModal].some(el=>!el.classList.contains('hidden'));overlay.classList.toggle('hidden',!anyVisible)}
function addMessage(role,text){const node=document.createElement('div');node.className=`message ${role}`;node.textContent=text;chat.appendChild(node);chat.scrollTop=chat.scrollHeight}
function setBackendIndicator(state,text){apiStatus.textContent=text;statusDot.classList.remove('online','offline');if(state==='online')statusDot.classList.add('online');else if(state==='offline')statusDot.classList.add('offline')}
async function api(path,options={}){const controller=new AbortController();const timeoutMs=Number(options.timeoutMs||8000);const timer=setTimeout(()=>controller.abort(),timeoutMs);let response;try{response=await fetch(`${apiBase}${path}`,{headers:{'Content-Type':'application/json',...(options.headers||{})},...options,signal:controller.signal})}catch(error){if(error.name==='AbortError')throw new Error('Таймаут подключения к backend');throw error}finally{clearTimeout(timer)}if(!response.ok){let detail=`HTTP ${response.status}`;try{const data=await response.json();detail=data.detail?JSON.stringify(data.detail):detail}catch(_){}throw new Error(detail)}return response.json()}
async function apiWithRetry(path,options={},attempts=5){let lastError=null;for(let attempt=1;attempt<=attempts;attempt+=1){try{return await api(path,options)}catch(error){lastError=error;await new Promise(resolve=>setTimeout(resolve,700*attempt))}}throw lastError}
function settingsPayload(){return{provider:providerSelect.value,ollama_base_url:ollamaBaseUrl.value.trim(),ollama_model:ollamaModel.value.trim(),openai_base_url:openaiBaseUrl.value.trim(),openai_model:openaiModel.value.trim(),openai_api_key:openaiApiKey.value.trim(),llm_request_timeout:Number(llmTimeout.value||45),llm_max_retries:Number(llmRetries.value||2),network_request_timeout:20,network_max_retries:2}}
function fillSettings(data){const cfg=data.config||{};providerSelect.value=data.provider||cfg.HEL_LLM_PROVIDER||'stub';ollamaBaseUrl.value=cfg.HEL_OLLAMA_BASE_URL||'http://127.0.0.1:11434';ollamaModel.value=cfg.HEL_OLLAMA_MODEL||'qwen2.5:7b-q4_K_M';openaiBaseUrl.value=cfg.HEL_OPENAI_BASE_URL||'https://api.openai.com/v1';openaiModel.value=cfg.HEL_OPENAI_MODEL||'gpt-4o-mini';openaiApiKey.value='';openaiApiKey.placeholder=cfg.HEL_OPENAI_API_KEY||'sk-...';llmTimeout.value=cfg.HEL_LLM_REQUEST_TIMEOUT||45;llmRetries.value=cfg.HEL_LLM_MAX_RETRIES||2;runtimeEnvPath.textContent=data.runtime_env_path||'-';providerStatus.textContent=data.provider||'stub';const test=data.llm_connection||{};settingsTestResult.textContent=test.message||'Пока не проверено.';if(data.needs_onboarding&&!onboardingShown){onboardingShown=true;setModalVisible(settingsModal,true);addMessage('system',data.onboarding_message||'Нужно один раз настроить LLM и API-ключ.')}}
async function loadSettings(showModal=false){try{const data=await api('/settings',{timeoutMs:4000});fillSettings(data);if(showModal)setModalVisible(settingsModal,true)}catch(error){if(showModal)setModalVisible(settingsModal,true);settingsTestResult.textContent=`Backend недоступен: ${error.message}`;addMessage('system',`Настройки пока не загружены: ${error.message}`)}}
async function checkHealth(retry=true){try{const data=retry?await apiWithRetry('/health',{timeoutMs:2500},5):await api('/health',{timeoutMs:2500});setBackendIndicator('online',`${data.status} / ${data.model_backend}`);providerStatus.textContent=data.model_backend||'stub';return true}catch(error){setBackendIndicator('offline','offline');addMessage('system','Backend пока недоступен. Открой настройки позже или проверь запуск Python/FastAPI.');return false}}
async function loadModes(){try{const data=await api('/modes',{timeoutMs:4000});modes=Array.isArray(data)&&data.length?data:[...fallbackModes]}catch(_){modes=[...fallbackModes]}renderModes()}
async function loadHistory(){try{const data=await api('/requests?limit=12',{timeoutMs:4000});lastHistory=Array.isArray(data)?data:[]}catch(_){lastHistory=[]}renderHistory()}
function renderModes(){modeList.innerHTML='';for(const mode of modes){const btn=document.createElement('button');btn.className='mode-item'+(mode.key===currentMode?' active':'');btn.innerHTML=`<strong>${mode.icon||''} ${mode.title}</strong><small>${mode.description}</small>`;btn.onclick=()=>{currentMode=mode.key;modeTitle.textContent=mode.title;modeDescription.textContent=mode.description;[...modeList.children].forEach(el=>el.classList.remove('active'));btn.classList.add('active');addMessage('system',`Режим переключён: ${mode.title}`)};modeList.appendChild(btn)}}
function renderHistory(){historyList.innerHTML='';if(!lastHistory.length){const empty=document.createElement('div');empty.className='history-empty';empty.textContent='История появится после первых задач.';historyList.appendChild(empty);return}for(const item of lastHistory){const btn=document.createElement('button');btn.className='history-item'+(item.request_id===activeRequestId?' active':'');const goal=item.goal||'Без названия';btn.innerHTML=`<strong>${goal}</strong><small>${item.mode||'general'}</small><div class="history-status">${item.status||'unknown'}</div>`;btn.onclick=()=>{activeRequestId=item.request_id;seenEvents=new Set();addMessage('system',`Открыта история задачи: ${goal}`);startPolling(item.request_id,true);renderHistory()};historyList.appendChild(btn)}}
function processState(state){for(let i=0;i<state.events.length;i+=1){const event=state.events[i];const key=`${state.request_id}:${i}:${event.type}`;if(seenEvents.has(key))continue;seenEvents.add(key);if(event.type==='plan_requested'){pendingPlanId=state.request_id;const steps=(event.data.steps||[]).map(step=>typeof step==='string'?step:(step.title||JSON.stringify(step)));planMessage.textContent=`Цель:\n${event.data.goal||state.goal}\n\nПлан:\n- ${steps.join('\n- ')}`;setModalVisible(planModal,true);addMessage('system','План готов. Нужна проверка пользователя.')}else if(event.type==='step_started'){addMessage('system',`Шаг ${event.data.index||'?'} / ${event.data.total||'?'}: ${event.data.step}`)}else if(event.type==='step_finished'){addMessage('system',`Шаг завершён: ${event.data.step}`)}else if(event.type==='permission_requested'){pendingPermissionId=event.data.request_id;permissionMessage.textContent=event.data.reason||'Требуется разрешение на действие.';setModalVisible(permissionModal,true);addMessage('system','Запрошено разрешение на действие.')}else if(event.type==='final_response'){addMessage('assistant',event.data.result)}else if(event.type==='request_failed'){addMessage('assistant',`Ошибка: ${event.data.error}`)}}if(state.status==='completed'||state.status==='failed'){stopPolling();loadHistory()}}
async function pollRequest(){if(!activeRequestId)return;try{const state=await api(`/requests/${activeRequestId}`);processState(state)}catch(error){addMessage('assistant',`Ошибка чтения статуса выполнения: ${error.message}`);stopPolling()}}
function startPolling(requestId,immediate=false){stopPolling();activeRequestId=requestId;if(!immediate)seenEvents=new Set();pollRequest();pollingTimer=setInterval(pollRequest,1200)}
function stopPolling(){if(pollingTimer)clearInterval(pollingTimer);pollingTimer=null}
async function sendMessage(){const text=input.value.trim();if(!text)return;input.value='';addMessage('user',text);addMessage('system','Запрос принят. Строим план и отслеживаем выполнение...');send.disabled=true;try{const data=await api('/chat',{method:'POST',body:JSON.stringify({message:text,mode:currentMode})});startPolling(data.request_id);await loadHistory()}catch(error){addMessage('assistant',`Ошибка связи с backend: ${error.message}`)}finally{send.disabled=false}}
send.onclick=sendMessage;input.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter')sendMessage()});
planApprove.onclick=async()=>{if(!pendingPlanId)return;await api('/plan_approval',{method:'POST',body:JSON.stringify({original_msg_id:pendingPlanId,approved:true})});pendingPlanId=null;setModalVisible(planModal,false)};
planReject.onclick=async()=>{if(!pendingPlanId)return;await api('/plan_approval',{method:'POST',body:JSON.stringify({original_msg_id:pendingPlanId,approved:false})});pendingPlanId=null;setModalVisible(planModal,false);await loadHistory()};
permissionAllow.onclick=async()=>{if(!pendingPermissionId)return;await api('/permission_response',{method:'POST',body:JSON.stringify({request_id:pendingPermissionId,allowed:true})});pendingPermissionId=null;setModalVisible(permissionModal,false)};
permissionDeny.onclick=async()=>{if(!pendingPermissionId)return;await api('/permission_response',{method:'POST',body:JSON.stringify({request_id:pendingPermissionId,allowed:false})});pendingPermissionId=null;setModalVisible(permissionModal,false);await loadHistory()};
openSettings.onclick=()=>loadSettings(true);closeSettings.onclick=()=>setModalVisible(settingsModal,false);refreshApp.onclick=async()=>{await bootstrap();addMessage('system','Статус и история обновлены.')};
testSettingsBtn.onclick=async()=>{settingsTestResult.textContent='Проверяем подключение...';try{const data=await api('/settings/test',{method:'POST',body:JSON.stringify(settingsPayload())});settingsTestResult.textContent=data.message||(data.ok?'Подключение успешно.':'Подключение не удалось.')}catch(error){settingsTestResult.textContent=`Ошибка проверки: ${error.message}`}};
saveSettingsBtn.onclick=async()=>{settingsTestResult.textContent='Сохраняем настройки...';try{const data=await api('/settings',{method:'POST',body:JSON.stringify(settingsPayload())});fillSettings(data);settingsTestResult.textContent=(data.llm_connection&&data.llm_connection.message)||'Сохранено.';addMessage('system','Настройки LLM сохранены. Их можно менять прямо из окна приложения.');await checkHealth(false)}catch(error){settingsTestResult.textContent=`Ошибка сохранения: ${error.message}`}};
async function bootstrap(){const online=await checkHealth(true);await Promise.allSettled([loadModes(),loadHistory(),loadSettings(false)]);if(!online)addMessage('system','Если backend не поднимается, запусти его вручную: python backend/main.py')}
window.addEventListener('load',async()=>{addMessage('assistant','Добро пожаловать в Проект Хель.');if(window.helApp?.version)addMessage('system',`UI bridge активен, версия ${window.helApp.version}`);await bootstrap();addMessage('system','Кнопка «LLM / API ключ» слева открывает быстрые настройки провайдера и ключа.')});
