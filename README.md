# OpenFlexure Stream Viewer

This folder contains a small standalone web service for the OpenFlexure Microscope. It runs on the microscope itself on a separate port, starts automatically as a service, shows only the live camera stream, and provides a single action: save the current frame as a photo on the microscope storage.

The viewer does not replace the main microscope server. It proxies the existing camera MJPEG stream from the regular OpenFlexure server, which by default is available locally on port `5000` as `/camera/mjpeg_stream`.

## What it uses from the official OpenFlexure server

The implementation follows the OpenFlexure Microscope Server documentation and the regular stream endpoint used by the main web interface.

## Files

- `openflexure_stream_viewer.py` - Python service that serves the page, proxies the stream, and saves photos locally on the microscope.
- `openflexure-stream-viewer.service` - systemd unit for automatic startup on Linux.
- `web/index.html` - Minimal page markup.
- `web/style.css` - Responsive styling.
- `web/app.js` - Stream handling and photo download logic.

## Requirements

- Python 3.11 or newer.
- The main OpenFlexure Microscope server must already be running on the microscope and exposing the camera stream locally.

## Install

Copy this folder to the microscope, for example to `/var/openflexure/application/openflexure-stream-viewer`, and make sure the main OpenFlexure Microscope server is already installed and running.

Then install the systemd unit:

```bash
sudo cp openflexure-stream-viewer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now openflexure-stream-viewer.service
```

The viewer will start automatically whenever the microscope boots.

## Run manually

If you want to test it without systemd, run it directly on the microscope:

```bash
python3 openflexure_stream_viewer.py --host 0.0.0.0 --port 8080 --upstream http://127.0.0.1:5000 --capture-dir ./captures
```

Then open:

```text
http://127.0.0.1:8080/
```

If the main microscope server listens on a different local port, change `--upstream` to match it. The viewer always proxies the stream from:

```text
<upstream>/camera/mjpeg_stream
```

## Service options

- `--host` - Address to bind to. Default: `0.0.0.0`.
- `--port` - Port for the viewer. Default: `8080`.
- `--capture-dir` - Directory used to save photos. Default: `./captures`.
- `--upstream` - Base URL of the regular OpenFlexure server on the microscope. Default: `http://127.0.0.1:5000`.

Example when the main microscope server uses a different local port:

```bash
python3 openflexure_stream_viewer.py --upstream http://127.0.0.1:5001 --port 8081 --capture-dir ./captures
```

## Notes

No extra Python packages are required. The service uses only the Python standard library and is intended to run on the microscope device itself.

If you want to keep it isolated, you can still create a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
python3 openflexure_stream_viewer.py --upstream http://127.0.0.1:5000 --port 8080 --capture-dir ./captures
```

## Behavior

- The page shows only the live camera stream.
- The camera stream is proxied through the viewer so the page can capture the current frame without cross-origin issues.
- Clicking **Save photo** stores a JPEG on the microscope under `captures/`.
- The layout is responsive and adapts to smaller screens.