# =============================================================================
# SDC Timing Constraints — Ariane-136 (CVA6)
# Target: NanGate45, 500 MHz (2.0 ns period)
# =============================================================================

# --- Primary Clock Definition ---
create_clock -name clk_i -period 2.0 [get_ports clk_i]

# --- Clock Uncertainty ---
# Accounts for jitter, skew, and OCV
set_clock_uncertainty -setup 0.15 [get_clocks clk_i]
set_clock_uncertainty -hold  0.05 [get_clocks clk_i]

# --- Clock Transition ---
set_clock_transition -max 0.10 [get_clocks clk_i]
set_clock_transition -min 0.05 [get_clocks clk_i]

# --- False Path ---
set_false_path -from [get_ports rst_ni]

# --- Input Delay ---
# Assume 40% of clock period for input setup
set_input_delay  -max 0.80 -clock clk_i [all_inputs]
set_input_delay  -min 0.10 -clock clk_i [all_inputs]

# --- Output Delay ---
# Assume 40% of clock period for output setup
set_output_delay -max 0.80 -clock clk_i [all_outputs]
set_output_delay -min 0.10 -clock clk_i [all_outputs]

# --- Drive Strength / Load ---
# TODO: DESIGN_FILES — Update with actual port-specific drive/load values
set_driving_cell -lib_cell BUF_X4 -pin Z [all_inputs]
set_load 0.05 [all_outputs]

# --- False Paths (if any) ---
# TODO: DESIGN_FILES — Add design-specific false paths, multicycle paths

# --- Design Rule Constraints ---
set_max_fanout 20 [current_design]
set_max_transition 0.20 [current_design]

# =============================================================================
# End of SDC
# =============================================================================
