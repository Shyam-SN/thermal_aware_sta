# =============================================================================
# Makefile — Thermal-Aware Pin-3D OpenROAD Framework
#
# Master build and execution flow for the electro-thermal optimization
# framework targeting Ariane-136 on NanGate45.
#
# Usage:
#   make run_thermal_pin3d DESIGN=ariane136         # Full flow
#   make run_thermal_pin3d DESIGN=ariane136 DRY_RUN=1  # Dry-run (no design files)
#   make test                                       # Run unit tests
#   make clean                                      # Clean all outputs
#
# =============================================================================

# ---------------------------------------------------------------------------
# Configuration Variables
# ---------------------------------------------------------------------------

# Design
DESIGN          ?= ariane136
NUM_TIERS       ?= 2
CLK_FREQ        ?= 500       # MHz

# Tool paths
PYTHON          ?= python3
OPENROAD        ?= /Users/prathima/OpenROAD/build/bin/openroad
OPENSTA         ?= sta
PACT_HOME       ?= $(shell echo $$PACT_HOME)

# Project directories
PROJECT_ROOT    := $(shell pwd)
SCRIPTS_DIR     := $(PROJECT_ROOT)/scripts
CONFIG_DIR      := $(PROJECT_ROOT)/config
PDK_DIR         ?= $(PROJECT_ROOT)/../platforms/nangate45_3D
DESIGNS_DIR     ?= $(PROJECT_ROOT)/../designs/nangate45_3D/$(DESIGN)
RESULTS_DIR     := $(PROJECT_ROOT)/results
REPORTS_DIR     := $(RESULTS_DIR)/reports
FIGURES_DIR     := $(RESULTS_DIR)/figures
THERMAL_DIR     := $(RESULTS_DIR)/thermal

# Design files
TIER0_DEF       ?= $(RESULTS_DIR)/ariane_routed_flat.def
TIER1_DEF       ?= $(RESULTS_DIR)/ariane_routed_flat.def
TIER0_SPEF      ?= $(RESULTS_DIR)/ariane_routed_flat.spef
TIER1_SPEF      ?= $(RESULTS_DIR)/ariane_routed_flat.spef
SDC_PATH        ?= $(DESIGNS_DIR)/ariane.sdc
LEF_PATH        ?= $(PDK_DIR)/NangateOpenCellLibrary.lef
LIB_PATH        ?= $(PDK_DIR)/NangateOpenCellLibrary_typical.lib

# Convergence parameters
MAX_ITERATIONS  ?= 4
CONV_DT         ?= 0.5       # °C
CONV_DWNS       ?= 5.0       # ps
GRID_SIZE       ?= 64

# Dry-run mode (set DRY_RUN=1 to enable)
DRY_RUN         ?= 0
DRY_RUN_FLAG    := $(if $(filter 1,$(DRY_RUN)),--dry-run,)

# P&R execution control
FORCE_PNR       ?= 0
FORCE_PNR_FLAG  := $(if $(filter 1,$(FORCE_PNR)),--force-pnr,)
SKIP_PNR        ?= 0
SKIP_PNR_FLAG   := $(if $(filter 1,$(SKIP_PNR)),--skip-pnr,)

# Verbosity
VERBOSE         ?= 0
VERBOSE_FLAG    := $(if $(filter 1,$(VERBOSE)),-v,)

# Timestamp for log files
TIMESTAMP       := $(shell date +%Y%m%d_%H%M%S)


# ---------------------------------------------------------------------------
# Phony Targets
# ---------------------------------------------------------------------------

.PHONY: all run_thermal_pin3d run_full_benchmark test test_pact test_rcx dry_run \
        plot visualizer_3d compare report_html benchmark_ab thermal_place all_reports \
        clean clean_results clean_thermal help dirs

# Default target
all: run_thermal_pin3d


# ---------------------------------------------------------------------------
# Main Execution Target
# ---------------------------------------------------------------------------

run_thermal_pin3d: dirs
	@echo "============================================================"
	@echo "  Thermal-Aware Pin-3D Flow — $(DESIGN)"
	@echo "  $(TIMESTAMP)"
	@echo "============================================================"
	$(PYTHON) $(SCRIPTS_DIR)/flow_pin3d_thermal.py \
		--design $(DESIGN) \
		--tier0-def $(TIER0_DEF) \
		--tier1-def $(TIER1_DEF) \
		--tier0-spef $(TIER0_SPEF) \
		--tier1-spef $(TIER1_SPEF) \
		--sdc $(SDC_PATH) \
		--config-dir $(CONFIG_DIR) \
		--results-dir $(RESULTS_DIR) \
		--pdk-dir $(PDK_DIR) \
		--grid-size $(GRID_SIZE) \
		--max-iter $(MAX_ITERATIONS) \
		--conv-dt $(CONV_DT) \
		--conv-dwns $(CONV_DWNS) \
		$(DRY_RUN_FLAG) \
		$(FORCE_PNR_FLAG) \
		$(SKIP_PNR_FLAG) \
		$(VERBOSE_FLAG) \
		2>&1 | tee $(REPORTS_DIR)/flow_$(DESIGN)_$(TIMESTAMP).log
	@echo ""
	@echo "Flow complete. Results in: $(RESULTS_DIR)/"


# ---------------------------------------------------------------------------
# Dry-Run Target (convenience alias)
# ---------------------------------------------------------------------------

dry_run: dirs
	@echo "============================================================"
	@echo "  DRY RUN — Thermal-Aware Pin-3D Flow"
	@echo "============================================================"
	$(PYTHON) $(SCRIPTS_DIR)/flow_pin3d_thermal.py \
		--design $(DESIGN) \
		--config-dir $(CONFIG_DIR) \
		--results-dir $(RESULTS_DIR) \
		--grid-size $(GRID_SIZE) \
		--max-iter $(MAX_ITERATIONS) \
		--conv-dt $(CONV_DT) \
		--conv-dwns $(CONV_DWNS) \
		--dry-run \
		$(VERBOSE_FLAG) \
		2>&1 | tee $(REPORTS_DIR)/dry_run_$(TIMESTAMP).log


# ---------------------------------------------------------------------------
# Individual Stage Targets
# ---------------------------------------------------------------------------

# Stage 1: Generate PACT inputs from DEF/power
pact_inputs: dirs
	$(PYTHON) $(SCRIPTS_DIR)/pact_bridge.py \
		--tier0-def $(TIER0_DEF) \
		--tier1-def $(TIER1_DEF) \
		--lef $(LEF_PATH) \
		--power-report $(REPORTS_DIR)/power_instance.rpt \
		--config-dir $(CONFIG_DIR) \
		--work-dir $(THERMAL_DIR) \
		--grid-size $(GRID_SIZE) \
		$(VERBOSE_FLAG)

# Stage 2: Run PACT thermal solver
pact_solve: pact_inputs
	$(PYTHON) $(SCRIPTS_DIR)/pact_bridge.py \
		--tier0-def $(TIER0_DEF) \
		--tier1-def $(TIER1_DEF) \
		--power-report $(REPORTS_DIR)/power_instance.rpt \
		--config-dir $(CONFIG_DIR) \
		--work-dir $(THERMAL_DIR) \
		--grid-size $(GRID_SIZE) \
		--run-solver \
		$(VERBOSE_FLAG)

# Stage 3: Apply thermal SPEF modification
thermal_rcx: dirs
	@for tier in 0 1; do \
		echo "Processing Tier $$tier SPEF..."; \
		$(PYTHON) $(SCRIPTS_DIR)/thermal_rcx.py \
			--spef $(THERMAL_DIR)/ariane_tier$${tier}.spef \
			--thermal-grid $(THERMAL_DIR)/thermal_grid_tier$${tier}.npz \
			--interface-grid $(THERMAL_DIR)/thermal_grid_interface.npz \
			--output $(THERMAL_DIR)/ariane_tier$${tier}_thermal.spef \
			--materials-config $(CONFIG_DIR)/materials.config \
			--tier $$tier \
			$(VERBOSE_FLAG); \
	done

# Stage 4: Run STA with thermal SPEF
sta_3d: dirs
	$(OPENROAD) -exit $(SCRIPTS_DIR)/run_sta_3d.tcl \
		-log $(REPORTS_DIR)/sta_3d_$(TIMESTAMP).log

# Stage 5: Generate plots
plot: dirs
	$(PYTHON) $(SCRIPTS_DIR)/plot_heatmaps.py \
		--tier0-grid $(THERMAL_DIR)/thermal_grid_tier0.npz \
		--tier1-grid $(THERMAL_DIR)/thermal_grid_tier1.npz \
		--interface-grid $(THERMAL_DIR)/thermal_grid_interface.npz \
		--metrics-dir $(REPORTS_DIR) \
		--output-dir $(FIGURES_DIR) \
		--dashboard \
		$(VERBOSE_FLAG)

# Stage 6: Interactive 3D Web Visualizer
visualizer_3d: dirs
	$(PYTHON) $(SCRIPTS_DIR)/plot_3d_interactive.py \
		--tier0-grid $(THERMAL_DIR)/thermal_grid_tier0.npz \
		--tier1-grid $(THERMAL_DIR)/thermal_grid_tier1.npz \
		--interface-grid $(THERMAL_DIR)/thermal_grid_interface.npz \
		--output $(FIGURES_DIR)/thermal_3d_interactive.html

# Stage 7: 3-Way Benchmark Comparison
compare: dirs
	$(PYTHON) $(SCRIPTS_DIR)/compare_benchmarks.py \
		--final-summary $(REPORTS_DIR)/final_summary.json \
		--results-dir $(RESULTS_DIR)

# Stage 8: Executive Sign-off HTML Report
report_html: dirs
	$(PYTHON) $(SCRIPTS_DIR)/generate_signoff_report.py \
		--final-summary $(REPORTS_DIR)/final_summary.json \
		--benchmark-json $(REPORTS_DIR)/benchmark_comparison.json \
		--output $(REPORTS_DIR)/signoff_report.html

# Stage 9: Direct A/B Benchmark (With Thermal vs. Without Thermal)
benchmark_ab: dirs
	$(PYTHON) $(SCRIPTS_DIR)/benchmark_thermal_vs_nonthermal.py \
		--results-dir $(RESULTS_DIR)

# Stage 10: Thermal-Aware 3D Placement Optimization (TAP)
thermal_place: dirs
	@echo "--- 1. Generating Thermal-Aware Relocated Placement ---"
	$(PYTHON) $(SCRIPTS_DIR)/thermal_place_opt.py \
		--input-def $(RESULTS_DIR)/ariane_routed_flat.def \
		--power-rpt $(REPORTS_DIR)/power_instance_iter0.rpt \
		--output-def $(RESULTS_DIR)/ariane_thermal_placed.def
	@echo "--- 2. Legalizing & Routing Thermal Placement in OpenROAD ---"
	$(OPENROAD) -exit $(SCRIPTS_DIR)/run_thermal_placement.tcl
	@echo "--- 3. Running Closed-Loop Thermal-Aware Sign-off on TAP Design ---"
	$(PYTHON) $(SCRIPTS_DIR)/flow_pin3d_thermal.py \
		--design $(DESIGN) \
		--tier0-def $(RESULTS_DIR)/ariane_thermal_legalized.def \
		--tier1-def $(RESULTS_DIR)/ariane_thermal_legalized.def \
		--tier0-spef $(RESULTS_DIR)/ariane_thermal_routed.spef \
		--tier1-spef $(RESULTS_DIR)/ariane_thermal_routed.spef \
		--sdc $(SDC_PATH) \
		--config-dir $(CONFIG_DIR) \
		--results-dir $(RESULTS_DIR) \
		--pdk-dir $(PDK_DIR) \
		--grid-size $(GRID_SIZE) \
		--max-iter $(MAX_ITERATIONS) \
		--conv-dt $(CONV_DT) \
		--conv-dwns $(CONV_DWNS) \
		--skip-pnr \
		$(VERBOSE_FLAG)
	@echo "--- 4. Evaluating Hotspot & Thermal Gradient Reduction ---"
	$(PYTHON) $(SCRIPTS_DIR)/compare_placement_thermal.py \
		--results-dir $(RESULTS_DIR)

# Generate All Reports & Visuals
all_reports: plot visualizer_3d compare report_html benchmark_ab

# Master Target: Run Full 3D P&R + Thermal Flow + Thermal-Aware Placement + Non-Thermal A/B + 3-Way Benchmark + 3D Visualizer + Executive HTML Report
run_full_benchmark: dirs
	@echo "============================================================"
	@echo "  STARTING FULL 3D P&R + THERMAL FLOW & TAP BENCHMARK"
	@echo "============================================================"
	$(MAKE) run_thermal_pin3d FORCE_PNR=1
	$(MAKE) thermal_place
	$(MAKE) all_reports
	@echo ""
	@echo "============================================================"
	@echo "  COMPLETE ELECTRO-THERMAL BENCHMARK & SIGN-OFF COMPLETE ✓"
	@echo "============================================================"
	@echo "  - Executive HTML Report:    $(REPORTS_DIR)/signoff_report.html"
	@echo "  - Interactive 3D Web App:   $(FIGURES_DIR)/thermal_3d_interactive.html"
	@echo "  - TAP Placement Heatmap:    $(FIGURES_DIR)/placement_thermal_reduction.png"
	@echo "  - A/B Benchmark Plot:       $(FIGURES_DIR)/thermal_vs_nonthermal_comparison.png"
	@echo "  - 3-Way Benchmark Plot:     $(FIGURES_DIR)/benchmark_comparison.png"
	@echo "  - Comprehensive Dashboard:  $(FIGURES_DIR)/dashboard.png"
	@echo "============================================================"
	@echo "  - Comprehensive Dashboard:  $(FIGURES_DIR)/dashboard.png"
	@echo "============================================================"


# ---------------------------------------------------------------------------
# Testing Targets
# ---------------------------------------------------------------------------

test: test_pact test_rcx
	@echo ""
	@echo "============================================================"
	@echo "  All tests passed ✓"
	@echo "============================================================"

test_pact:
	@echo "--- Testing pact_bridge.py ---"
	$(PYTHON) $(SCRIPTS_DIR)/pact_bridge.py --test

test_rcx:
	@echo "--- Testing thermal_rcx.py ---"
	$(PYTHON) $(SCRIPTS_DIR)/thermal_rcx.py --test


# ---------------------------------------------------------------------------
# Directory Creation
# ---------------------------------------------------------------------------

dirs:
	@mkdir -p $(REPORTS_DIR) $(FIGURES_DIR) $(THERMAL_DIR)


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

clean: clean_results
	@echo "Cleaned all outputs."

clean_results:
	rm -rf $(RESULTS_DIR)/reports/*.rpt
	rm -rf $(RESULTS_DIR)/reports/*.json
	rm -rf $(RESULTS_DIR)/reports/*.log
	rm -rf $(RESULTS_DIR)/reports/*.tcl
	rm -rf $(RESULTS_DIR)/figures/*
	rm -rf $(RESULTS_DIR)/thermal/iter*
	rm -rf $(RESULTS_DIR)/thermal/*.npz
	rm -rf $(RESULTS_DIR)/thermal/*.spef

clean_thermal:
	rm -rf $(THERMAL_DIR)/iter*
	rm -rf $(THERMAL_DIR)/*.npz


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

help:
	@echo "============================================================"
	@echo "  Thermal-Aware Pin-3D OpenROAD Framework"
	@echo "============================================================"
	@echo ""
	@echo "Main targets:"
	@echo "  make run_thermal_pin3d    Full electro-thermal flow"
	@echo "  make dry_run              Dry-run with synthetic data"
	@echo "  make test                 Run all unit tests"
	@echo "  make plot                 Generate visualization plots"
	@echo "  make clean                Clean all outputs"
	@echo "  make help                 Show this help"
	@echo ""
	@echo "Individual stages:"
	@echo "  make pact_inputs          Generate PACT input files"
	@echo "  make pact_solve           Run PACT thermal solver"
	@echo "  make thermal_rcx          Apply thermal SPEF modification"
	@echo "  make sta_3d               Run 3D STA timing analysis"
	@echo ""
	@echo "Variables:"
	@echo "  DESIGN=<name>             Design name (default: ariane136)"
	@echo "  DRY_RUN=1                 Enable dry-run mode"
	@echo "  VERBOSE=1                 Enable verbose logging"
	@echo "  MAX_ITERATIONS=<N>        Max convergence iters (default: 4)"
	@echo "  CONV_DT=<°C>             ΔT threshold (default: 0.5)"
	@echo "  CONV_DWNS=<ps>            ΔWNS threshold (default: 5.0)"
	@echo "  GRID_SIZE=<N>             Thermal grid NxN (default: 64)"
	@echo "  PACT_HOME=<path>          PACT installation directory"
	@echo ""
	@echo "Example:"
	@echo "  make run_thermal_pin3d DESIGN=ariane136 DRY_RUN=1"
	@echo ""
