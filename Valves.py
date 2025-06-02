from mcculw import ul
from mcculw.enums import DigitalPortType
from time import sleep

class Valves:
    def __init__(self):
        self.board_num = 0
        # Configure both channels as output
        ul.d_config_port(self.board_num, DigitalPortType.FIRSTPORTA, 1)

    # Function to switch to Position A
    def set_valve_position_a(self) -> None:
        for bit in range(8):
            ul.d_bit_out(self.board_num, DigitalPortType.FIRSTPORTA, bit, 1)
        ul.d_bit_out(self.board_num, DigitalPortType.FIRSTPORTA, 0, 0)

    # Function to switch to Position B
    def set_valve_position_b(self) -> None:
        for bit in range(8):
            ul.d_bit_out(self.board_num, DigitalPortType.FIRSTPORTA, bit, 1)
        ul.d_bit_out(self.board_num, DigitalPortType.FIRSTPORTA, 1, 0)

# Enable this to test valves
# def testValves():
#     testValve = Valves()
#     testValve.set_valve_position_a()
#     sleep(3)
#     testValve.set_valve_position_b()
# testValves()