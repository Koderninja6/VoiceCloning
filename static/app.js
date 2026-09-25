const sampleInput = document.querySelector('#sampleInput');
const uploadZone = document.querySelector('#uploadZone');
const uploadTitle = document.querySelector('#uploadTitle');
const uploadMeta = document.querySelector('#uploadMeta');
const consentInput = document.querySelector('#consentInput');
const cloneButton = document.querySelector('#cloneButton');
const speakButton = document.querySelector('#speakButton');
const messageInput = document.querySelector('#messageInput');
const languageSelect = document.querySelector('#languageSelect');
const charCount = document.querySelector('#charCount');
const player = document.querySelector('#player');
const audioPlayer = document.querySelector('#audioPlayer');
const errorMessage = document.querySelector('#errorMessage');
let selectedFile = null;
let voiceId = null;

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.hidden = false;
}

function clearError() {
  errorMessage.hidden = true;
  errorMessage.textContent = '';
}

function setLoading(button, loading) {
  button.classList.toggle('loading', loading);
  button.disabled = loading;
}

async function readResponse(response) {
  const body = await response.text();
  try {
    return JSON.parse(body);
  } catch {
    throw new Error(body.trim().slice(0, 300) || `Request failed (${response.status}).`);
  }
}

function updateCloneState() {
  cloneButton.disabled = !selectedFile || !consentInput.checked;
}

sampleInput.addEventListener('change', () => {
  selectedFile = sampleInput.files[0] || null;
  if (!selectedFile) return;
  uploadTitle.textContent = selectedFile.name;
  uploadMeta.textContent = `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB · ready to create your voice`;
  uploadZone.classList.add('has-file');
  clearError();
  updateCloneState();
});

['dragenter', 'dragover'].forEach((eventName) => uploadZone.addEventListener(eventName, (event) => {
  event.preventDefault();
  uploadZone.classList.add('dragging');
}));
['dragleave', 'drop'].forEach((eventName) => uploadZone.addEventListener(eventName, (event) => {
  event.preventDefault();
  uploadZone.classList.remove('dragging');
}));
uploadZone.addEventListener('drop', (event) => {
  const [file] = event.dataTransfer.files;
  if (!file || (!file.type.startsWith('audio/') && file.type !== 'video/mp4' && !file.name.toLowerCase().endsWith('.mp4'))) {
    showError('Please choose an audio or MP4 recording.');
    return;
  }
  selectedFile = file;
  uploadTitle.textContent = file.name;
  uploadMeta.textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB · ready to create your voice`;
  uploadZone.classList.add('has-file');
  updateCloneState();
});
consentInput.addEventListener('change', updateCloneState);

cloneButton.addEventListener('click', async () => {
  if (!selectedFile) return;
  clearError();
  setLoading(cloneButton, true);
  const formData = new FormData();
  formData.append('sample', selectedFile);
  try {
    const response = await fetch('/api/clone', { method: 'POST', body: formData });
    const data = await readResponse(response);
    if (!response.ok) throw new Error(data.detail || 'Could not create the voice.');
    voiceId = data.voice_id;
    speakButton.disabled = false;
    cloneButton.querySelector('.button-label').textContent = 'Voice ready';
    cloneButton.classList.remove('button-dark');
    cloneButton.classList.add('button-coral');
  } catch (error) {
    showError(error.message);
  } finally {
    setLoading(cloneButton, false);
    cloneButton.disabled = Boolean(voiceId) || !selectedFile || !consentInput.checked;
  }
});

document.querySelectorAll('.preset').forEach((button) => button.addEventListener('click', () => {
  document.querySelectorAll('.preset').forEach((item) => item.classList.remove('active'));
  button.classList.add('active');
  messageInput.value = button.dataset.text;
  charCount.textContent = messageInput.value.length;
}));

messageInput.addEventListener('input', () => {
  charCount.textContent = messageInput.value.length;
  document.querySelectorAll('.preset').forEach((item) => item.classList.remove('active'));
});

speakButton.addEventListener('click', async () => {
  clearError();
  const text = messageInput.value.trim();
  if (!voiceId || !text) return;
  setLoading(speakButton, true);
  try {
    const response = await fetch('/api/speak', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ voice_id: voiceId, text, language: languageSelect.value }),
    });
    const data = await readResponse(response);
    if (!response.ok) throw new Error(data.detail || 'Could not create the speech.');
    audioPlayer.src = `${data.audio_url}?t=${Date.now()}`;
    player.hidden = false;
    audioPlayer.play().catch(() => {});
  } catch (error) {
    showError(error.message);
  } finally {
    setLoading(speakButton, false);
  }
});
