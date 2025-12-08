Here is the comprehensive guide for your dynamic tank simulation, covering architecture, variables, setup, and control.

## 🏗️ High-Level Architecture

The system uses a **decoupled architecture** based on the Publish/Subscribe messaging pattern, with **MQTT** serving as the central nervous system.

1.  **MQTT Broker (Central Hub):** The broker acts as a non-sentient router. It receives messages from publishers (e.g., control panel) and instantly forwards them to all relevant subscribers (e.g., your Python simulation).
2.  **Simulation Client (`mqtt_sim_client.py`):** This is the core logic. It runs the physics model, **subscribes** to control topics, updates its parameters upon receiving a message, runs a $1$-second ODE segment, and **publishes** the resulting volume.
3.  **Controller/Publisher (External Client/Node-RED):** This external system publishes the desired control values to the broker topics (e.g., turning the pump off).

This structure ensures that the simulation runs continuously and synchronously (1 real second = 1 simulation second), responding dynamically to any input received via the broker.

-----

## 📊 Explanation of Variables

The variables are categorized based on their stability and source.

### 1\. Hardcoded System Constants (In `tank_model.py`)

These define the fixed physical limits of the system and do **not** change during the simulation run.

| Variable | Value (Example) | Units | Description |
| :--- | :--- | :--- | :--- |
| **$C_{\text{TOTAL}}$** | $20000.0$ | Liters (L) | Total capacity of both tanks combined. |
| **$R_{\text{PUMP}}$** | $60.0$ | L/min | Fixed maximum continuous flow rate of a single pump. |

### 2\. Dynamic Operational Variables (Global in `mqtt_sim_client.py`)

These variables define the current state and controls. They are updated asynchronously by the MQTT `on_message` callback.

| Variable | Default Value | Topic Source | Description |
| :--- | :--- | :--- | :--- |
| **$V_{\text{initial}}$** (`current_volume`) | $0.0$ | N/A | Current volume in the tanks (state variable). |
| **$t_{\text{elapsed}}$** (`sim_time_elapsed`) | $0.0$ | N/A | Total time the simulation has run (state variable). |
| **$R_{\text{fab}}$** | $100.0$ | `lift_station/fab_outflow` | The current maximum outflow rate from the source/fab pipe. (L/min) |
| **$N_{\text{active}}$** | $2.0$ | `lift_station/active_tanks` | Number of valves currently open (1.0 or 2.0). |
| **$S_{\text{pump}}$** | $1.0$ | `lift_station/pump_status` | Status of the pump (0.0 = OFF, 1.0 = ON). |
| **$t_{\text{step}}$** (`SIMULATION_SEGMENT_DURATION`) | $1/60$ | N/A | The fixed duration of each solver step ($1$ second, converted to minutes). |

-----

## 💻 Environment Setup

### 1\. Install Prerequisites

Ensure you have **Python 3.x** and an **MQTT Broker** installed and running (e.g., Mosquitto on `localhost:1883`).

### 2\. Create and Activate Virtual Environment

It's highly recommended to use a virtual environment (`venv`).

```bash
# Create the environment
python3 -m venv tank_sim_env

# Activate the environment (Linux/macOS)
source tank_sim_env/bin/activate

# For Windows (Command Prompt):
# tank_sim_env\Scripts\activate.bat 
```

### 3\. Install Dependencies

With the environment active, install the necessary libraries:

```bash
pip install numpy scipy paho-mqtt
```

-----

## 💾 File Setup

You must have two Python files in the same directory:

### 1\. `tank_model.py` (Model Logic)

This file contains the core math. **Crucially, remove the hardcoded `R_FAB = 100.0` line** so the client script can manage it dynamically.

### 2\. `mqtt_sim_client.py` (Simulation Controller)

This file contains the MQTT client, threading, and the main loop. Use the final, corrected code provided previously.

-----

## ▶️ Running the Simulation

1.  **Verify Broker:** Ensure your Mosquitto broker is running.
2.  **Start Client:** Run the main simulation controller script. It will connect to the broker and start the simulation loop.

<!-- end list -->

```bash
python mqtt_sim_client.py
```

The console output will show the synchronized state updates every second:

```
--- Simulation Controller Started (1-second step size) ---
Connected to MQTT Broker!
[T: 1 sec | 0.02 min] | V: 3 L | R_in: 200 | R_out: 60 | Status: OK
[T: 2 sec | 0.03 min] | V: 5 L | R_in: 200 | R_out: 60 | Status: OK
...
```

-----

## 🕹️ Controlling the Simulation

Control is achieved by publishing messages to the control topics using an external MQTT client (e.g., Mosquitto CLI or a Node-RED dashboard).

### Example Control Commands

Use a separate terminal window to publish these commands:

#### 1\. Stop the Pump (Simulate a control action)

This sets the net flow from $140 \text{ L/min}$ to $200 \text{ L/min}$, accelerating the filling process.

```bash
mosquitto_pub -h localhost -t lift_station/pump_status -m "0.0"
```

#### 2\. Change Fab Outflow (Simulate a source change)

This sets the max fab flow to $150 \text{ L/min}$, increasing the gross inflow to $300 \text{ L/min}$ (since $N_{\text{active}}=2$).

```bash
mosquitto_pub -h localhost -t lift_station/fab_outflow -m "150.0"
```

#### 3\. Close One Valve (Simulate a tank isolation)

This reduces the total inflow capability. Assuming the pump is ON ($R_{\text{out}}=60$), the net flow becomes $100 \text{ L/min} - 60 \text{ L/min} = 40 \text{ L/min}$.

```bash
mosquitto_pub -h localhost -t lift_station/active_tanks -m "1.0"
```