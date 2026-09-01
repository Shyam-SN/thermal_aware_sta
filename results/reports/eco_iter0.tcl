
# ECO Timing Repair — Iteration 0
# WNS: 0.0 ps, TNS: 0.0 ps

read_lef "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lef/NangateOpenCellLibrary.tech.lef"
read_lef "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lef_bottom/NangateOpenCellLibrary.macro.mod.bottom.lef"
read_lef "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lef_upper/NangateOpenCellLibrary.macro.mod.upper.lef"
read_lef "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lef_bottom/fakeram45_256x16.bottom.lef"
read_lef "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lef_upper/fakeram45_256x16.upper.lef"
read_liberty "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lib_bottom/NangateOpenCellLibrary_typical.bottom.lib"
read_liberty "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lib_upper/NangateOpenCellLibrary_typical.upper copy.lib"
read_liberty "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lib_bottom/fakeram45_256x16.bottom.lib"
read_liberty "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lib_upper/fakeram45_256x16.upper.lib"
read_def /Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/results/ariane_thermal_legalized.def
read_sdc /Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../designs/nangate45_3D/ariane136/ariane.sdc

# Setup timing repair
repair_timing -setup \
    -slack_margin 0.020

# Hold timing repair
repair_timing -hold \
    -slack_margin 0.010

# Re-route after ECO
# detailed_route -bottom_routing_layer metal1 -top_routing_layer metal7

# Write updated DEF
write_def /Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/results/ariane_thermal_legalized.def.eco_iter0.def

# Re-extract parasitics
set spef_out "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/results/ariane_thermal_routed.spef"
# extract_parasitics -ext_model_file <rcx_model>
# write_spef $spef_out
