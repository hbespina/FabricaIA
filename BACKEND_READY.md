# 🚀 Backend API - PRODUCTION READY

**Status: FULLY OPERATIONAL** ✅

## Server Information

- **URL**: http://127.0.0.1:8000
- **Framework**: Flask 3.1.3
- **Python**: 3.13.3
- **Mode**: Production (Debug OFF)

## Endpoints

### 1. Health Check
```
GET /health
```
**Purpose**: Verify server is running  
**Response**: 200 OK with JSON status

**Example**:
```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

---

### 2. Collect Data
```
POST /collect
Content-Type: application/json

{
  "hostname": "192.168.1.100",
  "username": "admin",
  "password": "yourpassword",
  "port": 22
}
```

**Purpose**: SSH connection to remote server and collect system inventory  
**Response**: 200 OK with collected data or error code  
**Error Codes**:
- `400`: Invalid/missing parameters
- `401`: Authentication failed
- `503`: Connection timeout

**Example**:
```powershell
$payload = @{
  hostname = "your-server.com"
  username = "admin"
  password = "pass123"
  port = 22
} | ConvertTo-Json

Invoke-RestMethod -Uri http://127.0.0.1:8000/collect `
  -Method POST -ContentType application/json -Body $payload
```

---

### 3. Analyze Data
```
POST /analyze
Content-Type: application/json

{
  "raw_data": "HOSTNAME: web-server-01\nKERNEL: 4.19\nOS: Ubuntu..."
}
```

**Purpose**: Analyze collected system data and generate recommendations  
**Response**: 200 OK with analysis results  
**Error Codes**:
- `400`: Missing or too short raw_data

**Example**:
```powershell
$analysis = @{
  raw_data = "HOSTNAME: server KERNEL: 4.19 OS: Ubuntu JAVA: 11 MYSQL: yes"
} | ConvertTo-Json

Invoke-RestMethod -Uri http://127.0.0.1:8000/analyze `
  -Method POST -ContentType application/json -Body $analysis
```

---

## How to Use with Frontend

1. **Start Backend** (if not running):
   ```powershell
   cd c:\Users\hberrioe\Fabrica
   py backend.py
   ```

2. **Open Frontend**:
   - Open `index.html` in your browser
   - Or: `start "" index.html`

3. **Use Options**:
   - **SSH Collect**: Enter server details → Click "Conectar" → Get raw data
   - **Paste Data**: Paste pre-collected data → Click "Iniciar Análisis Forense"
   - **Dashboard**: View architecture, risks, financial impact, migration plan

---

## Backend Features

✅ SSH Collection (via Paramiko)  
✅ Input Validation (hostname, username, length)  
✅ Error Handling (timeouts, auth failures, network errors)  
✅ Request Logging (timestamps for all operations)  
✅ CORS Support (frontend can communicate)  
✅ Heuristic Analysis (fallback when Bedrock unavailable)  

---

## Recent Fixes

- ✅ Fixed backend.py syntax corruption (mixed Python/Bash code)
- ✅ All 3 endpoints tested and working
- ✅ Proper error handling for connection timeouts
- ✅ Input validation prevents invalid requests

---

## For Production Use

To use a production WSGI server instead of Flask development server:

```powershell
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 backend:app
```

---

**Last Updated**: 2026-03-27  
**Version**: 2.0  
**Status**: ✅ Ready for testing
