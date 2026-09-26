# ULTRON

Local voice and text assistant for controlling the host PC and Android devices connected over ADB. Gemini handles language and tool selection; machine-control actions run on the computer hosting this app.

## Run locally

1. Install Python 3.10 or newer.
2. Install dependencies with `python -m pip install -r requirements.txt`.
3. Set `GEMINI_API_KEY` to a Gemini API key. In PowerShell:

   ```powershell
   $env:GEMINI_API_KEY = "your-key"
   ```

4. Start the production WSGI server with `python app.py`.
5. Open `http://127.0.0.1:5000` in Chrome.

The server binds to `127.0.0.1` by default. `PORT` can select a different local port.

## Security

This app can launch programs and capture screenshots, and its API currently has no authentication. Keep it on localhost. Do not expose it to the internet or an untrusted network; public deployment requires authentication, HTTPS, and a security review. A cloud-hosted copy controls the cloud machine, not your personal PC.

`.env` is ignored by Git. Never commit API keys or other secrets.