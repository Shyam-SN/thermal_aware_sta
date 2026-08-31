# OpenROAD TCL script to legalize and route Thermal-Optimized 3D Placement
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

# 3. Read thermal-optimized DEF
puts "Reading Thermal-Optimized DEF: results/ariane_thermal_placed.def"
read_def results/ariane_thermal_placed.def

# 4. Load timing constraints
read_sdc ../designs/nangate45_3D/ariane136/ariane.sdc
catch {set_false_path -from [get_ports rst_ni]}

# 6. Detailed Legalization
puts "Running OpenROAD Detailed Legalization on Thermal Placement..."
detailed_placement

# 7. Global Route on updated placement
puts "Running Global Route on Thermal Placement..."
set ::env(MIN_ROUTING_LAYER) "metal2"
set ::env(MAX_ROUTING_LAYER) "metal20"
source ../platforms/nangate45_3D/fastroute.tcl
source ../platforms/nangate45_3D/setRC.tcl
global_route

# 8. Write Legalized Thermal DEF
puts "Writing Legalized Thermal 3D DEF..."
write_def results/ariane_thermal_legalized.def

# 9. Extract Global Parasitics with OpenRCX
puts "Extracting Parasitics for Thermal Placement..."
set rcx_rules "../platforms/nangate45_3D/nangate45_3D.rules"
if {[file exists $rcx_rules]} {
    catch {set_extraction_rules_file $rcx_rules}
}
estimate_parasitics -global_routing -spef_file results/ariane_thermal_routed.spef

puts "✓ Thermal-Aware Placement Legalization & Routing Complete!"
exit
