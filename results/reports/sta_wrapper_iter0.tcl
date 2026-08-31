
set design_name ariane136
set tech_lef_path "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lef/NangateOpenCellLibrary.tech.lef"
set lef_files  [list "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lef_bottom/NangateOpenCellLibrary.macro.mod.bottom.lef" "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lef_upper/NangateOpenCellLibrary.macro.mod.upper.lef" "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lef_bottom/fakeram45_256x16.bottom.lef" "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lef_upper/fakeram45_256x16.upper.lef"]
set lib_files  [list "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lib_bottom/NangateOpenCellLibrary_typical.bottom.lib" "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lib_upper/NangateOpenCellLibrary_typical.upper copy.lib" "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lib_bottom/fakeram45_256x16.bottom.lib" "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../platforms/nangate45_3D/lib_upper/fakeram45_256x16.upper.lib"]
set tier0_def "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/results/ariane_thermal_legalized.def"
set tier1_def "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/results/ariane_thermal_legalized.def"
set tier0_spef "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/results/thermal/ariane_tier0_thermal_iter0.spef"
set tier1_spef "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/results/thermal/ariane_tier1_thermal_iter0.spef"
set sdc_path "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/../designs/nangate45_3D/ariane136/ariane.sdc"
set report_dir "/Users/prathima/Desktop/Shyam/thermal_pin3d_openroad/results/reports"
set iteration 0
source scripts/run_sta_3d.tcl
