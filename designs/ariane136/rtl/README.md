# Ariane-136 (CVA6) RTL Sources

## TODO: DESIGN_FILES

Place the Ariane-136 (CVA6 64-bit 6-stage RISC-V application processor) RTL files here.

### Expected Files
- `ariane_pkg.sv` — Top-level package definitions
- `ariane.sv` — Top-level module
- All sub-module SystemVerilog sources

### Source
- Repository: https://github.com/openhwgroup/cva6
- The "ariane136" variant refers to the ~136K instance post-synthesis configuration.

### Synthesis Target
- PDK: NanGate45
- Clock frequency: ≥ 500 MHz
- Synthesize using Yosys or commercial synthesis tool, producing a gate-level netlist.
