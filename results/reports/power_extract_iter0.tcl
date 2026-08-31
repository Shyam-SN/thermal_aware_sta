
# Power extraction — Iteration 0
read_lef "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lef/NangateOpenCellLibrary.tech.lef"

read_lef "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lef_bottom/NangateOpenCellLibrary.macro.mod.bottom.lef"
read_lef "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lef_upper/NangateOpenCellLibrary.macro.mod.upper.lef"
read_lef "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lef_bottom/fakeram45_256x16.bottom.lef"
read_lef "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lef_upper/fakeram45_256x16.upper.lef"

read_liberty "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lib_bottom/NangateOpenCellLibrary_typical.bottom.lib"
read_liberty "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lib_upper/NangateOpenCellLibrary_typical.upper copy.lib"
read_liberty "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lib_bottom/fakeram45_256x16.bottom.lib"
read_liberty "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lib_upper/fakeram45_256x16.upper.lib"
read_def "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/results/ariane_thermal_legalized.def"
read_sdc "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../designs/nangate45_3D/ariane136/ariane.sdc"

# Read SPEF if available (for more accurate switching activity)
set spef_path "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/results/ariane_thermal_routed.spef"
if {[file exists $spef_path]} {
    read_spef $spef_path
}

# Report instance-level power
report_power -instances [get_cells *] > "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/results/reports/power_instance_iter0.rpt"
