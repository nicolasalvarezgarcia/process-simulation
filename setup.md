# Setup Instructions

## Create Virtual Environment

```powershell
python -m venv .venv
```

## Activate Virtual Environment

```powershell
.\.venv\Scripts\Activate.ps1
```

*Note: If you encounter an execution policy error, run:*
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

## Install Dependencies

```powershell
pip install -r requirements.txt
```

## Run the Simulation

```powershell
python mqtt_sim_client.py
```

**Prerequisites:**
- Python 3.x installed
- MQTT broker running on `localhost:1883` (e.g., Mosquitto)

## Deactivate Virtual Environment

```powershell
deactivate
```
