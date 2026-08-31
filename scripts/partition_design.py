#!/usr/bin/env python3
import sys
import re
import argparse
from pathlib import Path

def generate_structural_macros(suffix):
    # Generates a pure structural Nangate45-compatible netlist for the macro wrappers
    return f"""
// SyncSpRamBeNx64_00000008_00000100_0_2{suffix}
module SyncSpRamBeNx64_00000008_00000100_0_2{suffix}(
   Clk_CI,
   Rst_RBI,
   CSel_SI,
   WrEn_SI,
   BEn_SI,
   WrData_DI,
   Addr_DI,
   RdData_DO
   );

   input [7:0]   BEn_SI;
   input [63:0]  WrData_DI;
   input [7:0]   Addr_DI;
   output [63:0] RdData_DO;
   input         Clk_CI;
   input         Rst_RBI;
   input         CSel_SI;
   input         WrEn_SI;

   wire          wren_b, csel_b;
   wire          c_high;

   INV_X1{suffix} inv_wren (.A(WrEn_SI), .ZN(wren_b));
   INV_X1{suffix} inv_csel (.A(CSel_SI), .ZN(csel_b));
   LOGIC1_X1{suffix} tie_high (.Z(c_high));

   fakeram45_256x16{suffix} macro_mem_0 (.clk(Clk_CI),.rd_out(RdData_DO[15:0]), .ce_in(csel_b),.we_in(wren_b),.addr_in(Addr_DI),.w_mask_in({{c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high}}),.wd_in(WrData_DI[15:0]));
   fakeram45_256x16{suffix} macro_mem_1 (.clk(Clk_CI),.rd_out(RdData_DO[31:16]),.ce_in(csel_b),.we_in(wren_b),.addr_in(Addr_DI),.w_mask_in({{c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high}}),.wd_in(WrData_DI[31:16]));
   fakeram45_256x16{suffix} macro_mem_2 (.clk(Clk_CI),.rd_out(RdData_DO[47:32]),.ce_in(csel_b),.we_in(wren_b),.addr_in(Addr_DI),.w_mask_in({{c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high}}),.wd_in(WrData_DI[47:32]));
   fakeram45_256x16{suffix} macro_mem_3 (.clk(Clk_CI),.rd_out(RdData_DO[63:48]),.ce_in(csel_b),.we_in(wren_b),.addr_in(Addr_DI),.w_mask_in({{c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high}}),.wd_in(WrData_DI[63:48]));

endmodule

// limping_SyncSpRamBeNx64_00000008_00000100_0_2{suffix}
module limping_SyncSpRamBeNx64_00000008_00000100_0_2{suffix}(
   Clk_CI,
   Rst_RBI,
   CSel_SI,
   WrEn_SI,
   BEn_SI,
   WrData_DI,
   Addr_DI,
   RdData_DO
   );

   input [7:0]   BEn_SI;
   input [63:0]  WrData_DI;
   input [7:0]   Addr_DI;
   output [63:0] RdData_DO;
   input         Clk_CI;
   input         Rst_RBI;
   input         CSel_SI;
   input         WrEn_SI;

   wire          wren_b, csel_b;
   wire          c_high;

   INV_X1{suffix} inv_wren (.A(WrEn_SI), .ZN(wren_b));
   INV_X1{suffix} inv_csel (.A(CSel_SI), .ZN(csel_b));
   LOGIC1_X1{suffix} tie_high (.Z(c_high));

   fakeram45_256x16{suffix} macro_mem_0 (.clk(Clk_CI),.rd_out(RdData_DO[15:0]), .ce_in(csel_b),.we_in(wren_b),.addr_in(Addr_DI),.w_mask_in({{c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high}}),.wd_in(WrData_DI[15:0]));
   fakeram45_256x16{suffix} macro_mem_1 (.clk(Clk_CI),.rd_out(RdData_DO[31:16]),.ce_in(csel_b),.we_in(wren_b),.addr_in(Addr_DI),.w_mask_in({{c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high}}),.wd_in(WrData_DI[31:16]));
   fakeram45_256x16{suffix} macro_mem_2 (.clk(Clk_CI),.rd_out(RdData_DO[47:32]),.ce_in(csel_b),.we_in(wren_b),.addr_in(Addr_DI),.w_mask_in({{c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high}}),.wd_in(WrData_DI[47:32]));
   fakeram45_256x16{suffix} macro_mem_3 (.clk(Clk_CI),.rd_out(RdData_DO[63:48]),.ce_in(csel_b),.we_in(wren_b),.addr_in(Addr_DI),.w_mask_in({{c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high}}),.wd_in(WrData_DI[63:48]));

endmodule

// SyncSpRamBeNx64_00000008_00000100_0_2_d45{suffix}
module SyncSpRamBeNx64_00000008_00000100_0_2_d45{suffix}(
   Clk_CI,
   Rst_RBI,
   CSel_SI,
   WrEn_SI,
   BEn_SI,
   WrData_DI,
   Addr_DI,
   RdData_DO
   );

   input [7:0]   BEn_SI;
   input [44:0]  WrData_DI;
   input [7:0]   Addr_DI;
   output [44:0] RdData_DO;
   input         Clk_CI;
   input         Rst_RBI;
   input         CSel_SI;
   input         WrEn_SI;

   wire          wren_b, csel_b;
   wire          c_high;
   wire [2:0]    unused_bits;

   INV_X1{suffix} inv_wren (.A(WrEn_SI), .ZN(wren_b));
   INV_X1{suffix} inv_csel (.A(CSel_SI), .ZN(csel_b));
   LOGIC1_X1{suffix} tie_high (.Z(c_high));

   fakeram45_256x16{suffix} macro_mem_0 (.clk(Clk_CI),.rd_out(RdData_DO[15:0]), .ce_in(csel_b),.we_in(wren_b),.addr_in(Addr_DI),.w_mask_in({{c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high}}),.wd_in(WrData_DI[15:0]));
   fakeram45_256x16{suffix} macro_mem_1 (.clk(Clk_CI),.rd_out(RdData_DO[31:16]),.ce_in(csel_b),.we_in(wren_b),.addr_in(Addr_DI),.w_mask_in({{c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high}}),.wd_in(WrData_DI[31:16]));
   fakeram45_256x16{suffix} macro_mem_2 (.clk(Clk_CI),.rd_out({{unused_bits, RdData_DO[44:32]}}),.ce_in(csel_b),.we_in(wren_b),.addr_in(Addr_DI),.w_mask_in({{c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high}}),.wd_in({{3'b000, WrData_DI[44:32]}}));

endmodule

// SyncSpRamBeNx64_00000008_00000100_0_2_d44{suffix}
module SyncSpRamBeNx64_00000008_00000100_0_2_d44{suffix}(
   Clk_CI,
   Rst_RBI,
   CSel_SI,
   WrEn_SI,
   BEn_SI,
   WrData_DI,
   Addr_DI,
   RdData_DO
   );

   input [7:0]   BEn_SI;
   input [43:0]  WrData_DI;
   input [7:0]   Addr_DI;
   output [43:0] RdData_DO;
   input         Clk_CI;
   input         Rst_RBI;
   input         CSel_SI;
   input         WrEn_SI;

   wire          wren_b, csel_b;
   wire          c_high;
   wire [3:0]    unused_bits;

   INV_X1{suffix} inv_wren (.A(WrEn_SI), .ZN(wren_b));
   INV_X1{suffix} inv_csel (.A(CSel_SI), .ZN(csel_b));
   LOGIC1_X1{suffix} tie_high (.Z(c_high));

   fakeram45_256x16{suffix} macro_mem_0 (.clk(Clk_CI),.rd_out(RdData_DO[15:0]), .ce_in(csel_b),.we_in(wren_b),.addr_in(Addr_DI),.w_mask_in({{c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high}}),.wd_in(WrData_DI[15:0]));
   fakeram45_256x16{suffix} macro_mem_1 (.clk(Clk_CI),.rd_out(RdData_DO[31:16]),.ce_in(csel_b),.we_in(wren_b),.addr_in(Addr_DI),.w_mask_in({{c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high}}),.wd_in(WrData_DI[31:16]));
   fakeram45_256x16{suffix} macro_mem_2 (.clk(Clk_CI),.rd_out({{unused_bits, RdData_DO[43:32]}}),.ce_in(csel_b),.we_in(wren_b),.addr_in(Addr_DI),.w_mask_in({{c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high,c_high}}),.wd_in({{4'b0000, WrData_DI[43:32]}}));

endmodule
"""

def partition_design(input_verilog, input_macros, output_verilog, ratio=0.5):
    print(f"Reading 2D gate netlist: {input_verilog}")
    with open(input_verilog, 'r') as f:
        verilog_content = f.read()

    keywords = {
        'module', 'wire', 'input', 'output', 'inout', 'assign', 'endmodule',
        'parameter', 'localparam', 'tri', 'supply0', 'supply1', 'reg',
        'always', 'initial', 'begin', 'end', 'case', 'endcase', 'if', 'else',
        'generate', 'endgenerate', 'specify', 'endspecify'
    }

    # First pass: count cell instances and record their locations/order
    lines = verilog_content.split('\n')
    instances = []
    
    # Matches: CellType InstanceName (supporting escaped identifiers)
    inst_pattern = re.compile(r'^\s*([a-zA-Z_]\w*)\s+(\\?\S+)\s*\(')

    for line_idx, line in enumerate(lines):
        match = inst_pattern.match(line)
        if match:
            cell_type, inst_name = match.groups()
            if cell_type not in keywords:
                is_leaf = '_X' in cell_type or cell_type.startswith('SyncSpRam') or cell_type.startswith('limping_SyncSpRam') or 'fakeram45' in cell_type
                if is_leaf:
                    instances.append((cell_type, inst_name, line_idx))

    total_inst = len(instances)
    print(f"Discovered {total_inst} cell instances in 2D netlist.")

    if total_inst == 0:
        print("ERROR: No cell instances found! Check netlist format.")
        sys.exit(1)

    # Partition cell instances 50/50 (or based on ratio)
    cutoff = int(total_inst * ratio)
    tier_map = {}
    
    for idx, (cell_type, inst_name, line_idx) in enumerate(instances):
        # 0 = bottom, 1 = upper
        tier = 0 if idx < cutoff else 1
        tier_map[line_idx] = tier

    print(f"Partitioned: {cutoff} cells on Tier 0 (bottom), {total_inst - cutoff} cells on Tier 1 (upper).")

    # Second pass: modify module declarations/instantiations in main netlist
    output_lines = []
    for line_idx, line in enumerate(lines):
        if line_idx in tier_map:
            tier = tier_map[line_idx]
            suffix = "_bottom" if tier == 0 else "_upper"
            
            # Extract cell type from the line to replace it
            match = inst_pattern.match(line)
            cell_type, inst_name = match.groups()
            
            # Replace only the cell type name on this line
            line = re.sub(rf'\b{cell_type}\b', f"{cell_type}{suffix}", line, count=1)
            
        output_lines.append(line)

    print(f"Writing partitioned 3D netlist to {output_verilog}")
    
    # Write everything (partitioned ariane netlist + structural macro wrappers)
    with open(output_verilog, 'w') as f:
        f.write("\n".join(output_lines))
        f.write("\n\n// ==========================================\n")
        f.write("// 3D Projected Macro Wrapper Definitions\n")
        f.write("// ==========================================\n\n")
        f.write(generate_structural_macros("_bottom"))
        f.write(generate_structural_macros("_upper"))

    print("Partitioning and 3D netlist generation completed successfully!")

def main():
    parser = argparse.ArgumentParser(description="3D IC Verilog Netlist Partitioner (bottom/upper suffixes)")
    parser.add_argument("--netlist", required=True, help="Input 2D synthesized Verilog netlist")
    parser.add_argument("--macros", required=True, help="Input 2D macro definitions")
    parser.add_argument("--output", required=True, help="Output 3D partitioned Verilog netlist")
    parser.add_argument("--ratio", type=float, default=0.5, help="Ratio of cells assigned to Tier 0 (default: 0.5)")
    
    args = parser.parse_args()
    partition_design(args.netlist, args.macros, args.output, args.ratio)

if __name__ == "__main__":
    main()
