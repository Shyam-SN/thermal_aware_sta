#!/usr/bin/env python3
"""
thermal_rcx.py — Thermal-Aware SPEF Parasitic Modifier

This module ingests baseline SPEF files (from OpenRCX) and spatial temperature
grids (from PACT via pact_bridge.py), then applies temperature-dependent
resistance scaling to every routed interconnect segment.

Key operations:
  1. Parse SPEF *D_NET / *R_NET sections with segment coordinates
  2. For each segment, compute T_seg from the thermal grid via bilinear interp
  3. Apply TCR scaling: R_new = R_nom * [1 + alpha * (T_seg - T_nom)]
  4. Scale HBT/MIV inter-tier via resistances using T_interface(x,y)
  5. Emit valid, modified SPEF preserving all formatting and capacitance

Part of the Thermal-Aware Pin-3D Framework for Ariane-136.
"""

import argparse
import configparser
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

# Import thermal grid utilities from pact_bridge
try:
    from pact_bridge import ThermalGrid, load_thermal_grid
except ImportError:
    # Fallback: add parent/scripts to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from pact_bridge import ThermalGrid, load_thermal_grid

# ---------------------------------------------------------------------------
# Configuration & Constants
# ---------------------------------------------------------------------------

logger = logging.getLogger("thermal_rcx")

# Reference temperature for TCR calculations
T_NOM = 25.0  # °C

# Default TCR for Cu interconnect [K⁻¹]
ALPHA_CU = 0.00393

# Default TCR for Al (top metal / pad) [K⁻¹]
ALPHA_AL = 0.00429

# TCR for Cu HBT / MIV vias
ALPHA_HBT = 0.00393

# SPEF coordinate scale factor (DEF units to µm)
# This should match the SPEF *DESIGN_FLOW / *DIVIDER settings
DEFAULT_SPEF_COORD_SCALE = 1.0 / 1000.0  # DEF units → µm


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class SPEFHeader:
    """Parsed SPEF header metadata."""
    spef_version: str = ""
    design_name: str = ""
    date: str = ""
    vendor: str = ""
    program: str = ""
    divider: str = "/"
    delimiter: str = ":"
    bus_delimiter: str = "[]"
    t_unit: str = "1 NS"
    c_unit: str = "1 PF"
    r_unit: str = "1 OHM"
    l_unit: str = "1 HENRY"
    # Name map
    name_map: Dict[str, str] = field(default_factory=dict)

    @property
    def r_multiplier(self) -> float:
        """Resistance multiplier to convert SPEF R values to Ohms."""
        parts = self.r_unit.strip().split()
        if len(parts) == 2:
            val = float(parts[0])
            unit = parts[1].upper()
            unit_map = {"OHM": 1.0, "KOHM": 1e3, "MOHM": 1e-3}
            return val * unit_map.get(unit, 1.0)
        return 1.0


@dataclass
class SPEFNode:
    """A node (pin or internal node) in a SPEF net."""
    name: str
    x: float = 0.0  # Coordinate in µm
    y: float = 0.0
    has_coords: bool = False


@dataclass
class SPEFResistor:
    """A resistor segment in a SPEF net."""
    node1: str
    node2: str
    resistance: float  # In SPEF units (before scaling)
    line_number: int = -1  # For in-place editing


@dataclass
class SPEFNet:
    """A parsed SPEF net (*D_NET or *R_NET)."""
    name: str
    total_cap: float = 0.0
    nodes: Dict[str, SPEFNode] = field(default_factory=dict)
    resistors: List[SPEFResistor] = field(default_factory=list)
    is_dnet: bool = True  # True for *D_NET, False for *R_NET


# ---------------------------------------------------------------------------
# Material / TCR Configuration Loader
# ---------------------------------------------------------------------------

class TCRConfig:
    """
    Loads layer-specific TCR (alpha) values from materials.config.
    Falls back to Cu default for unspecified layers.
    """

    def __init__(self, config_path: str = None):
        self.layer_alpha: Dict[str, float] = {}
        self.via_alpha: float = ALPHA_HBT

        if config_path and Path(config_path).exists():
            self._load(config_path)
        else:
            self._set_defaults()

    def _load(self, config_path: str):
        """Parse materials.config for per-layer alpha values."""
        logger.info(f"Loading TCR configuration from {config_path}")

        current_section = None

        with open(config_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                # Section header [section_name]
                section_match = re.match(r'\[(\w+)\]', line)
                if section_match:
                    current_section = section_match.group(1).lower()
                    continue

                # Key = value
                kv_match = re.match(r'(\w+)\s*=\s*(.+)', line)
                if kv_match and current_section:
                    key = kv_match.group(1).strip().lower()
                    value = kv_match.group(2).strip()

                    if key == 'alpha' and current_section.startswith('metal'):
                        try:
                            self.layer_alpha[current_section] = float(value)
                        except ValueError:
                            pass

                    if key == 'alpha' and current_section in ('hbt_via', 'miv_via'):
                        try:
                            self.via_alpha = float(value)
                        except ValueError:
                            pass

        if not self.layer_alpha:
            self._set_defaults()

        logger.info(f"  Loaded TCR for {len(self.layer_alpha)} metal layers")

    def _set_defaults(self):
        """Set default Cu TCR for all metal layers."""
        for i in range(1, 21):
            self.layer_alpha[f"metal{i}"] = ALPHA_CU
        self.via_alpha = ALPHA_HBT

    def get_alpha(self, layer_name: str) -> float:
        """
        Get TCR alpha for a given layer.

        Args:
            layer_name: Metal layer name (e.g., 'metal1', 'M3', 'via4')

        Returns:
            TCR alpha value [K⁻¹]
        """
        # Normalize layer name
        normalized = layer_name.lower().replace(' ', '')

        # Direct match
        if normalized in self.layer_alpha:
            return self.layer_alpha[normalized]

        # Try 'M1' -> 'metal1' conversion
        m_match = re.match(r'm(\d+)', normalized)
        if m_match:
            key = f"metal{m_match.group(1)}"
            if key in self.layer_alpha:
                return self.layer_alpha[key]

        # Via layers
        if 'via' in normalized or 'hbt' in normalized or 'miv' in normalized:
            return self.via_alpha

        # Default to Cu
        return ALPHA_CU


# ---------------------------------------------------------------------------
# SPEF Parser
# ---------------------------------------------------------------------------

class SPEFParser:
    """
    Parses SPEF (Standard Parasitic Exchange Format) files.

    Extracts:
      - Header metadata (units, name map, design info)
      - Net definitions (*D_NET or *R_NET)
      - Node coordinates (*CONN, *I, *P sections)
      - Resistance segments (*RES section)
      - Capacitance values (*CAP section) — preserved but not modified
    """

    def __init__(self, spef_path: str):
        self.spef_path = Path(spef_path)
        self.header = SPEFHeader()
        self.nets: Dict[str, SPEFNet] = {}
        self._raw_lines: List[str] = []

    def parse(self) -> Tuple[SPEFHeader, Dict[str, SPEFNet], List[str]]:
        """
        Parse the SPEF file.

        Returns:
            Tuple of (header, nets dict, raw lines for modification)
        """
        logger.info(f"Parsing SPEF: {self.spef_path}")

        if not self.spef_path.exists():
            raise FileNotFoundError(f"SPEF file not found: {self.spef_path}")

        with open(self.spef_path, 'r') as f:
            self._raw_lines = f.readlines()

        self._parse_header()
        self._parse_name_map()
        self._parse_nets()

        logger.info(f"  Parsed {len(self.nets)} nets, "
                     f"{sum(len(n.resistors) for n in self.nets.values())} R segments")

        return self.header, self.nets, self._raw_lines

    def _parse_header(self):
        """Parse SPEF header statements."""
        for line in self._raw_lines[:100]:  # Header is in the first ~100 lines
            stripped = line.strip()

            if stripped.startswith('*SPEF'):
                parts = stripped.split('"')
                if len(parts) >= 2:
                    self.header.spef_version = parts[1]
            elif stripped.startswith('*DESIGN'):
                parts = stripped.split('"')
                if len(parts) >= 2:
                    self.header.design_name = parts[1]
            elif stripped.startswith('*DATE'):
                parts = stripped.split('"')
                if len(parts) >= 2:
                    self.header.date = parts[1]
            elif stripped.startswith('*T_UNIT'):
                self.header.t_unit = stripped.split(None, 1)[1] if len(stripped.split()) > 1 else ""
            elif stripped.startswith('*C_UNIT'):
                self.header.c_unit = stripped.split(None, 1)[1] if len(stripped.split()) > 1 else ""
            elif stripped.startswith('*R_UNIT'):
                self.header.r_unit = stripped.split(None, 1)[1] if len(stripped.split()) > 1 else ""
            elif stripped.startswith('*L_UNIT'):
                self.header.l_unit = stripped.split(None, 1)[1] if len(stripped.split()) > 1 else ""
            elif stripped.startswith('*DIVIDER'):
                self.header.divider = stripped.split()[-1]
            elif stripped.startswith('*DELIMITER'):
                self.header.delimiter = stripped.split()[-1]

    def _parse_name_map(self):
        """Parse *NAME_MAP section."""
        in_name_map = False
        for line in self._raw_lines:
            stripped = line.strip()

            if stripped.startswith('*NAME_MAP'):
                in_name_map = True
                continue

            if in_name_map:
                if stripped.startswith('*') and not stripped.startswith('*'):
                    break

                # Format: *123 net_name or *123 inst_name
                match = re.match(r'\*(\d+)\s+(\S+)', stripped)
                if match:
                    self.header.name_map[f"*{match.group(1)}"] = match.group(2)
                elif stripped.startswith('*') and not stripped.startswith('*NAME'):
                    # End of name map
                    if not re.match(r'\*\d+', stripped):
                        break

    def _parse_nets(self):
        """Parse *D_NET and *R_NET sections."""
        i = 0
        while i < len(self._raw_lines):
            line = self._raw_lines[i].strip()

            # Detect net start
            dnet_match = re.match(r'\*D_NET\s+(\S+)\s+([\d.eE+\-]+)', line)
            rnet_match = re.match(r'\*R_NET\s+(\S+)\s+([\d.eE+\-]+)', line) if not dnet_match else None

            if dnet_match or rnet_match:
                match = dnet_match or rnet_match
                net_name = match.group(1)
                total_cap = float(match.group(2))

                net = SPEFNet(
                    name=net_name,
                    total_cap=total_cap,
                    is_dnet=(dnet_match is not None),
                )

                i = self._parse_net_body(net, i + 1)
                self.nets[net_name] = net
            else:
                i += 1

    def _parse_net_body(self, net: SPEFNet, start_idx: int) -> int:
        """Parse the body of a *D_NET/*R_NET block."""
        i = start_idx
        in_conn = False
        in_res = False
        in_cap = False

        while i < len(self._raw_lines):
            line = self._raw_lines[i].strip()

            # End of net
            if line.startswith('*END'):
                return i + 1

            # Next net or end of file
            if line.startswith('*D_NET') or line.startswith('*R_NET'):
                return i

            # Section markers
            if line.startswith('*CONN'):
                in_conn = True
                in_res = False
                in_cap = False
                i += 1
                continue
            elif line.startswith('*RES'):
                in_conn = False
                in_res = True
                in_cap = False
                i += 1
                continue
            elif line.startswith('*CAP'):
                in_conn = False
                in_res = False
                in_cap = True
                i += 1
                continue

            if in_conn:
                self._parse_conn_line(net, line)
            elif in_res:
                self._parse_res_line(net, line, i)

            i += 1

        return i

    def _parse_conn_line(self, net: SPEFNet, line: str):
        """
        Parse a *CONN section line to extract node coordinates.

        Formats:
          *I inst:pin *C x y     (internal pin)
          *P port *C x y         (external port)
          *N node *C x y         (internal node with coords)
        """
        # Match *I or *P with coordinates
        match = re.match(
            r'\*[IPN]\s+(\S+).*?\*C\s+([\d.eE+\-]+)\s+([\d.eE+\-]+)',
            line
        )
        if match:
            node_name = match.group(1)
            x = float(match.group(2)) * DEFAULT_SPEF_COORD_SCALE
            y = float(match.group(3)) * DEFAULT_SPEF_COORD_SCALE

            net.nodes[node_name] = SPEFNode(
                name=node_name, x=x, y=y, has_coords=True
            )

    def _parse_res_line(self, net: SPEFNet, line: str, line_idx: int):
        """
        Parse a *RES section line.

        Format: index node1 node2 resistance_value
        """
        match = re.match(
            r'(\d+)\s+(\S+)\s+(\S+)\s+([\d.eE+\-]+)',
            line
        )
        if match:
            net.resistors.append(SPEFResistor(
                node1=match.group(2),
                node2=match.group(3),
                resistance=float(match.group(4)),
                line_number=line_idx,
            ))


# ---------------------------------------------------------------------------
# Thermal SPEF Modifier
# ---------------------------------------------------------------------------

class ThermalSPEFModifier:
    """
    Applies temperature-dependent resistance scaling to parsed SPEF data.

    For each resistor segment:
      1. Look up node coordinates from SPEF *CONN data
      2. Compute segment temperature: T_seg = avg(T(x_a,y_a), T(x_b,y_b))
      3. Apply TCR: R_new = R_nom * [1 + alpha * (T_seg - T_nom)]
      4. Update the raw SPEF line with the new resistance value
    """

    def __init__(self, thermal_grid: ThermalGrid, tcr_config: TCRConfig,
                 t_nom: float = T_NOM,
                 interface_grid: ThermalGrid = None):
        self.thermal_grid = thermal_grid
        self.tcr_config = tcr_config
        self.t_nom = t_nom
        self.interface_grid = interface_grid

        # Statistics
        self.stats = {
            "segments_modified": 0,
            "segments_skipped_no_coords": 0,
            "max_t_seg": t_nom,
            "min_t_seg": t_nom,
            "max_r_ratio": 1.0,
            "min_r_ratio": 1.0,
            "total_nets_processed": 0,
        }

    def modify_spef(self, header: SPEFHeader, nets: Dict[str, SPEFNet],
                     raw_lines: List[str],
                     layer_name: str = "metal1") -> List[str]:
        """
        Apply thermal scaling to all nets and return modified SPEF lines.

        Args:
            header: Parsed SPEF header
            nets: Parsed SPEF nets
            raw_lines: Original SPEF file lines
            layer_name: Default metal layer for TCR lookup

        Returns:
            Modified list of SPEF lines
        """
        logger.info("Applying thermal resistance scaling...")

        modified_lines = list(raw_lines)  # Copy
        alpha = self.tcr_config.get_alpha(layer_name)

        for net_name, net in nets.items():
            self.stats["total_nets_processed"] += 1

            for res in net.resistors:
                # Get coordinates for both nodes
                node1 = net.nodes.get(res.node1)
                node2 = net.nodes.get(res.node2)

                if node1 and node1.has_coords and node2 and node2.has_coords:
                    # Compute segment temperature (bilinear interpolation)
                    t1 = self.thermal_grid.get_temperature(node1.x, node1.y)
                    t2 = self.thermal_grid.get_temperature(node2.x, node2.y)
                    t_seg = (t1 + t2) / 2.0

                    # Apply TCR scaling
                    r_ratio = 1.0 + alpha * (t_seg - self.t_nom)
                    r_new = res.resistance * r_ratio

                    # Update raw line
                    if 0 <= res.line_number < len(modified_lines):
                        old_line = modified_lines[res.line_number]
                        new_line = self._replace_resistance(
                            old_line, res.resistance, r_new
                        )
                        modified_lines[res.line_number] = new_line

                    # Track stats
                    self.stats["segments_modified"] += 1
                    self.stats["max_t_seg"] = max(self.stats["max_t_seg"], t_seg)
                    self.stats["min_t_seg"] = min(self.stats["min_t_seg"], t_seg)
                    self.stats["max_r_ratio"] = max(self.stats["max_r_ratio"], r_ratio)
                    self.stats["min_r_ratio"] = min(self.stats["min_r_ratio"], r_ratio)

                elif node1 and node1.has_coords:
                    # Only one node has coords — use its temperature
                    t_seg = self.thermal_grid.get_temperature(node1.x, node1.y)
                    r_ratio = 1.0 + alpha * (t_seg - self.t_nom)
                    r_new = res.resistance * r_ratio

                    if 0 <= res.line_number < len(modified_lines):
                        old_line = modified_lines[res.line_number]
                        new_line = self._replace_resistance(
                            old_line, res.resistance, r_new
                        )
                        modified_lines[res.line_number] = new_line

                    self.stats["segments_modified"] += 1

                elif node2 and node2.has_coords:
                    t_seg = self.thermal_grid.get_temperature(node2.x, node2.y)
                    r_ratio = 1.0 + alpha * (t_seg - self.t_nom)
                    r_new = res.resistance * r_ratio

                    if 0 <= res.line_number < len(modified_lines):
                        old_line = modified_lines[res.line_number]
                        new_line = self._replace_resistance(
                            old_line, res.resistance, r_new
                        )
                        modified_lines[res.line_number] = new_line

                    self.stats["segments_modified"] += 1

                else:
                    # Neither node has coords in SPEF — scale by tier mean temperature
                    t_seg = float(np.mean(self.thermal_grid.temperatures))
                    r_ratio = 1.0 + alpha * (t_seg - self.t_nom)
                    r_new = res.resistance * r_ratio

                    if 0 <= res.line_number < len(modified_lines):
                        old_line = modified_lines[res.line_number]
                        new_line = self._replace_resistance(
                            old_line, res.resistance, r_new
                        )
                        modified_lines[res.line_number] = new_line

                    self.stats["segments_modified"] += 1
                    self.stats["max_t_seg"] = max(self.stats["max_t_seg"], t_seg)
                    self.stats["min_t_seg"] = min(self.stats["min_t_seg"], t_seg)
                    self.stats["max_r_ratio"] = max(self.stats["max_r_ratio"], r_ratio)
                    self.stats["min_r_ratio"] = min(self.stats["min_r_ratio"], r_ratio)

        logger.info(f"  Modified: {self.stats['segments_modified']} segments")
        logger.info(f"  Skipped (no coords): {self.stats['segments_skipped_no_coords']}")
        logger.info(f"  T_seg range: {self.stats['min_t_seg']:.2f}°C — "
                     f"{self.stats['max_t_seg']:.2f}°C")
        logger.info(f"  R ratio range: {self.stats['min_r_ratio']:.4f} — "
                     f"{self.stats['max_r_ratio']:.4f}")

        return modified_lines

    def scale_interface_vias(self, header: SPEFHeader, nets: Dict[str, SPEFNet],
                              raw_lines: List[str],
                              via_net_pattern: str = r'.*hbt.*|.*miv.*|.*cross_tier.*'
                              ) -> List[str]:
        """
        Scale inter-tier via (HBT/MIV) resistances using the interface
        temperature grid.

        Args:
            header: SPEF header
            nets: Parsed nets
            raw_lines: Current SPEF lines (may already be modified)
            via_net_pattern: Regex pattern to identify cross-tier nets

        Returns:
            Modified SPEF lines
        """
        if self.interface_grid is None:
            logger.warning("No interface thermal grid — skipping via scaling")
            return raw_lines

        logger.info("Scaling inter-tier via resistances...")

        modified_lines = list(raw_lines)
        pattern = re.compile(via_net_pattern, re.IGNORECASE)
        alpha_via = self.tcr_config.via_alpha
        vias_scaled = 0

        for net_name, net in nets.items():
            # Resolve net name through name map
            resolved_name = header.name_map.get(net_name, net_name)

            # Auto-detect cross-tier nets: either by name pattern or by having connections across both tiers
            is_cross_tier = bool(pattern.match(resolved_name))
            if not is_cross_tier:
                has_bottom = any("_bottom" in header.name_map.get(node.split(':')[0], node.split(':')[0]) for node in net.nodes)
                has_upper = any("_upper" in header.name_map.get(node.split(':')[0], node.split(':')[0]) for node in net.nodes)
                is_cross_tier = (has_bottom and has_upper)

            if not is_cross_tier:
                continue

            for res in net.resistors:
                # Use any available coordinate
                coord_node = None
                for node_name in [res.node1, res.node2]:
                    node = net.nodes.get(node_name)
                    if node and node.has_coords:
                        coord_node = node
                        break

                if coord_node:
                    t_intf = self.interface_grid.get_temperature(
                        coord_node.x, coord_node.y
                    )
                    r_ratio = 1.0 + alpha_via * (t_intf - self.t_nom)
                    r_new = res.resistance * r_ratio

                    if 0 <= res.line_number < len(modified_lines):
                        old_line = modified_lines[res.line_number]
                        new_line = self._replace_resistance(
                            old_line, res.resistance, r_new
                        )
                        modified_lines[res.line_number] = new_line
                        vias_scaled += 1

        logger.info(f"  Scaled {vias_scaled} inter-tier via resistances")
        return modified_lines

    @staticmethod
    def _replace_resistance(line: str, old_r: float, new_r: float) -> str:
        """
        Replace a resistance value in a SPEF line while preserving formatting.

        This handles both fixed and scientific notation formats.
        """
        # Build a pattern that matches the old resistance value
        # We need to handle floating point representation ambiguity
        old_str_candidates = [
            f"{old_r:.6f}",       # Fixed notation
            f"{old_r:.4f}",
            f"{old_r:.6e}",       # Scientific notation
            f"{old_r:.4e}",
            f"{old_r}",           # Default repr
        ]

        for old_str in old_str_candidates:
            if old_str in line:
                # Format new value similarly
                if 'e' in old_str or 'E' in old_str:
                    new_str = f"{new_r:.6e}"
                else:
                    # Match decimal places
                    dot_pos = old_str.find('.')
                    if dot_pos >= 0:
                        decimal_places = len(old_str) - dot_pos - 1
                        new_str = f"{new_r:.{decimal_places}f}"
                    else:
                        new_str = f"{new_r:.6f}"

                return line.replace(old_str, new_str, 1)

        # Fallback: regex-based replacement of the last number on the line
        parts = line.rstrip().rsplit(None, 1)
        if len(parts) == 2:
            try:
                float(parts[1])  # Verify it's a number
                return parts[0] + f" {new_r:.6f}" + "\n"
            except ValueError:
                pass

        return line  # Return unchanged if we can't find the value

    def get_stats_report(self) -> str:
        """Generate a human-readable statistics report."""
        lines = [
            "=" * 60,
            "Thermal SPEF Modification Report",
            "=" * 60,
            f"Nets processed:            {self.stats['total_nets_processed']}",
            f"Segments modified:         {self.stats['segments_modified']}",
            f"Segments skipped (no XY):  {self.stats['segments_skipped_no_coords']}",
            f"T_seg range:               {self.stats['min_t_seg']:.2f}°C — "
            f"{self.stats['max_t_seg']:.2f}°C",
            f"R scaling ratio range:     {self.stats['min_r_ratio']:.6f} — "
            f"{self.stats['max_r_ratio']:.6f}",
            f"Reference temperature:     {self.t_nom}°C",
            "=" * 60,
        ]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# SPEF Writer
# ---------------------------------------------------------------------------

def write_spef(lines: List[str], output_path: str,
               annotation_comment: str = None):
    """
    Write modified SPEF lines to a file.

    Optionally adds an annotation comment at the top indicating
    thermal modification.

    Args:
        lines: Modified SPEF lines
        output_path: Output file path
        annotation_comment: Optional comment to prepend
    """
    logger.info(f"Writing thermal SPEF: {output_path}")

    with open(output_path, 'w') as f:
        if annotation_comment:
            f.write(f"// {annotation_comment}\n")
            f.write(f"// Generated by thermal_rcx.py\n")
            f.write(f"// Reference T_nom = {T_NOM}°C\n\n")

        for line in lines:
            f.write(line)

    file_size = Path(output_path).stat().st_size
    logger.info(f"  Written {len(lines)} lines ({file_size / 1024:.1f} KB)")


# ---------------------------------------------------------------------------
# Integrated Pipeline
# ---------------------------------------------------------------------------

def process_tier_spef(spef_path: str, thermal_grid_path: str,
                       output_path: str, config_path: str = None,
                       interface_grid_path: str = None,
                       tier: int = 0) -> dict:
    """
    End-to-end processing of a single tier's SPEF file.

    Args:
        spef_path: Input baseline SPEF
        thermal_grid_path: Path to .npz thermal grid
        output_path: Output thermal SPEF path
        config_path: Optional materials.config path
        interface_grid_path: Optional interface thermal grid .npz
        tier: Tier index

    Returns:
        Statistics dict
    """
    logger.info(f"Processing Tier {tier} SPEF: {spef_path}")

    # Load thermal grid
    thermal_grid = load_thermal_grid(thermal_grid_path)

    # Load interface grid if provided
    interface_grid = None
    if interface_grid_path and Path(interface_grid_path).exists():
        interface_grid = load_thermal_grid(interface_grid_path)

    # Load TCR configuration
    tcr_config = TCRConfig(config_path)

    # Parse SPEF
    parser = SPEFParser(spef_path)
    header, nets, raw_lines = parser.parse()

    # Create modifier
    modifier = ThermalSPEFModifier(
        thermal_grid=thermal_grid,
        tcr_config=tcr_config,
        interface_grid=interface_grid,
    )

    # Apply wire resistance scaling
    modified_lines = modifier.modify_spef(header, nets, raw_lines)

    # Apply interface via scaling if applicable
    if interface_grid:
        modified_lines = modifier.scale_interface_vias(
            header, nets, modified_lines
        )

    # Write output
    annotation = (f"Thermal-aware SPEF — Tier {tier}, "
                   f"T range: {modifier.stats['min_t_seg']:.1f}-"
                   f"{modifier.stats['max_t_seg']:.1f}°C")
    write_spef(modified_lines, output_path, annotation_comment=annotation)

    # Report
    report = modifier.get_stats_report()
    logger.info("\n" + report)

    return modifier.stats


# ---------------------------------------------------------------------------
# Self-Test with Synthetic Data
# ---------------------------------------------------------------------------

def run_self_test():
    """
    Run a self-test with synthetic SPEF and temperature data to validate
    TCR scaling math and SPEF round-trip integrity.
    """
    print("=" * 70)
    print("thermal_rcx.py — Self-Test with Synthetic Data")
    print("=" * 70)

    import tempfile

    # Create synthetic thermal grid (hotspot in center)
    grid_size = 16
    temps = np.zeros((grid_size, grid_size))
    for i in range(grid_size):
        for j in range(grid_size):
            cx = (j + 0.5) / grid_size * 2000  # µm
            cy = (i + 0.5) / grid_size * 2000
            dist = np.sqrt((cx - 1000) ** 2 + (cy - 1000) ** 2)
            temps[i, j] = 25.0 + 80.0 * np.exp(-dist / 400)

    thermal_grid = ThermalGrid(
        tier=0, rows=grid_size, cols=grid_size,
        x_min=0, y_min=0, x_max=2000, y_max=2000,
        temperatures=temps,
    )

    print(f"\nSynthetic thermal grid: T_min={np.min(temps):.1f}°C, "
          f"T_max={np.max(temps):.1f}°C")

    # Create synthetic SPEF content
    synth_spef = """*SPEF "IEEE 1481-1998"
*DESIGN "test_design"
*DATE "2024-01-01"
*VENDOR "thermal_rcx_test"
*PROGRAM "thermal_rcx.py"
*DESIGN_FLOW "PIN_CAP NONE"
*DIVIDER /
*DELIMITER :
*BUS_DELIMITER [ ]
*T_UNIT 1 NS
*C_UNIT 1 PF
*R_UNIT 1 OHM
*L_UNIT 1 HENRY

*NAME_MAP
*1 net_a
*2 net_b

*D_NET *1 0.050000
*CONN
*I inst_0:A *C 500.0 500.0
*I inst_1:Z *C 1500.0 1500.0
*CAP
1 inst_0:A 0.025000
2 inst_1:Z 0.025000
*RES
1 inst_0:A inst_1:Z 10.000000
*END

*D_NET *2 0.030000
*CONN
*I inst_2:A *C 200.0 200.0
*I inst_3:Z *C 1000.0 1000.0
*CAP
1 inst_2:A 0.015000
2 inst_3:Z 0.015000
*RES
1 inst_2:A inst_3:Z 5.000000
*END
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write synthetic SPEF
        spef_path = os.path.join(tmpdir, "test.spef")
        with open(spef_path, 'w') as f:
            f.write(synth_spef)

        # Save thermal grid
        grid_path = os.path.join(tmpdir, "thermal_grid.npz")
        from pact_bridge import save_thermal_grid
        save_thermal_grid(thermal_grid, grid_path)

        # Parse SPEF
        parser = SPEFParser(spef_path)
        header, nets, raw_lines = parser.parse()

        print(f"\n✓ Parsed SPEF: {len(nets)} nets")
        assert len(nets) == 2, f"Expected 2 nets, got {len(nets)}"

        # Check resistor extraction
        net1 = nets.get("*1")
        assert net1 is not None, "Net *1 not found"
        assert len(net1.resistors) == 1, f"Expected 1 resistor, got {len(net1.resistors)}"
        assert abs(net1.resistors[0].resistance - 10.0) < 0.001
        print(f"✓ Resistor extraction: R = {net1.resistors[0].resistance:.6f} Ω")

        # Check node coordinate extraction
        assert len(net1.nodes) >= 2, "Expected at least 2 nodes with coords"
        for node_name, node in net1.nodes.items():
            assert node.has_coords, f"Node {node_name} should have coordinates"
        print(f"✓ Node coordinates extracted for {len(net1.nodes)} nodes")

        # Apply TCR scaling
        tcr_config = TCRConfig()  # Defaults
        modifier = ThermalSPEFModifier(thermal_grid, tcr_config)
        modified_lines = modifier.modify_spef(header, nets, raw_lines)

        print(f"✓ Modified {modifier.stats['segments_modified']} segments")

        # Verify TCR math manually for net *1
        # Node1 at (500*scale, 500*scale) and Node2 at (1500*scale, 1500*scale)
        # With DEFAULT_SPEF_COORD_SCALE = 0.001, coords are in µm after scaling
        coord_scale = DEFAULT_SPEF_COORD_SCALE
        x1, y1 = 500.0 * coord_scale, 500.0 * coord_scale  # µm
        x2, y2 = 1500.0 * coord_scale, 1500.0 * coord_scale  # µm
        t1 = thermal_grid.get_temperature(x1, y1)
        t2 = thermal_grid.get_temperature(x2, y2)
        t_seg = (t1 + t2) / 2.0
        expected_ratio = 1.0 + ALPHA_CU * (t_seg - T_NOM)
        expected_r = 10.0 * expected_ratio

        print(f"\n  Manual verification (net *1):")
        print(f"    Node1 coords: ({x1:.3f}, {y1:.3f}) µm -> T = {t1:.2f}°C")
        print(f"    Node2 coords: ({x2:.3f}, {y2:.3f}) µm -> T = {t2:.2f}°C")
        print(f"    T_seg = {t_seg:.2f}°C")
        print(f"    R_ratio = {expected_ratio:.6f}")
        print(f"    R_new = {expected_r:.6f} Ω (from R_nom = 10.0 Ω)")

        # Write output and verify round-trip
        output_path = os.path.join(tmpdir, "test_thermal.spef")
        write_spef(modified_lines, output_path,
                   annotation_comment="Self-test thermal SPEF")

        assert Path(output_path).exists(), "Output SPEF not created"
        with open(output_path) as f:
            output_content = f.read()
        assert "*D_NET" in output_content, "Output missing *D_NET"
        assert "*RES" in output_content, "Output missing *RES"
        print(f"\n✓ SPEF round-trip OK ({Path(output_path).stat().st_size} bytes)")

        print(f"\n{modifier.get_stats_report()}")

    print("\n" + "=" * 70)
    print("All self-tests passed ✓")
    print("=" * 70)


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Thermal-Aware SPEF Modifier (TCR-based R scaling)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run self-test
  python thermal_rcx.py --test

  # Process a single tier SPEF
  python thermal_rcx.py \\
    --spef ariane_tier0.spef \\
    --thermal-grid results/thermal/thermal_grid_tier0.npz \\
    --output ariane_tier0_thermal.spef \\
    --materials-config config/materials.config \\
    --tier 0

  # Process both tiers with interface scaling
  python thermal_rcx.py \\
    --spef ariane_tier0.spef \\
    --thermal-grid results/thermal/thermal_grid_tier0.npz \\
    --interface-grid results/thermal/thermal_grid_interface.npz \\
    --output ariane_tier0_thermal.spef \\
    --tier 0
        """
    )

    parser.add_argument('--test', action='store_true',
                        help='Run self-test with synthetic SPEF data')
    parser.add_argument('--spef', type=str,
                        help='Input baseline SPEF file path')
    parser.add_argument('--thermal-grid', type=str,
                        help='Path to thermal grid .npz file (from pact_bridge)')
    parser.add_argument('--interface-grid', type=str,
                        help='Path to interface thermal grid .npz file')
    parser.add_argument('--output', type=str,
                        help='Output thermal SPEF file path')
    parser.add_argument('--materials-config', type=str, default=None,
                        help='Path to materials.config for TCR values')
    parser.add_argument('--tier', type=int, default=0,
                        help='Tier index (0 or 1, default: 0)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable debug logging')

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S',
    )

    if args.test:
        run_self_test()
        return

    if not args.spef or not args.thermal_grid or not args.output:
        parser.error("--spef, --thermal-grid, and --output are required "
                      "(unless --test is used)")

    stats = process_tier_spef(
        spef_path=args.spef,
        thermal_grid_path=args.thermal_grid,
        output_path=args.output,
        config_path=args.materials_config,
        interface_grid_path=args.interface_grid,
        tier=args.tier,
    )

    # Write stats as JSON for pipeline consumption
    stats_path = args.output.replace('.spef', '_stats.json')
    with open(stats_path, 'w') as f:
        json.dump(stats, f, indent=2)
    logger.info(f"Stats written to {stats_path}")


if __name__ == "__main__":
    main()
