import numpy as np
from scipy.integrate import solve_ivp

# --- 1. System Constants (Parameters) ---
C_TANK = 10000.0  # liters
C_TOTAL = C_TANK * 2.0  # Total capacity (20,000 L)
#R_FAB = 100.0  # Fab outflow rate (L/min) - Handled by the client
R_PUMP = 60.0  # Single pump continuous rate (L/min)

# --- 2. Model Function (The Differential Equation) ---

def ode_function(t, V, R_fab, R_pump, N_active, S_pump, C_total):
    """
    Calculates dV/dt (Rate of change of total volume).
    
    Args:
        t (float): Time (required by solve_ivp but unused here).
        V (ndarray): Current total volume [V_total].
        R_fab, R_pump, etc.: System and control parameters.
        
    Returns:
        ndarray: The rate of change of volume [dV/dt].
    """
    
    # Calculate current inflow and outflow based on control inputs
    R_in = R_fab * N_active
    R_out_pump = R_pump * S_pump
    net_flow = R_in - R_out_pump

    # --- Overflow Condition ---
    # If tanks are full AND flow is positive (i.e., overflowing),
    # the volume change rate must be zero (dV/dt = 0).
    if V[0] >= C_total and net_flow > 0:
        return np.array([0.0])
    
    # Otherwise, return the net flow rate
    return np.array([net_flow])

# --- 3. Event Function (Stops integration exactly at the capacity limit) ---

def overflow_event(t, V, *args):
    """Event function to detect when volume hits total capacity (20,000 L)."""
    # The solver terminates when this function returns 0
    return V[0] - C_TOTAL

# Set termination criteria for the event
overflow_event.terminal = True
overflow_event.direction = 1  # Only trigger when volume is increasing

# --- 4. Testing Function ---

def run_test_scenario():
    """
    Simulates a scenario where the tanks fill up and overflow.
    Scenario:
    1. Start empty (0 L).
    2. Both valves open (N_active=2) -> R_in = 200 L/min.
    3. Pump is ON (S_pump=1) -> R_out = 60 L/min.
    4. Net flow: 140 L/min. T_fill approx 142.86 minutes.
    """
    
    print(f"--- Running Test Scenario: R_in={R_FAB*2:.1f} L/min, R_out={R_PUMP*1:.1f} L/min ---")
    
    # Initial Conditions
    V_initial = 0.0
    
    # Control Inputs for this scenario (fixed for the run)
    N_active = 2.0 
    S_pump = 1.0   
    
    # Simulation Time Span: 0 to 300 minutes (5 hours)
    t_span = [0, 300]
    
    # Time points for output (e.g., every 10 minutes)
    t_eval = np.linspace(t_span[0], t_span[1], 31)

    # All parameters passed to the ODE and Event functions
    params = (R_FAB, R_PUMP, N_active, S_pump, C_TOTAL)

    # Run the solver
    result = solve_ivp(
        ode_function, 
        t_span=t_span, 
        y0=np.array([V_initial]), 
        t_eval=t_eval,
        events=overflow_event, 
        args=params
    )

    # --- Analysis and Output (FIXED SECTION) ---
    
    time_reached = 0.0
    
    # Check if the overflow event was triggered by the solver
    # result.t_events[0] contains the array of times when the overflow_event was triggered
    if result.t_events[0].size > 0:
        # Get the very first time the capacity was hit
        time_reached = result.t_events[0][0] 
        
    print("\nSimulation Results (Volume over Time):")
    print("Time (min) | Volume (L) | Status")
    print("-" * 35)
    
    # Loop over the calculated time points
    for t, V in zip(result.t, result.y[0]):
        status = "Filling"
        
        # Use the accurate time_reached variable to determine the status
        if time_reached > 0 and t >= time_reached:
            status = "Overflowing"
            # Ensure the volume is capped at the capacity
            V = C_TOTAL 
        
        print(f"{t:10.2f} | {V:10.2f} | {status}")

    # Final Summary Check
    if time_reached > 0:
        R_pit = (R_FAB * N_active) - (R_PUMP * S_pump)
        print(f"\n✅ SUCCESS: Tank capacity reached at t = {time_reached:.2f} minutes.")
        print(f"   Steady-state overflow rate into pit: {R_pit:.1f} L/min.")
    else:
        print("\n❌ FAILED: Tank capacity was not reached during the simulation.")


if __name__ == "__main__":
    run_test_scenario()