-- The per-asset Modbus maps are retired: the Modbus server serves the PAE point standard layout
-- (powerflow.point_standard), so nothing read this table.
DROP TABLE IF EXISTS modbus_maps;
