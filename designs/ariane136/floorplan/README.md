# Pin-3D Floorplan Specifications — Ariane-136

## TODO: DESIGN_FILES

Place Pin-3D floorplan configuration and resulting tier DEF files here.

### Expected Files
- `ariane_tier0.def` — Tier 0 (bottom die) placed & routed DEF
- `ariane_tier1.def` — Tier 1 (top die) placed & routed DEF
- `partition_config.json` — Pin-3D partitioning parameters
- `hbt_locations.csv` — Hybrid Bonding Terminal coordinates (x, y, net_name)

### Pin-3D Partitioning Parameters
- Partitioning strategy: Min-cut balanced area
- Target tier area ratio: 50/50 (±5%)
- Cross-tier via technology: HBT (F2F hybrid bonding)
- HBT pitch: 10 µm, diameter: 5 µm
- Max cross-tier net cuts: minimize inter-tier signal crossings
