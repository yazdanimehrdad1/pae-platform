#This class takes a modbus client and will define series of function that base on the functions input do different types of polling and return raw modbus points

from services.modbus.client import ModbusClient


class ModbusUtils:
    def __init__(self, modbus_client: ModbusClient):
        self.modbus_client = modbus_client


    def read_holding_registers(self, address: int, count: int, server_id: int, host: str, port: int) -> list[int | bool]:
        return self.modbus_client.read_registers(kind="holding", address=address, count=count, server_id=server_id, host=host, port=port)

    def read_input_registers(self, address: int, count: int, server_id: int, host: str, port: int) -> list[int | bool]:
        return self.modbus_client.read_registers(kind="input", address=address, count=count, server_id=server_id, host=host, port=port)

    def read_coils(self, address: int, count: int, server_id: int, host: str, port: int) -> list[int | bool]:
        return self.modbus_client.read_registers(kind="coils", address=address, count=count, server_id=server_id, host=host, port=port)
