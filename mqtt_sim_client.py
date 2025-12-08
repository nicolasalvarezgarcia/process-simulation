import numpy as np
import time
import threading
import sys
from paho.mqtt import client as mqtt_client
from scipy.integrate import solve_ivp
# Import core modeling functions and fixed constants
from tank_model import ode_function, overflow_event, C_TOTAL, R_PUMP

# --- 1. MQTT Configuration ---
BROKER = 'localhost'
PORT = 1883           
CLIENT_ID = f'python-simulator-{time.time()}'

# Control Topics (Inputs)
TOPIC_ACTIVE_TANKS = "lift_station/active_tanks"
TOPIC_PUMP_STATUS = "lift_station/pump_status"
TOPIC_FAB_OUTFLOW = "lift_station/fab_outflow" 

# Data Topic (Output)
TOPIC_VOLUME_OUT = "data/lift_station/current_volume" 

# --- 2. Simulation Global State ---
current_volume = 0.0      # L (V_initial)
sim_time_elapsed = 0.0    # minutes
is_running = True

# Dynamic Control Variables (Initial/Default Values)
N_active = 2.0            # Number of active filling tanks
S_pump = 1.0              # Pump status (1.0 = ON)
R_fab = 100.0             # Fab Outflow Rate (L/min)

# Simulation Step Size
SIMULATION_SEGMENT_DURATION = 1.0 / 60.0 # 1 second converted to minutes

# --- 3. MQTT Callback Functions ---

def on_connect(client, userdata, flags, rc):
    """Callback triggered upon connecting to the broker."""
    if rc == 0:
        print("Connected to MQTT Broker!")
        # Subscribe to all three dynamic control topics
        client.subscribe([
            (TOPIC_ACTIVE_TANKS, 0), 
            (TOPIC_PUMP_STATUS, 0),
            (TOPIC_FAB_OUTFLOW, 0)
        ])
    else:
        print(f"Failed to connect, return code {rc}")

def on_message(client, userdata, msg):
    """Callback triggered when a message is received on a subscribed topic."""
    global N_active, S_pump, R_fab, sim_time_elapsed
    
    try:
        # Decode and convert payload to float
        payload = float(msg.payload.decode())
        
        if msg.topic == TOPIC_ACTIVE_TANKS:
            N_active = payload
            print(f"[{sim_time_elapsed:.2f} min] CONTROL: Active Tanks set to {N_active:.0f}")

        elif msg.topic == TOPIC_PUMP_STATUS:
            S_pump = payload
            print(f"[{sim_time_elapsed:.2f} min] CONTROL: Pump Status set to {S_pump:.0f}")
            
        elif msg.topic == TOPIC_FAB_OUTFLOW:
            R_fab = payload
            print(f"[{sim_time_elapsed:.2f} min] CONTROL: Fab Outflow (R_fab) set to {R_fab:.1f} L/min")
            
    except ValueError:
        print(f"Error: Received non-numeric payload on topic {msg.topic}")
    except Exception as e:
        print(f"An unexpected error occurred in on_message: {e}")

# --- 4. Main Simulation Controller Loop ---

def simulate_and_publish(client):
    """
    Runs the simulation by solving the ODE in 1-second segments, 
    publishing the result, and pausing for 1 second of real-time.
    """
    global current_volume, sim_time_elapsed, N_active, S_pump, R_fab, is_running

    print("--- Simulation Controller Started (1-second step size) ---")
    
    # Ensure event configuration
    overflow_event.terminal = True
    overflow_event.direction = 1

    while is_running:
        # 1. PAUSE for 1 second of real time to synchronize speed
        time.sleep(1) 

        # 2. Define segment time span (1 second duration)
        t_start = sim_time_elapsed
        t_end = t_start + SIMULATION_SEGMENT_DURATION
        
        # 3. Get current parameters (R_fab is dynamic, R_PUMP is fixed)
        params = (R_fab, R_PUMP, N_active, S_pump, C_TOTAL)

        try:
            # 4. Run the solver for the 1-second segment
            result = solve_ivp(
                ode_function, 
                t_span=[t_start, t_end], 
                y0=np.array([current_volume]), 
                events=overflow_event, 
                args=params
            )
        except Exception as e:
            print(f"\n[ERROR] Solver failed: {e}")
            is_running = False
            break

        # 5. Update Global State
        if result.t.size > 0:
            sim_time_elapsed = result.t[-1]
            current_volume = result.y[0][-1]
        
        # Handle overflow capping for volume reporting
        if current_volume > C_TOTAL:
            current_volume = C_TOTAL
            
        # 6. Publish Results and Display Status
        
        R_in = R_fab * N_active
        R_out = R_PUMP * S_pump
        
        # Publish Volume
        payload = f"{current_volume:.2f}"
        client.publish(TOPIC_VOLUME_OUT, payload, qos=0)
        
        # Display status (using sys.stdout.write for smooth updates)
        status_msg = (
            f"[T: {sim_time_elapsed*60:.0f} sec | {sim_time_elapsed:.2f} min] "
            f"| V: {current_volume:.0f} L "
            f"| R_in: {R_in:.0f} | R_out: {R_out:.0f} "
            f"| Status: {'OVERFLOW' if current_volume >= C_TOTAL else 'OK'}"
        )
        sys.stdout.write(status_msg + '                                        \r')
        sys.stdout.flush()

# --- 5. Main Execution ---

def run_mqtt_client():
    global is_running 

    client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION1, CLIENT_ID)
    client.on_connect = on_connect
    client.on_message = on_message

    # Start the non-blocking network loop
    try:
        client.connect(BROKER, PORT)
    except ConnectionRefusedError:
        print(f"ERROR: Could not connect to broker at {BROKER}:{PORT}. Is the broker running?")
        return

    client.loop_start()

    # Start the simulation loop in a separate thread
    sim_thread = threading.Thread(target=simulate_and_publish, args=(client,))
    sim_thread.daemon = True
    sim_thread.start()

    # Keep the main thread alive until user stops
    try:
        while is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nSimulation stopping...")
    finally:
        is_running = False
        client.loop_stop()
        print("MQTT client and simulation stopped.")


if __name__ == '__main__':
    run_mqtt_client()