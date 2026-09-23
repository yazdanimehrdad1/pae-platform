"""
Fixed protocol and domain constants.

These values are not env-driven and should not be in config.py.
Runtime-configurable values (host, port, TTL, timeouts) belong in config.py.
"""

# Modbus Application Protocol spec: max registers per PDU read request
MODBUS_MAX_REGISTERS_PER_READ = 125
