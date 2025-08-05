import nidaqmx

class DAQController:
    def __init__(self, device_name="Dev4"):
        self.device_name = device_name

    def set_device_name(self, device_name):
        self.device_name = device_name

    def write_voltage(self, channel, voltage):
        """Write voltage to analog output channel (clamped to 0-5V)"""
        clamped_voltage = max(0.0, min(5.0, voltage))

        with nidaqmx.Task() as task:
            task.ao_channels.add_ao_voltage_chan(
                f"{self.device_name}/{channel}",
                min_val=0.0,
                max_val=5.0
            )
            task.write(clamped_voltage)

    def read_voltage(self, channel):
        """Read voltage from analog input channel"""
        with nidaqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan(f"{self.device_name}/{channel}")
            return task.read()

    def write_digital(self, port_line, state):
        """Write digital output (on/off) to a specific port/line"""
        with nidaqmx.Task() as task:
            task.do_channels.add_do_chan(f"{self.device_name}/{port_line}")
            task.write(bool(state))