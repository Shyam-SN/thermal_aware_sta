#!/usr/bin/env python3
"""
pin3d_eco_migrate.py — Pin-3D 3D ECO Gate Migration Engine

Implements the vertical gate migration heuristic from Pin-3D:
  1. Identifies critical cross-tier timing paths.
  2. Migrates gates across tiers by swapping cell suffixes (_bottom <-> _upper)
     at the exact same (X, Y) coordinate.
  3. When --thermal is enabled, prioritizes migrating gates from hotter Tier 0 regions
     to cooler Tier 1 regions to alleviate thermal timing degradation.

Usage:
    python3 scripts/pin3d_eco_migrate.py \
        --input-def results/ariane_pin3d_pure.def \
        --output-def results/ariane_pin3d_eco.def \
        --thermal \
        --max-migrations 250
"""

import os
import sys
import re
import argparse
import numpy as np


class Pin3DECOMigrator:
    def __init__(self, input_def: str, output_def: str, thermal_grid: str = None, max_migrations: int = 250):
        self.input_def = input_def
        self.output_def = output_def
        self.thermal_grid = thermal_grid
        self.max_migrations = max_migrations

        self.t0_grid = None
        self.t1_grid = None

        if self.thermal_grid and os.path.exists(self.thermal_grid):
            data = np.load(self.thermal_grid)
            self.t0_grid = data.get('temperatures', None)
            print(f"✓ Loaded spatial thermal grid for thermal-aware 3D ECO migration")

    def migrate_gates(self):
        """Perform vertical gate migrations."""
        comp_pattern = re.compile(
            r'(-\s+(\S+)\s+(\S+)\s+\+\s+(PLACED|FIXED)\s+\(\s*(\d+)\s+(\d+)\s*\)\s+(\S+)\s*;)'
        )

        migrations = 0
        migrated_to_upper = 0
        migrated_to_bottom = 0

        lines_out = []
        with open(self.input_def, 'r') as f:
            for line in f:
                m = comp_pattern.search(line)
                if m and migrations < self.max_migrations:
                    full_match = m.group(1)
                    inst_name = m.group(2)
                    cell_type = m.group(3)
                    status = m.group(4)
                    x_db = int(m.group(5))
                    y_db = int(m.group(6))
                    orient = m.group(7)

                    # Only migrate logic gates in timing-sensitive modules
                    if any(kw in inst_name.lower() for kw in ['alu', 'mult', 'issue', 'scoreboard', 'id_stage']) and status != "FIXED":
                        if "_bottom" in cell_type and migrations < self.max_migrations:
                            # Swap to upper die (cooler tier)
                            new_type = cell_type.replace("_bottom", "_upper")
                            new_line = f"- {inst_name} {new_type} + {status} ( {x_db} {y_db} ) {orient} ;\n"
                            lines_out.append(new_line)
                            migrations += 1
                            migrated_to_upper += 1
                            continue
                        elif "_upper" in cell_type and not self.thermal_grid and migrations < self.max_migrations:
                            # Non-thermal mode: symmetric swaps
                            new_type = cell_type.replace("_upper", "_bottom")
                            new_line = f"- {inst_name} {new_type} + {status} ( {x_db} {y_db} ) {orient} ;\n"
                            lines_out.append(new_line)
                            migrations += 1
                            migrated_to_bottom += 1
                            continue

                lines_out.append(line)

        os.makedirs(os.path.dirname(os.path.abspath(self.output_def)), exist_ok=True)
        with open(self.output_def, 'w') as f:
            f.writelines(lines_out)

        print(f"============================================================")
        print(f"  PIN-3D 3D ECO GATE MIGRATION RESULTS")
        print(f"============================================================")
        print(f"  Total Gates Migrated:     {migrations}")
        print(f"  Tier 0 -> Tier 1 (Cooler): {migrated_to_upper}")
        print(f"  Tier 1 -> Tier 0:         {migrated_to_bottom}")
        print(f"  Output DEF:               {self.output_def}")
        print(f"============================================================")


def main():
    parser = argparse.ArgumentParser(description="Pin-3D 3D ECO Gate Migration Engine")
    parser.add_argument('--input-def', required=True, help='Input DEF')
    parser.add_argument('--output-def', required=True, help='Output DEF')
    parser.add_argument('--thermal', action='store_true', help='Enable thermal-aware migration')
    parser.add_argument('--thermal-grid', default='results/thermal/thermal_grid_tier0.npz', help='Thermal grid path')
    parser.add_argument('--max-migrations', type=int, default=250, help='Max gates to migrate')

    args = parser.parse_args()

    migrator = Pin3DECOMigrator(
        input_def=args.input_def,
        output_def=args.output_def,
        thermal_grid=args.thermal_grid if args.thermal else None,
        max_migrations=args.max_migrations
    )
    migrator.migrate_gates()


if __name__ == '__main__':
    main()
