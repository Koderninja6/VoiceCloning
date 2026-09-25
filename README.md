# Heartline Voice

A small FastAPI app for creating a consent-based local voice clone with Chatterbox and turning romantic text into English, Hindi, or Korean speech.

## Run locally

1. Create a virtual environment and install dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Start the app:

```powershell
python main.py
```

Open http://127.0.0.1:8000.

Chatterbox downloads its model the first time the app generates speech. After that download, voice cloning and speech generation run locally without an API key or network request. The model download is large and requires internet access only on that first run.

The installed Chatterbox multilingual model does not support Nepali. The UI leaves Nepali visible but disabled rather than producing an inaccurate language output.

## Share through Cloudflare

Install `cloudflared`, keep the app running, then run:

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

The command prints a temporary `trycloudflare.com` URL. It stays available while both processes remain running.

Only clone a voice you own or have explicit permission to use. Do not use a clone to impersonate someone.
