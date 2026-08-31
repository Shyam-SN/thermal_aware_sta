# OpenROAD TCL script to run flat 3D Place and Route on partitioned Ariane design
# Part of the Thermal-Aware Pin-3D Framework.

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

# 3. Read partitioned 3D Verilog netlist
read_verilog results/ariane_3d.v
link_design ariane

# 4. Load timing constraints
read_sdc ../designs/nangate45_3D/ariane136/ariane.sdc

# 5. Initialize floorplan
# Die area 1000x1000 um
initialize_floorplan -site FreePDK45_38x28_10R_NP_162NW_34O -die_area {0 0 1000 1000} -core_area {10 12 990 988}

# Load track generation and RC values
set ::env(MIN_ROUTING_LAYER) "metal2"
set ::env(MAX_ROUTING_LAYER) "metal20"
source ../platforms/nangate45_3D/fastroute.tcl
source ../platforms/nangate45_3D/setRC.tcl

# Place IO pins
place_pins -hor_layer metal5 -ver_layer metal6

# 6. Placement
puts "Running Global Placement..."
global_placement -density 0.75

puts "Running Detailed Placement..."
detailed_placement

# 7. Symmetrical CTS using bottom buffers to avoid cross-tier clock skew imbalances
puts "Running Symmetrical Clock Tree Synthesis..."
clock_tree_synthesis -buf_list "BUF_X4_bottom"

# 8. Global Routing
puts "Running Global Route..."
global_route

# Write placed and routed flat DEF
puts "Writing flat 3D DEF..."
write_def results/ariane_routed_flat.def

# Run parasitics extraction (OpenRCX / Global Route parasitics)
puts "Running OpenRCX Parasitics Extraction..."
set rcx_rules "../platforms/nangate45_3D/nangate45_3D.rules"
if {[file exists $rcx_rules]} {
    catch {set_extraction_rules_file $rcx_rules}
}
estimate_parasitics -global_routing -spef_file results/ariane_routed_flat.spef

puts "Flat 3D Place & Route completed successfully!"
exit
