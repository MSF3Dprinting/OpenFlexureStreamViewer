const stream = document.getElementById('stream');
const saveButton = document.getElementById('savePhoto');
const status = document.getElementById('status');
let streamReady = false;

function setStatus(message) {
  status.textContent = message;
}

function enableSaving() {
  streamReady = true;
  saveButton.disabled = false;
  setStatus('Live stream ready');
}

stream.addEventListener('load', enableSaving);
stream.addEventListener('error', () => {
  streamReady = false;
  saveButton.disabled = true;
  setStatus('Camera stream unavailable');
});

saveButton.addEventListener('click', async () => {
  if (!streamReady || !stream.naturalWidth || !stream.naturalHeight) {
    setStatus('Wait for the stream to load before saving');
    return;
  }

  saveButton.disabled = true;
  setStatus('Saving photo on the microscope…');

  try {
    const response = await fetch('/capture', { method: 'POST' });
    const payload = await response.json();

    if (!response.ok || !payload.ok) {
      throw new Error(payload.error || 'Unable to save the photo');
    }

    setStatus(`Photo saved on the microscope as ${payload.filename}`);
  } catch (error) {
    console.error(error);
    setStatus(error instanceof Error ? error.message : 'Unable to save the photo');
  } finally {
    saveButton.disabled = false;
  }
});
