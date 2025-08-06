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
            # Configure all digital I/O bits as outputs
            ul.d_config_port(self.board_num, DigitalPortType.AUXPORT, 1)
            self._hardware_available = True
        except Exception as e:
            print(f"Warning: Digital I/O board {self.board_num} not found. Valve controls will be simulated.")
            self._hardware_available = False

    def _set_valve(self, a_state: int, b_state: int):
        """Set both valve control lines to specified states"""
        if not self._hardware_available:
            return

        try:
            # Set Position B control (DIO1)
            ul.d_bit_out(self.board_num, DigitalPortType.AUXPORT, 1, b_state)
            # Set Position A control (DIO3)
            ul.d_bit_out(self.board_num, DigitalPortType.AUXPORT, 3, a_state)

        except Exception as e:
            print(f"Error setting valve states: {str(e)}")

    def set_valve_position_b(self) -> None:
        if not self._hardware_available:
            print("Simulating valve B open")
            return

        try:
            # Set A high, B low
            self._set_valve(a_state=1, b_state=0)
            print("Valve set to Position B")
        except Exception as e:
            print(f"Error setting valve B: {str(e)}")

    def set_valve_position_a(self) -> None:
        if not self._hardware_available:
            print("Simulating valve A open")
            return

        try:
            # Set B high, A low
            self._set_valve(a_state=0, b_state=1)
            print("Valve set to Position A")
        except Exception as e:
            print(f"Error setting valve A: {str(e)}")

def testValves():
    testValve = Valves()
    testValve.board_num = 0
    ul.d_bit_out(0, DigitalPortType.AUXPORT, 1, 1)
    sleep(5)
    ul.d_bit_out(0, DigitalPortType.AUXPORT, 1, 0)

# Uncomment the line below to run the test
# testValves()