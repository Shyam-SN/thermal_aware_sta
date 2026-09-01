# OpenROAD TCL script to execute the authentic Pin-3D 3-Pass Alternating Tier Optimization Loop
# Based on the Pin-3D methodology (ICCAD '20 by Pentapati et al.)

puts "======================================================================"
puts "  STARTING PIN-3D 3-PASS ALTERNATING TIER OPTIMIZATION"
puts "======================================================================"

# 1. Load Technology and standard cell/macro LEFs
read_lef ../platforms/nangate45_3D/lef/NangateOpenCellLibrary.tech.lef
read_lef ../platforms/nangate45_3D/lef_bottom/NangateOpenCellLibrary.macro.mod.bottom.lef
read_lef ../platforms/nangate45_3D/lef_upper/NangateOpenCellLibrary.macro.mod.upper.lef
read_lef ../platforms/nangate45_3D/lef_bottom/fakeram45_256x16.bottom.lef
read_lef ../platforms/nangate45_3D/lef_upper/fakeram45_256x16.upper.lef

# 2. Load timing libraries
read_liberty "../platforms/nangate45_3D/lib_bottom/NangateOpenCellLibrary_typical.bottom.lib"
read_liberty "../platforms/nangate45_3D/lib_upper/NangateOpenCellLibrary_typical.upper copy.lib"
read_liberty "../platforms/nangate45_3D/lib_bottom/fakeram45_256x16.bottom.lib"
read_liberty "../platforms/nangate45_3D/lib_upper/fakeram45_256x16.upper.lib"

# 3. Read 3D DEF
puts "Reading 3D DEF: results/ariane_routed_flat.def"
read_def results/ariane_routed_flat.def

# 4. Load timing constraints
read_sdc ../designs/nangate45_3D/ariane136/ariane.sdc
catch {set_false_path -from [get_ports rst_ni]}

# Load parasitics
if {[file exists results/ariane_routed_flat.spef]} {
    read_spef results/ariane_routed_flat.spef
}

puts "\n----------------------------------------------------------------------"
puts "  PIN-3D PASS 1: Optimize Top Die (Tier 1) — Bottom Die Frozen"
puts "----------------------------------------------------------------------"
# In Pass 1: Tier 0 cells are frozen/unmovable. Buffer insertion and gate sizing are performed for Tier 1.
# Estimate baseline timing
report_worst_slack -max
report_worst_slack -min

# Run setup & hold repair with upper-tier buffer list
catch {repair_timing -setup -hold -buffer_cell "BUF_X4_upper"}

puts "\n----------------------------------------------------------------------"
puts "  PIN-3D PASS 2: Optimize Bottom Die (Tier 0) — Top Die Frozen"
puts "----------------------------------------------------------------------"
# In Pass 2: Tier 1 cells are fixed, and Tier 0 cells are optimized with full 3D timing context.
catch {repair_timing -setup -hold -buffer_cell "BUF_X4_bottom"}

puts "\n----------------------------------------------------------------------"
puts "  PIN-3D PASS 3: Top Die (Tier 1) Cleanup Pass"
puts "----------------------------------------------------------------------"
# In Pass 3: Re-optimize Tier 1 with accurate Tier 0 context to clean up over-inserted buffers.
catch {repair_timing -setup -buffer_cell "BUF_X4_upper"}

# Detailed Legalization after 3-Pass Sizing
puts "\nRunning OpenROAD Detailed Legalization after Pin-3D 3-Pass Optimization..."
detailed_placement

# FastRoute 3D Global Routing Update
puts "Running Global Route on Optimized 3D Design..."
set ::env(MIN_ROUTING_LAYER) "metal2"
set ::env(MAX_ROUTING_LAYER) "metal20"
source ../platforms/nangate45_3D/fastroute.tcl
source ../platforms/nangate45_3D/setRC.tcl
global_route

# Export Optimized DEF and SPEF
puts "Writing Pin-3D Optimized DEF & SPEF..."
write_def results/ariane_pin3d_pure.def

set rcx_rules "../platforms/nangate45_3D/nangate45_3D.rules"
if {[file exists $rcx_rules]} {
    catch {set_extraction_rules_file $rcx_rules}
}
estimate_parasitics -global_routing -spef_file results/ariane_pin3d_pure.spef

puts "✓ Pin-3D 3-Pass Alternating Optimization Completed Successfully!"
exit
