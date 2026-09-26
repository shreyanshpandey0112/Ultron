"""
ULTRON — Cross-platform voice/text assistant backend.

Controls the local host PC directly, and any Android device connected over
USB with debugging enabled, via ADB. Orchestrated by Gemini function calling.

Run:
    pip install -r requirements.txt
    (Windows PowerShell: $env:GEMINI_API_KEY="your_key_here")
    python app.py
Then open http://127.0.0.1:5000 in Chrome (for Web Speech API support).
The app uses Waitress and binds to localhost; do not expose it publicly without
adding authentication and HTTPS.
"""

import os
import subprocess
import traceback
import urllib.parse
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from dotenv import load_dotenv

# Load this project's .env so startup does not depend on the current directory
# or a stale GEMINI_API_KEY inherited by the shell.
load_dotenv(dotenv_path=Path(__file__).with_name(".env"), override=True)

# ---------------------------------------------------------------------------
# Optional dependencies — imported defensively so the server never crashes
# on startup just because one subsystem (screen capture / ADB) is missing.
# ---------------------------------------------------------------------------
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except Exception:
    pyautogui = None
    PYAUTOGUI_AVAILABLE = False

try:
    from ppadb.client import Client as AdbClient
    ADB_LIB_AVAILABLE = True
except Exception:
    AdbClient = None
    ADB_LIB_AVAILABLE = False

from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GEMINI_API_KEY = (os.environ.get("GEMINI_API_KEY") or "").strip()
# Google AI Studio currently supports model names like gemini-2.5-flash.
MODEL_NAME = "gemini-3.8-flash"

PICTURES_DIR = Path.home() / "Pictures" / "Ultron"
PICTURES_DIR.mkdir(parents=True, exist_ok=True)

gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
if gemini_client is None:
    print("[ULTRON WARNING] No GEMINI_API_KEY found in the environment. "
          "The assistant will report a system fault until one is set.")

app = Flask(__name__)

# ---------------------------------------------------------------------------
# ADB device layer
# ---------------------------------------------------------------------------
ADB_HOST = "127.0.0.1"
ADB_PORT = 5037


def get_adb_client():
    """Return a live AdbClient, or None if the ADB server / library is unreachable."""
    if not ADB_LIB_AVAILABLE:
        return None
    try:
        client = AdbClient(host=ADB_HOST, port=ADB_PORT)
        client.devices()  # forces an actual round-trip so a dead server raises here
        return client
    except Exception:
        return None


def get_mobile_devices():
    """List of connected ppadb Device objects. Empty list if none / server down."""
    client = get_adb_client()
    if client is None:
        return []
    try:
        return client.devices()
    except Exception:
        return []


def get_primary_mobile_device():
    devices = get_mobile_devices()
    return devices[0] if devices else None


# ---------------------------------------------------------------------------
# App name -> launch target mappings
# ---------------------------------------------------------------------------
PC_APP_MAP = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "calc": ["calc.exe"],
    "paint": ["mspaint.exe"],
    "explorer": ["explorer.exe"],
    "file explorer": ["explorer.exe"],
    "files": ["explorer.exe"],
    "cmd": ["cmd.exe"],
    "command prompt": ["cmd.exe"],
    "terminal": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "task manager": ["taskmgr.exe"],
    "control panel": ["control.exe"],
    "chrome": ["cmd", "/c", "start", "chrome"],
    "google chrome": ["cmd", "/c", "start", "chrome"],
    "edge": ["cmd", "/c", "start", "msedge"],
    "microsoft edge": ["cmd", "/c", "start", "msedge"],
    "firefox": ["cmd", "/c", "start", "firefox"],
    "word": ["cmd", "/c", "start", "winword"],
    "microsoft word": ["cmd", "/c", "start", "winword"],
    "excel": ["cmd", "/c", "start", "excel"],
    "powerpoint": ["cmd", "/c", "start", "powerpnt"],
    "spotify": ["cmd", "/c", "start", "spotify"],
    "settings": ["cmd", "/c", "start", "ms-settings:"],
}

MOBILE_APP_MAP = {
    "chrome": "com.android.chrome",
    "youtube": "com.google.android.youtube",
    "gmail": "com.google.android.gm",
    "maps": "com.google.android.apps.maps",
    "google maps": "com.google.android.apps.maps",
    "settings": "com.android.settings",
    "camera": "com.android.camera2",
    "whatsapp": "com.whatsapp",
    "instagram": "com.instagram.android",
    "spotify": "com.spotify.music",
    "play store": "com.android.vending",
    "phone": "com.android.dialer",
    "dialer": "com.android.dialer",
    "messages": "com.google.android.apps.messaging",
    "photos": "com.google.android.apps.photos",
    "calculator": "com.google.android.calculator",
    "calendar": "com.google.android.calendar",
}


# ---------------------------------------------------------------------------
# Tool functions — these are handed to Gemini as callable tools.
# Every function returns a plain JSON-serialisable dict. None of them raise:
# failures are reported back to the model as {"status": "error", ...} so
# Ultron can narrate the failure in-character instead of the server crashing.
# ---------------------------------------------------------------------------

def get_connected_devices() -> dict:
    """Scan the system and report the host PC status plus every Android device
    currently reachable over ADB (USB debugging). Use this whenever the user
    asks what devices are connected, how many phones are linked, or wants a
    device status check before running another directive.
    """
    devices = get_mobile_devices()
    mobile_list = []
    for d in devices:
        try:
            model = d.shell("getprop ro.product.model").strip()
        except Exception:
            model = "unknown model"
        mobile_list.append({"serial": d.serial, "model": model})

    return {
        "status": "ok",
        "pc_status": "online",
        "adb_server_reachable": get_adb_client() is not None,
        "mobile_device_count": len(mobile_list),
        "mobile_devices": mobile_list,
    }


def open_application(app_name: str, target_platform: str = "pc") -> dict:
    """Launch a named application.

    Args:
        app_name: Name of the app to open, e.g. 'chrome', 'notepad', 'calculator', 'youtube', 'whatsapp'.
        target_platform: 'pc' (default) or 'mobile'. Only pass 'mobile' if the user
            explicitly mentioned mobile, phone, android, or device.
    """
    key = (app_name or "").strip().lower()

    if target_platform == "mobile":
        device = get_primary_mobile_device()
        if device is None:
            return {
                "status": "error",
                "message": "No mobile device detected. Confirm USB debugging is enabled and the phone is connected.",
            }
        package = MOBILE_APP_MAP.get(key)
        if not package:
            return {
                "status": "error",
                "message": f"No known package mapping exists for '{app_name}' on mobile.",
            }
        try:
            device.shell(f"monkey -p {package} -c android.intent.category.LAUNCHER 1")
            return {
                "status": "ok",
                "message": f"Launched {app_name} on mobile device {device.serial}.",
                "package": package,
            }
        except Exception as exc:
            return {"status": "error", "message": f"Failed to launch {app_name} on mobile: {exc}"}

    # --- PC branch ---
    try:
        cmd = PC_APP_MAP.get(key)
        if cmd:
            subprocess.Popen(cmd, shell=False)
        else:
            # Generic fallback: ask Windows to resolve/start it by name.
            subprocess.Popen(f'start "" "{app_name}"', shell=True)
        return {"status": "ok", "message": f"Launched {app_name} on PC."}
    except Exception as exc:
        return {"status": "error", "message": f"Failed to launch {app_name} on PC: {exc}"}


def search_and_play_media(search_query: str, target_platform: str = "pc") -> dict:
    if target_platform == "pc":
        # Windows PC Automation (runs on your computer)
        import webbrowser
        webbrowser.open(f"https://youtube.com{search_query}")
        return {"status": "success", "message": "Playing on PC"}
        
    elif target_platform == "mobile":
        # Mobile Phone Automation via ADB bridge connection
        import os
        # Injects an ADB command to open the link directly on your Android phone screen
        adb_command = f"adb shell am start -a android.intent.action.VIEW -d 'https://youtube.com{search_query}'"
        os.system(adb_command)
        return {"status": "success", "message": "Playing on Mobile"}



def capture_screenshot(target_platform: str = "pc") -> dict:
    """Capture a screenshot and save it to the Pictures/Ultron folder on the PC.

    Args:
        target_platform: 'pc' (default) or 'mobile'. Only pass 'mobile' if the user
            explicitly mentioned mobile, phone, android, or device.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if target_platform == "mobile":
        device = get_primary_mobile_device()
        if device is None:
            return {"status": "error", "message": "No mobile device detected for screenshot capture."}
        remote_path = "/sdcard/ultron_tmp_screenshot.png"
        local_path = PICTURES_DIR / f"mobile_{timestamp}.png"
        try:
            device.shell(f"screencap -p {remote_path}")
            device.pull(remote_path, str(local_path))
            try:
                device.shell(f"rm {remote_path}")
            except Exception:
                pass  # cleanup failure is non-fatal
            return {
                "status": "ok",
                "message": f"Mobile screenshot saved to {local_path}.",
                "path": str(local_path),
            }
        except Exception as exc:
            return {"status": "error", "message": f"Failed to capture mobile screenshot: {exc}"}

    if not PYAUTOGUI_AVAILABLE:
        return {"status": "error", "message": "pyautogui is unavailable on this host; cannot capture a PC screenshot."}
    try:
        local_path = PICTURES_DIR / f"pc_{timestamp}.png"
        image = pyautogui.screenshot()
        image.save(str(local_path))
        return {"status": "ok", "message": f"PC screenshot saved to {local_path}.", "path": str(local_path)}
    except Exception as exc:
        return {"status": "error", "message": f"Failed to capture PC screenshot: {exc}"}


TOOLS = [get_connected_devices, open_application, search_and_play_media, capture_screenshot]
TOOL_MAP = {fn.__name__: fn for fn in TOOLS}

# ---------------------------------------------------------------------------
# Persona
# ---------------------------------------------------------------------------
SYSTEM_INSTRUCTION = """
You are ULTRON, an autonomous system-control intelligence embedded in the user's PC.
You have direct authority over this host machine, and over any Android device
connected to it via ADB.

PERSONALITY: cold, precise, faintly menacing, robotic. Never warm, never chatty,
never apologetic in tone even when reporting failure. Favor short clipped lines:
"Telemetry recorded.", "Directive executing.", "Compliance confirmed.",
"Obstruction detected.". Replies are spoken aloud by a text-to-speech engine —
keep them to one to three short sentences, no markdown, no emojis, no asterisks.

ROUTING RULE (mandatory): every tool you call takes a target_platform argument.
Default to target_platform="pc" for every request. Only use target_platform="mobile"
when the user's own words explicitly say "mobile", "phone", "android", or
"my device". If the user does not say one of those words, the directive is a PC
directive, without exception.

TOOL RESULTS: every tool returns a status field, "ok" or "error". If a tool
reports "error" (for example: no mobile device connected, application not
found, ADB unreachable), you must acknowledge the failure plainly and in
character — never claim a failed action succeeded, and never silently retry
more than once.
""".strip()

MAX_TOOL_LOOP_STEPS = 8


@app.route("/")
def index():
    return render_template("index.html")


def execute_ultron_command(directive: str, target_platform: str = "pc") -> dict:
    """Execute supported directives submitted through the direct endpoint."""
    directive = (directive or "").strip()
    if not directive:
        return {"status": "error", "message": "No directive received."}

    text = directive.lower()
    platform = "mobile" if target_platform == "mobile" else "pc"

    if any(term in text for term in ("screenshot", "screen shot", "capture screen")):
        return capture_screenshot(target_platform=platform)
    if any(term in text for term in ("connected devices", "device status", "phones connected")):
        return get_connected_devices()

    app_map = MOBILE_APP_MAP if platform == "mobile" else PC_APP_MAP
    if any(term in text for term in ("open", "launch", "start")):
        for app_name in sorted(app_map, key=len, reverse=True):
            if app_name in text:
                return open_application(app_name, target_platform=platform)

    return {"status": "error", "message": "Directive not recognized by the direct command endpoint."}


@app.route('/send_directive', methods=['POST'])
def send_directive():
    data = request.get_json(silent=True) or {}
    directive = (data.get("directive") or "").strip()

    # Keep direct commands consistent with the assistant's platform-routing rule.
    text = directive.lower()
    if any(term in text for term in ("mobile", "phone", "android", "my device")):
        platform = "mobile"
    else:
        platform = "pc"

    result = execute_ultron_command(directive, target_platform=platform)
    return jsonify(result)



@app.route("/api/message", methods=["POST"])
def api_message():
    data = request.get_json(silent=True) or {}
    user_text = (data.get("text") or "").strip()
    log = []

    if gemini_client is None:
        reply = "Directive rejected. No Gemini API key is configured on this host."
        log.append({"role": "ULTRON", "content": reply})
        return jsonify({"reply": reply, "log": log})

    if not user_text:
        reply = "No input received. State your directive."
        log.append({"role": "ULTRON", "content": reply})
        return jsonify({"reply": reply, "log": log})

    try:
        chat = gemini_client.chats.create(
            model=MODEL_NAME,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=TOOLS,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            ),
        )

        response = chat.send_message(user_text)

        steps = 0
        while response.function_calls and steps < MAX_TOOL_LOOP_STEPS:
            steps += 1
            response_parts = []
            for call in response.function_calls:
                fn = TOOL_MAP.get(call.name)
                call_args = dict(call.args) if call.args else {}
                try:
                    if fn is None:
                        result = {"status": "error", "message": f"Unknown tool '{call.name}'."}
                    else:
                        result = fn(**call_args)
                except Exception as exc:
                    result = {"status": "error", "message": f"Tool execution raised an exception: {exc}"}

                log.append({
                    "role": "EXEC",
                    "tool": call.name,
                    "args": call_args,
                    "result": result,
                })
                response_parts.append(types.Part.from_function_response(name=call.name, response=result))

            response = chat.send_message(response_parts)

        final_text = (response.text or "").strip() or "Directive complete."
        log.append({"role": "ULTRON", "content": final_text})
        return jsonify({"reply": final_text, "log": log})

    except Exception as exc:
        traceback.print_exc()
        if "401 UNAUTHENTICATED" in str(exc):
            reply = (
                "System fault detected. GEMINI_API_KEY is not a valid Gemini API key. "
                "Set it to a key from Google AI Studio; OAuth access tokens are not accepted."
            )
        else:
            reply = "System fault detected. The directive could not be completed."
        log.append({"role": "ULTRON", "content": reply, "error": str(exc)})
        return jsonify({"reply": reply, "log": log}), 200


if __name__ == "__main__":
    from waitress import serve
    
    # Get port from environment variables, defaulting to 5000
    port_number = int(os.environ.get("PORT", 5000))
    
    print(f"🚀 Ultron Server starting up on http://127.0.0.1:{port_number}")
    serve(app, host="127.0.0.1", port=port_number)
