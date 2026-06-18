const stream = document.getElementById('stream');
const saveButton = document.getElementById('savePhoto');
const status = document.getElementById('status');
const captureCanvas = document.getElementById('captureCanvas');
const captureContext = captureCanvas.getContext('2d');
let streamReady = false;
let retryTimer = null;

function refreshStream() {
  window.clearTimeout(retryTimer);
  streamReady = false;
  saveButton.disabled = true;
  stream.removeAttribute('src');

  window.setTimeout(() => {
    stream.src = '/camera/mjpeg_stream';
  }, 120);
}

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
  window.clearTimeout(retryTimer);
  retryTimer = window.setTimeout(refreshStream, 5000);
});

window.addEventListener('pageshow', refreshStream);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) {
    refreshStream();
  }
});

stream.src = '/camera/mjpeg_stream';

saveButton.addEventListener('click', async () => {
  if (!streamReady || !stream.naturalWidth || !stream.naturalHeight) {
    setStatus('Wait for the stream to load before saving');
    return;
  }

  saveButton.disabled = true;
  setStatus('Saving photo to this computer…');

  try {
    captureCanvas.width = stream.naturalWidth;
    captureCanvas.height = stream.naturalHeight;
    captureContext.drawImage(stream, 0, 0, captureCanvas.width, captureCanvas.height);

    const blob = await new Promise((resolve, reject) => {
      captureCanvas.toBlob((result) => {
        if (result) {
          resolve(result);
          return;
        }

        reject(new Error('Could not capture the current frame.'));
      }, 'image/png');
    });

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    const downloadLink = document.createElement('a');
    downloadLink.href = URL.createObjectURL(blob);
    downloadLink.download = `openflexure-photo-${timestamp}.png`;
    document.body.appendChild(downloadLink);
    downloadLink.click();
    downloadLink.remove();
    URL.revokeObjectURL(downloadLink.href);
    setStatus('Photo saved to this computer');
  } catch (error) {
    console.error(error);
    setStatus(error instanceof Error ? error.message : 'Unable to save the photo');
  } finally {
    saveButton.disabled = false;
  }
});
