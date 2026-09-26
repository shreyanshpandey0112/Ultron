# ULTRON — Cross-Platform Voice & AI Assistant

Ultron is an autonomous system-control intelligence built using Python. It uses the next-generation Google Gemini live function-calling architecture to directly control a local host computer or an Android mobile device connected via Android Debug Bridge (ADB). 

The application is built on top of a custom Flask backend framework wrapped inside a stable Waitress production-grade WSGI server layer, ensuring smooth background thread scheduling for heavy desktop automation pipelines.

---

## 📺 Project Walkthrough & Video Demonstration
> 💡 **For Recruiters & Evaluators:** Because API keys are kept strictly confidential and omitted from version control for security compliance, you can see a full live overview of Ultron executing system directives in this demonstration video.

[![Ultron Live Demo](https://shields.io▶-Watch%20Live%20Demo%20Video-red?style=for-the-badge&logo=youtube)](YOUR_YOUTUBE_OR_LOOM_VIDEO_LINK_HERE)

### Key Features Demonstrated in the Video:
* **Cold Voice Agent Persona:** Highly customized, MENACING system-control voice character interactions.
* **Desktop Automation Layer:** Seamless control using PyAutoGUI to launch core applications, navigate directories, and capture screenshots.
* **Mobile Bridge Layer:** Remote Android interface controls executing shell directives directly over active USB debug hooks.

---

## 🛠️ Architecture & Tech Stack
* **Language Core:** Python 3.12+
* **Backend Framework:** Flask (Asynchronous API endpoints for processing raw string directives)
* **WSGI Production Server:** Waitress (Handles execution pools securely)
* **Orchestration Layer:** Google GenAI SDK (Gemini-2.5-Flash utilizing explicit function routing constraints)
* **OS Interfacing:** PyAutoGUI & Pure-Python ADB Client (ppadb)

---

## 🚀 Setup & Evaluation Guide

Follow these steps to run the application locally on your machine with your own credentials.

### 1. Prerequisites
Ensure you have Python 3.12+ installed. If you intend to test the mobile debugging layer, ensure `adb` is added to your local system path variables.

### 2. Clone and Setup Environment
Clone the repository to your desktop environment:
```bash
git clone https://github.com
cd Ultron
```

Create a virtual environment and install the required subsystem dependencies:
```bash
python -m venv venv
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Add Your Personal API Key
This project requires a **Google AI Studio API key** to perform runtime semantic logic processing. 

1. Obtain a free testing token string directly via [Google AI Studio](https://google.com).
2. Create a new file named exactly `.env` inside the root folder of the project.
3. Paste your credentials into the file using the variable format below (do not add spaces or quotation markers):

```env
GEMINI_API_KEY=AIzaSyYourActualSecretTokenGoesHere
```
*(Note: The `.env` file is explicitly ignored inside our `.gitignore` settings configuration to prevent any security leakage.)*

### 4. Initialize the Server
Execute the main application launcher file from your terminal:
```bash
python app.py
```
Upon initialization, your terminal console line will print:
`🚀 Ultron Server starting up on http://127.0.0.1:5000`

### 5. Access the Web Console
Open **Google Chrome** (recommended for native Web Speech API recognition compatibility) and navigate to:
```text
http://127.0.0.1:5000
```
Type or speak commands like *"Open Chrome"*, *"Take a screenshot"*, or *"Device status"* to watch the agent parse and execute requests instantly.

---

## 🔒 Security Compliance
This system is meant for private desktop evaluations only. The server binds exclusively to `localhost (127.0.0.1)` inside the Waitress configuration wrapper layer. Do not modify the initialization parameters to expose this environment publically without implementing robust TLS certificates and a cryptographically sound session authorization gate.
