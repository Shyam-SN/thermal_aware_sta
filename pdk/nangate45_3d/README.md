# NanGate45 3D PDK Files

## TODO: DESIGN_FILES

Place the NanGate45 open standard cell library files adapted for 3D integration here.

### Expected Files
- `NangateOpenCellLibrary.lef` — Cell LEF (abstract layout)
- `NangateOpenCellLibrary_typical.lib` — Liberty timing (TT corner)
- `NangateOpenCellLibrary_fast.lib` — Liberty timing (FF corner)
- `NangateOpenCellLibrary_slow.lib` — Liberty timing (SS corner)
- `NangateOpenCellLibrary.tech.lef` — Technology LEF (metal stack)
- `NangateOpenCellLibrary.v` — Verilog behavioral models

### 3D Adaptations Required
- Modify tech LEF to include HBT/MIV via definitions
- Add cross-tier via rules to routing tech file
- Optionally: Create tier-specific LEF variants with reduced metal stacks

### Source
- NanGate FreePDK45: https://si2.org/open-cell-library/
- OpenROAD flow scripts include NanGate45 support
