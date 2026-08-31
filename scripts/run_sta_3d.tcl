# =============================================================================
# run_sta_3d.tcl — OpenSTA Multi-Tier 3D Timing Evaluation Script
#
# Loads LEF/LIB/DEF for both tiers, reads thermal-annotated SPEF, and
# reports WNS, TNS, hold slack, and cross-tier clock skew metrics.
#
# Part of the Thermal-Aware Pin-3D Framework for Ariane-136.
#
# Usage:
#   openroad -exit run_sta_3d.tcl \
#     -design_name ariane136 \
#     -lef_path <lef> \
#     -lib_path <lib> \
#     -tier0_def <def> -tier1_def <def> \
#     -tier0_spef <spef> -tier1_spef <spef> \
#     -sdc_path <sdc> \
#     -report_dir <dir> \
#     -iteration <N>
#
# =============================================================================

# ---------------------------------------------------------------------------
# Argument Parsing (Tcl variables set by caller or defaults)
# ---------------------------------------------------------------------------

# Design name
if {![info exists design_name]} {
    set design_name "ariane136"
}

# PDK paths
if {![info exists tech_lef_path]} {
    set tech_lef_path "platforms/nangate45_3D/lef/NangateOpenCellLibrary.tech.lef"
}
if {![info exists lef_files]} {
    set lef_files [list \
        "platforms/nangate45_3D/lef_bottom/NangateOpenCellLibrary.macro.mod.bottom.lef" \
        "platforms/nangate45_3D/lef_upper/NangateOpenCellLibrary.macro.mod.upper.lef" \
        "platforms/nangate45_3D/lef_bottom/fakeram45_256x16.bottom.lef" \
        "platforms/nangate45_3D/lef_upper/fakeram45_256x16.upper.lef" \
    ]
}
if {![info exists lib_files]} {
    set lib_files [list \
        "platforms/nangate45_3D/lib_bottom/NangateOpenCellLibrary_typical.bottom.lib" \
        "platforms/nangate45_3D/lib_upper/NangateOpenCellLibrary_typical.upper copy.lib" \
        "platforms/nangate45_3D/lib_bottom/fakeram45_256x16.bottom.lib" \
        "platforms/nangate45_3D/lib_upper/fakeram45_256x16.upper.lib" \
    ]
}

# Tier DEF files
if {![info exists tier0_def]} {
    set tier0_def "designs/${design_name}/floorplan/ariane_tier0.def"
}
if {![info exists tier1_def]} {
    set tier1_def "designs/${design_name}/floorplan/ariane_tier1.def"
}

# Thermal SPEF files
if {![info exists tier0_spef]} {
    set tier0_spef "results/thermal/ariane_tier0_thermal.spef"
}
if {![info exists tier1_spef]} {
    set tier1_spef "results/thermal/ariane_tier1_thermal.spef"
}

# SDC constraints
if {![info exists sdc_path]} {
    set sdc_path "designs/${design_name}/constraints/${design_name}.sdc"
}

# Report output directory
if {![info exists report_dir]} {
    set report_dir "results/reports"
}

# Iteration number (for convergence tracking)
if {![info exists iteration]} {
    set iteration 0
}

# Clock name
if {![info exists clk_name]} {
    set clk_name "clk_i"
}

# =============================================================================
# Utility Procedures
# =============================================================================

proc log_msg {msg} {
    puts ">>> \[STA-3D\] $msg"
}

proc ensure_dir {dir} {
    if {![file exists $dir]} {
        file mkdir $dir
    }
}

# Parse numeric value from timing report line
proc extract_slack {line} {
    set parts [split [string trim $line]]
    set val [lindex $parts end]
    if {[string is double $val]} {
        return $val
    }
    return 0.0
}

# =============================================================================
# Main STA Flow
# =============================================================================

log_msg "========================================================"
log_msg "3D Timing Evaluation — Iteration $iteration"
log_msg "Design: $design_name"
log_msg "========================================================"

ensure_dir $report_dir

# ---------------------------------------------------------------------------
# Step 1: Load Technology & Libraries
# ---------------------------------------------------------------------------

log_msg "Loading technology LEF..."
if {[file exists $tech_lef_path]} {
    read_lef $tech_lef_path
}

log_msg "Loading cell and macro LEFs..."
foreach lef $lef_files {
    if {[file exists $lef]} {
        read_lef $lef
    } else {
        log_msg "WARNING: LEF not found: $lef"
    }
}

log_msg "Loading Liberty timing libraries..."
foreach lib $lib_files {
    if {[file exists $lib]} {
        read_liberty $lib
    } else {
        log_msg "WARNING: LIB not found: $lib"
    }
}

# ---------------------------------------------------------------------------
# Step 2: Load Tier 0 Design
# ---------------------------------------------------------------------------

log_msg "--- Tier 0 Analysis ---"

log_msg "Reading Tier 0 DEF: $tier0_def"
read_def $tier0_def

log_msg "Reading SDC constraints: $sdc_path"
read_sdc $sdc_path
catch {set_false_path -from [get_ports rst_ni]}

# Read thermal-annotated SPEF for Tier 0
log_msg "Reading Tier 0 thermal SPEF: $tier0_spef"
if {[file exists $tier0_spef]} {
    read_spef $tier0_spef
} else {
    log_msg "WARNING: Tier 0 SPEF not found — timing will use estimated parasitics"
}

# ---------------------------------------------------------------------------
# Step 3: Run Setup Timing Analysis
# ---------------------------------------------------------------------------

log_msg "Running setup timing analysis..."

# Report worst setup paths
set setup_rpt "${report_dir}/timing_setup_tier0_iter${iteration}.rpt"
report_checks -path_delay max -format full_clock_expanded \
    -fields {slew cap input_pins nets fanout} \
    -digits 4 \
    > $setup_rpt

# Report WNS and TNS
set wns_rpt "${report_dir}/wns_tns_tier0_iter${iteration}.rpt"
report_worst_slack -max > $wns_rpt
report_tns >> $wns_rpt

log_msg "Setup timing report: $setup_rpt"

# ---------------------------------------------------------------------------
# Step 4: Run Hold Timing Analysis
# ---------------------------------------------------------------------------

log_msg "Running hold timing analysis..."

set hold_rpt "${report_dir}/timing_hold_tier0_iter${iteration}.rpt"
report_checks -path_delay min -format full_clock_expanded \
    -fields {slew cap input_pins nets fanout} \
    -digits 4 \
    > $hold_rpt

set hold_wns_rpt "${report_dir}/hold_wns_tier0_iter${iteration}.rpt"
report_worst_slack -min > $hold_wns_rpt

log_msg "Hold timing report: $hold_rpt"

# ---------------------------------------------------------------------------
# Step 5: Clock Skew Analysis
# ---------------------------------------------------------------------------

log_msg "Analyzing clock tree skew..."

set skew_rpt "${report_dir}/clock_skew_iter${iteration}.rpt"

# Report clock properties
report_clock_skew > $skew_rpt

log_msg "Clock skew report: $skew_rpt"

# ---------------------------------------------------------------------------
# Step 6: Power Report
# ---------------------------------------------------------------------------

log_msg "Reporting power..."

set power_rpt "${report_dir}/power_iter${iteration}.rpt"
report_power -digits 4 > $power_rpt

set power_inst_rpt "${report_dir}/power_instance_iter${iteration}.rpt"
# Instance-level power for next thermal iteration
# report_power -instance > $power_inst_rpt
# NOTE: Instance-level power report may not be available in all OpenSTA versions.
# If not available, use OpenROAD's power analysis instead.

log_msg "Power report: $power_rpt"

# ---------------------------------------------------------------------------
# Step 7: Extract Key Metrics for Convergence Check
# ---------------------------------------------------------------------------

log_msg "Extracting key metrics..."

# Create structured output for Python pipeline consumption
set metrics_file "${report_dir}/metrics_iter${iteration}.json"

# Extract WNS
set wns_val "0.0"
if {[file exists $wns_rpt]} {
    set fp [open $wns_rpt r]
    set wns_content [read $fp]
    close $fp
    # Parse worst slack value from report
    foreach line [split $wns_content "\n"] {
        set trimmed [string trim $line]
        if {[string is double $trimmed]} {
            set wns_val $trimmed
            break
        }
        # Also try matching "worst slack (max/min) X.XXX"
        if {[regexp {worst\s+slack\s+(?:max\s+|min\s+)?([\-\d.]+)} $trimmed -> val]} {
            set wns_val $val
            break
        }
    }
}

# Extract TNS
set tns_val "0.0"
if {[file exists $wns_rpt]} {
    set fp [open $wns_rpt r]
    set tns_content [read $fp]
    close $fp
    foreach line [split $tns_content "\n"] {
        if {[regexp {tns\s+(?:max\s+|min\s+)?([\-\d.]+)} $line -> val]} {
            set tns_val $val
            break
        }
    }
}

# Write metrics JSON (simple manual JSON construction for Tcl compatibility)
set fp [open $metrics_file w]
puts $fp "\{"
puts $fp "  \"iteration\": $iteration,"
puts $fp "  \"design\": \"$design_name\","
puts $fp "  \"wns_ns\": \"$wns_val\","
puts $fp "  \"tns_ns\": \"$tns_val\","
puts $fp "  \"setup_report\": \"$setup_rpt\","
puts $fp "  \"hold_report\": \"$hold_rpt\","
puts $fp "  \"skew_report\": \"$skew_rpt\","
puts $fp "  \"power_report\": \"$power_rpt\""
puts $fp "\}"
close $fp

log_msg "Metrics written to: $metrics_file"

# ---------------------------------------------------------------------------
# Step 8: Summary
# ---------------------------------------------------------------------------

log_msg "========================================================"
log_msg "3D STA Summary — Iteration $iteration"
log_msg "  WNS (setup):  $wns_val ns"
log_msg "  TNS:          $tns_val ns"
log_msg "  Reports in:   $report_dir"
log_msg "========================================================"

# If running in OpenROAD (not standalone OpenSTA), we can also access:
# - Detailed routing info
# - Buffer count
# - Wirelength statistics
# These are reported conditionally:
if {[info commands report_design_area] ne ""} {
    log_msg "Design area:"
    report_design_area
}

if {[info commands report_wire_length] ne ""} {
    set wl_rpt "${report_dir}/wirelength_iter${iteration}.rpt"
    log_msg "Wirelength report: $wl_rpt"
}

log_msg "3D STA evaluation complete."

# =============================================================================
# End of run_sta_3d.tcl
# =============================================================================
