from mcculw import ul
from mcculw.enums import DigitalPortType
from time import sleep

from Settings import settings

class Valves:
    def __init__(self):
        self.board_num = settings.dio_board_number
        self._hardware_available = False

        try:
            # Try to access the board to verify it exists
            ul.get_board_name(self.board_num)
            ul.d_config_port(self.board_num, DigitalPortType.FIRSTPORTA, 1)
            self._hardware_available = True
        except Exception as e:
            print(f"Warning: Digital I/O board {self.board_num} not found. Valve controls will be simulated.")
            self._hardware_available = False

    # Function to switch to Position A
    def set_valve_position_a(self) -> None:
        if not self._hardware_available:
            print("Simulating valve A open")
            return

        try:
            for bit in range(8):
                ul.d_bit_out(self.board_num, DigitalPortType.FIRSTPORTA, bit, 1)
            ul.d_bit_out(self.board_num, DigitalPortType.FIRSTPORTA, 0, 0)
        except Exception as e:
            print(f"Error setting valve A: {str(e)}")

    # Function to switch to Position B
    def set_valve_position_b(self) -> None:
        if not self._hardware_available:
            print("Simulating valve B open")
            return

        try:
            for bit in range(8):
                ul.d_bit_out(self.board_num, DigitalPortType.FIRSTPORTA, bit, 1)
            ul.d_bit_out(self.board_num, DigitalPortType.FIRSTPORTA, 1, 0)
        except Exception as e:
            print(f"Error setting valve B: {str(e)}")

# Enable this to test valves
# def testValves():
#     testValve = Valves()
#     testValve.set_valve_position_a()
#     sleep(3)
#     testValve.set_valve_position_b()
# testValves()