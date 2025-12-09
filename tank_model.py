"""Tank system physical model.

This module defines the differential equation model for a dual-tank lift station system.
The model calculates volume changes based on inflow from fab facilities and
outflow from pumping equipment, with overflow handling when tanks reach capacity.

The model is designed to be driven by an external controller that manages dynamic
parameters such as active tank count and pump status.
"""

import numpy as np
from scipy.integrate import solve_ivp

# Physical system constants - these represent fixed infrastructure characteristics
INDIVIDUAL_TANK_CAPACITY_LITERS = 10000.0
TOTAL_SYSTEM_CAPACITY_LITERS = INDIVIDUAL_TANK_CAPACITY_LITERS * 2.0
PUMP_FLOW_RATE_LITERS_PER_MIN = 60.0

def calculate_volume_change_rate(time: float, 
                                  volume: np.ndarray, 
                                  fab_outflow_rate: float, 
                                  pump_flow_rate: float, 
                                  active_tank_count: float, 
                                  pump_status: float, 
                                  total_capacity: float) -> np.ndarray:
    """Calculate the rate of change of total tank volume (dV/dt).
    
    This function implements the differential equation for the tank system.
    The net flow rate is the difference between inflow and outflow, unless
    the system is at capacity with positive net flow (overflow condition).
    
    Args:
        time: Current simulation time in minutes (required by solver, unused in calculation)
        volume: Array containing current total volume in liters
        fab_outflow_rate: Flow rate from fab facility per tank (L/min)
        pump_flow_rate: Maximum flow rate of a single pump (L/min)
        active_tank_count: Number of tanks currently receiving inflow (0-2)
        pump_status: Pump operational state (0=off, 1=on)
        total_capacity: Maximum combined capacity of both tanks (L)
        
    Returns:
        Array containing the volume change rate (dV/dt) in L/min
    """
    
    total_inflow_rate = fab_outflow_rate * active_tank_count
    total_outflow_rate = pump_flow_rate * pump_status
    net_flow_rate = total_inflow_rate - total_outflow_rate

    # Prevent volume from exceeding capacity during overflow conditions
    # When tanks are full and receiving net inflow, volume cannot increase further
    if volume[0] >= total_capacity and net_flow_rate > 0:
        return np.array([0.0])
    
    return np.array([net_flow_rate])

def detect_capacity_reached(time: float, volume: np.ndarray, *args) -> float:
    """Detect when tank volume reaches maximum capacity.
    
    This event function is used by the ODE solver to precisely identify
    when the system reaches its capacity limit. The solver will terminate
    integration when this function returns zero.
    
    Args:
        time: Current simulation time (unused)
        volume: Array containing current volume
        *args: Additional parameters passed by solver (unused)
        
    Returns:
        Difference between current volume and total capacity.
        Returns 0 when capacity is reached.
    """
    return volume[0] - TOTAL_SYSTEM_CAPACITY_LITERS

# Configure event to stop solver when capacity is reached during filling
detect_capacity_reached.terminal = True
detect_capacity_reached.direction = 1  # Only trigger when volume is increasing

def run_test_scenario():
    """Run a test scenario to validate the tank model behavior.
    
    This test demonstrates the model's ability to simulate tank filling and
    overflow detection. The scenario uses fixed control parameters to verify
    that the system correctly calculates volume changes and detects when
    capacity is reached.
    
    Test parameters:
    - Initial volume: 0 L (empty tanks)
    - Both tanks active (receiving inflow)
    - Pump operating continuously
    - Net positive flow causes gradual filling until capacity
    """
    
    # Test scenario configuration
    FAB_OUTFLOW_RATE = 100.0  # L/min per tank
    initial_volume = 0.0  # Start with empty tanks
    active_tank_count = 2.0  # Both tanks receiving inflow
    pump_status = 1.0  # Pump operating
    
    total_inflow = FAB_OUTFLOW_RATE * active_tank_count
    total_outflow = PUMP_FLOW_RATE_LITERS_PER_MIN * pump_status
    
    print(f"--- Running Test Scenario: Inflow={total_inflow:.1f} L/min, Outflow={total_outflow:.1f} L/min ---")
    
    simulation_start_time = 0
    simulation_end_time = 300  # 5 hours in minutes
    time_span = [simulation_start_time, simulation_end_time]
    
    # Generate output points every 10 minutes
    time_evaluation_points = np.linspace(time_span[0], time_span[1], 31)

    model_parameters = (FAB_OUTFLOW_RATE, PUMP_FLOW_RATE_LITERS_PER_MIN, 
                       active_tank_count, pump_status, TOTAL_SYSTEM_CAPACITY_LITERS)

    result = solve_ivp(
        calculate_volume_change_rate, 
        t_span=time_span, 
        y0=np.array([initial_volume]), 
        t_eval=time_evaluation_points,
        events=detect_capacity_reached, 
        args=model_parameters
    )
    
    capacity_reached_time = 0.0
    
    # Check if capacity was reached during simulation
    if result.t_events[0].size > 0:
        capacity_reached_time = result.t_events[0][0] 
        
    print("\nSimulation Results (Volume over Time):")
    print("Time (min) | Volume (L) | Status")
    print("-" * 35)
    
    for time_point, volume_value in zip(result.t, result.y[0]):
        status = "Filling"
        
        if capacity_reached_time > 0 and time_point >= capacity_reached_time:
            status = "Overflowing"
            volume_value = TOTAL_SYSTEM_CAPACITY_LITERS
        
        print(f"{time_point:10.2f} | {volume_value:10.2f} | {status}")

    if capacity_reached_time > 0:
        overflow_rate = (FAB_OUTFLOW_RATE * active_tank_count) - (PUMP_FLOW_RATE_LITERS_PER_MIN * pump_status)
        print(f"\n SUCCESS: Tank capacity reached at t = {capacity_reached_time:.2f} minutes.")
        print(f"   Steady-state overflow rate into pit: {overflow_rate:.1f} L/min.")
    else:
        print("\n FAILED: Tank capacity was not reached during the simulation.")


if __name__ == "__main__":
    run_test_scenario()