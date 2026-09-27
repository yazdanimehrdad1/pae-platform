"""Asset models (BESS, PV, load). Pure Python: no power flow solver and no clock, so every model
is unit-testable on its own. The simulation core feeds them setpoints, profile values and dt."""
