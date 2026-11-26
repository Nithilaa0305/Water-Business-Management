# Developer Build & Windows Packaging Guide

## 1. Prerequisites
- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Python**: 3.11, 3.12, or 3.13 64-bit
- **Inno Setup**: Version 6.x (for generating `WaterBusinessManager_Setup.exe`)

## 2. Setting Up the Development Environment
```powershell
# Navigate to the project directory
cd d:\stock

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install runtime and dev dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## 3. Running Automated Tests
```powershell
# Run the complete test suite (unit, integration, and UI smoke tests)
pytest -v
```

## 4. Running the Application in Development
```powershell
python main.py
```

## 5. Building the Standalone Windows Executable
Execute the provided build script:
```powershell
.\packaging\build_windows.ps1
```
Or with command prompt:
```cmd
packaging\build_windows.bat
```
The standalone application will be assembled into:
`dist\WaterBusinessManager\WaterBusinessManager.exe`

## 6. Creating the Windows Installer with Inno Setup
1. Open `packaging\installer.iss` in Inno Setup Compiler.
2. Click **Build -> Compile** (or run `iscc packaging\installer.iss` from command line).
3. The setup installer will be generated at:
   `dist\WaterBusinessManager_Setup.exe`
