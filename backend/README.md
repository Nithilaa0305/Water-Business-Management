# Wholesale Billing System - Backend API

FastAPI backend server for the wholesale billing management system.

## Setup Instructions

1. **Navigate to the backend folder**:
   ```bash
   cd backend
   ```

2. **Create a virtual environment**:
   ```bash
   py -m venv venv
   # Or: python -m venv venv
   ```

3. **Activate the virtual environment**:
   - Windows (PowerShell):
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   - Windows (Command Prompt):
     ```cmd
     venv\Scripts\activate.bat
     ```

4. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Configure environment variables**:
   - Copy `.env.example` to `.env`:
     ```powershell
     Copy-Item .env.example .env
     ```
   - Update `DATABASE_URL` with your PostgreSQL password and database name.

6. **Run the API server**:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

7. **Interactive API Documentation (Swagger)**:
   - Visit [http://localhost:8000/docs](http://localhost:8000/docs) in your browser.
