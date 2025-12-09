"""MQTT-based tank simulation client.

This module implements a real-time simulation controller for a dual-tank lift station.
It uses MQTT for dynamic control inputs and data publishing, running the physical model
in 1-second segments to maintain real-time synchronization (1 sim second = 1 real second).

The simulation subscribes to control topics for dynamic parameter updates and publishes
the current tank volume at each time step. This architecture allows external systems
to control the simulation in real-time via MQTT messaging.
"""

import numpy as np
import time
import threading
import sys
from typing import Any
from paho.mqtt import client as mqtt_client
from scipy.integrate import solve_ivp

from tank_model import (
    calculate_volume_change_rate,
    detect_capacity_reached,
    TOTAL_SYSTEM_CAPACITY_LITERS,
    PUMP_FLOW_RATE_LITERS_PER_MIN
)

# MQTT Broker Configuration
MQTT_BROKER_HOST = 'localhost'
MQTT_BROKER_PORT = 1883
MQTT_CLIENT_ID = f'python-simulator-{time.time()}'

# MQTT Topics - Control Inputs (subscribed)
TOPIC_ACTIVE_TANK_COUNT = "lift_station/active_tanks"
TOPIC_PUMP_OPERATIONAL_STATUS = "lift_station/pump_status"
TOPIC_FAB_OUTFLOW_RATE = "lift_station/fab_outflow"

# MQTT Topics - Data Output (published)
TOPIC_CURRENT_VOLUME = "data/lift_station/current_volume" 

# Simulation State Variables
current_tank_volume_liters = 0.0
simulation_time_elapsed_minutes = 0.0
is_simulation_running = True

# Dynamic Control Parameters (updated via MQTT messages)
active_tank_count = 2.0
pump_operational_status = 1.0  # 1.0 = ON, 0.0 = OFF
fab_outflow_rate_per_tank = 100.0  # L/min

# Simulation timing configuration
SIMULATION_STEP_DURATION_MINUTES = 1.0 / 60.0  # 1 second in minutes

def handle_broker_connection(client: mqtt_client.Client, 
                            userdata: Any, 
                            flags: dict, 
                            return_code: int) -> None:
    """Handle MQTT broker connection event.
    
    This callback is triggered when the client successfully connects to the broker.
    It subscribes to all control topics to receive dynamic parameter updates.
    
    Args:
        client: The MQTT client instance
        userdata: User-defined data (unused)
        flags: Connection flags from broker
        return_code: Connection result code (0 = success)
    """
    if return_code == 0:
        print("Connected to MQTT Broker!")
        client.subscribe([
            (TOPIC_ACTIVE_TANK_COUNT, 0),
            (TOPIC_PUMP_OPERATIONAL_STATUS, 0),
            (TOPIC_FAB_OUTFLOW_RATE, 0)
        ])
    else:
        print(f"Failed to connect, return code {return_code}")

def handle_control_message(client: mqtt_client.Client, 
                          userdata: Any, 
                          message: mqtt_client.MQTTMessage) -> None:
    """Process incoming MQTT control messages.
    
    This callback updates the simulation's dynamic parameters when control
    messages are received. It handles three control topics: active tank count,
    pump status, and fab outflow rate.
    
    Args:
        client: The MQTT client instance
        userdata: User-defined data (unused)
        message: The received MQTT message containing topic and payload
    """
    global active_tank_count, pump_operational_status, fab_outflow_rate_per_tank
    global simulation_time_elapsed_minutes
    
    try:
        control_value = float(message.payload.decode())
        
        if message.topic == TOPIC_ACTIVE_TANK_COUNT:
            active_tank_count = control_value
            print(f"[{simulation_time_elapsed_minutes:.2f} min] CONTROL: Active Tanks set to {active_tank_count:.0f}")

        elif message.topic == TOPIC_PUMP_OPERATIONAL_STATUS:
            pump_operational_status = control_value
            print(f"[{simulation_time_elapsed_minutes:.2f} min] CONTROL: Pump Status set to {pump_operational_status:.0f}")
            
        elif message.topic == TOPIC_FAB_OUTFLOW_RATE:
            fab_outflow_rate_per_tank = control_value
            print(f"[{simulation_time_elapsed_minutes:.2f} min] CONTROL: Fab Outflow set to {fab_outflow_rate_per_tank:.1f} L/min")
            
    except ValueError:
        print(f"Error: Received non-numeric payload '{message.payload.decode()}' on topic {message.topic}")
    except Exception as error:
        print(f"Unexpected error processing message: {error}")

def calculate_flow_rates() -> tuple[float, float]:
    """Calculate current inflow and outflow rates based on control parameters.
    
    Returns:
        Tuple of (total_inflow_rate, total_outflow_rate) in L/min
    """
    total_inflow_rate = fab_outflow_rate_per_tank * active_tank_count
    total_outflow_rate = PUMP_FLOW_RATE_LITERS_PER_MIN * pump_operational_status
    return total_inflow_rate, total_outflow_rate


def format_status_display(elapsed_seconds: float, 
                         elapsed_minutes: float, 
                         volume: float, 
                         inflow_rate: float, 
                         outflow_rate: float) -> str:
    """Format the current simulation status for console display.
    
    Args:
        elapsed_seconds: Simulation time in seconds
        elapsed_minutes: Simulation time in minutes
        volume: Current tank volume in liters
        inflow_rate: Current total inflow rate in L/min
        outflow_rate: Current total outflow rate in L/min
        
    Returns:
        Formatted status string for display
    """
    status_indicator = 'OVERFLOW' if volume >= TOTAL_SYSTEM_CAPACITY_LITERS else 'OK'
    return (
        f"[T: {elapsed_seconds:.0f} sec | {elapsed_minutes:.2f} min] "
        f"| V: {volume:.0f} L "
        f"| R_in: {inflow_rate:.0f} | R_out: {outflow_rate:.0f} "
        f"| Status: {status_indicator}"
    )


def run_simulation_loop(mqtt_client: mqtt_client.Client) -> None:
    """Execute the main simulation control loop.
    
    This function runs the ODE solver in 1-second segments, synchronized with
    real-time. Each iteration solves the differential equation for the current
    control parameters, updates the global state, publishes results via MQTT,
    and displays status information.
    
    The loop continues until is_simulation_running is set to False.
    
    Args:
        mqtt_client: Connected MQTT client for publishing volume data
    """
    global current_tank_volume_liters, simulation_time_elapsed_minutes
    global active_tank_count, pump_operational_status, fab_outflow_rate_per_tank
    global is_simulation_running

    print("--- Simulation Controller Started (1-second step size) ---")
    
    detect_capacity_reached.terminal = True
    detect_capacity_reached.direction = 1

    while is_simulation_running:
        time.sleep(1)  # Synchronize with real-time (1 second pause)
        
        segment_start_time = simulation_time_elapsed_minutes
        segment_end_time = segment_start_time + SIMULATION_STEP_DURATION_MINUTES
        
        model_parameters = (
            fab_outflow_rate_per_tank,
            PUMP_FLOW_RATE_LITERS_PER_MIN,
            active_tank_count,
            pump_operational_status,
            TOTAL_SYSTEM_CAPACITY_LITERS
        )

        try:
            solver_result = solve_ivp(
                calculate_volume_change_rate,
                t_span=[segment_start_time, segment_end_time],
                y0=np.array([current_tank_volume_liters]),
                events=detect_capacity_reached,
                args=model_parameters
            )
        except Exception as solver_error:
            print(f"\n[ERROR] Solver failed: {solver_error}")
            is_simulation_running = False
            break

        if solver_result.t.size > 0:
            simulation_time_elapsed_minutes = solver_result.t[-1]
            current_tank_volume_liters = solver_result.y[0][-1]
        
        # Ensure volume doesn't exceed capacity in reporting
        if current_tank_volume_liters > TOTAL_SYSTEM_CAPACITY_LITERS:
            current_tank_volume_liters = TOTAL_SYSTEM_CAPACITY_LITERS
            
        total_inflow, total_outflow = calculate_flow_rates()
        
        # Publish current volume to MQTT
        volume_payload = f"{current_tank_volume_liters:.2f}"
        mqtt_client.publish(TOPIC_CURRENT_VOLUME, volume_payload, qos=0)
        
        # Display real-time status
        elapsed_seconds = simulation_time_elapsed_minutes * 60
        status_message = format_status_display(
            elapsed_seconds,
            simulation_time_elapsed_minutes,
            current_tank_volume_liters,
            total_inflow,
            total_outflow
        )
        sys.stdout.write(status_message + '                                        \r')
        sys.stdout.flush()

def initialize_and_run_mqtt_simulation() -> None:
    """Initialize MQTT client and start the simulation.
    
    This function sets up the MQTT client with appropriate callbacks,
    connects to the broker, and launches the simulation loop in a
    separate thread. The main thread remains active to handle MQTT
    messages and graceful shutdown on keyboard interrupt.
    """
    global is_simulation_running

    mqtt_sim_client = mqtt_client.Client(
        mqtt_client.CallbackAPIVersion.VERSION1,
        MQTT_CLIENT_ID
    )
    mqtt_sim_client.on_connect = handle_broker_connection
    mqtt_sim_client.on_message = handle_control_message

    try:
        mqtt_sim_client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    except ConnectionRefusedError:
        print(f"ERROR: Could not connect to broker at {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}.")
        print("Please ensure the MQTT broker is running.")
        return
    except Exception as connection_error:
        print(f"ERROR: Failed to connect to MQTT broker: {connection_error}")
        return

    mqtt_sim_client.loop_start()

    simulation_thread = threading.Thread(
        target=run_simulation_loop,
        args=(mqtt_sim_client,),
        daemon=True
    )
    simulation_thread.start()

    try:
        while is_simulation_running:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nSimulation stopping...")
    finally:
        is_simulation_running = False
        mqtt_sim_client.loop_stop()
        print("MQTT client and simulation stopped.")


if __name__ == '__main__':
    initialize_and_run_mqtt_simulation()