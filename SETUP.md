# BroPilot Workbench Setup

## Prerequisites

- Windows PowerShell
- Python 3.12
- Node.js 20 or newer
- Git
- OpenAI API key

## 1. Clone the Repo

```powershell
git clone https://github.com/jualam/BroPilot.git
cd BroPilot
```

If the repo already exists locally:

```powershell
cd D:\BroPilot
```

## 2. Backend Setup

```powershell
cd D:\BroPilot\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create `backend\.env`:

```powershell
notepad .env
```

Add:

```text
OPENAI_API_KEY=sk-your-key-here
```

Optional:

```text
BROPILOT_OPENAI_AGENT_MODEL=gpt-5.6-terra
BROPILOT_OPS_AGENT_MODEL=gpt-5.6-terra
BROPILOT_MEMO_AGENT_MODEL=gpt-5.6-terra
```

Start the backend:

```powershell
cd D:\BroPilot\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Backend URL:

```text
http://127.0.0.1:8000
```

## 3. Frontend Setup

Open a second PowerShell window:

```powershell
cd D:\BroPilot\frontend
npm install
npm run dev
```

Frontend URL:

```text
http://localhost:3000
```

## 4. OCR Setup

Ops Pilot image OCR needs Tesseract installed at:

```text
D:\BroPilot\tools\Tesseract-OCR\tesseract.exe
```

Install Tesseract into:

```text
D:\BroPilot\tools\Tesseract-OCR
```

Check installation:

```powershell
cd D:\BroPilot
.\tools\Tesseract-OCR\tesseract.exe --version
```

Python OCR dependencies are installed from `backend\requirements.txt`:

```text
pillow
pytesseract
```

## 5. Code Pilot Demo Repo

Reset the local demo repo:

```powershell
cd D:\BroPilot
powershell -ExecutionPolicy Bypass -File .\scripts\reset-demo.ps1
```

Use this repo path in Code Pilot:

```text
D:\bropilot-demo
```

## 6. Validation Commands

Frontend build:

```powershell
cd D:\BroPilot\frontend
npm run build
```

Backend syntax check:

```powershell
cd D:\BroPilot\backend
.\.venv\Scripts\python.exe -m py_compile app\main.py
```

