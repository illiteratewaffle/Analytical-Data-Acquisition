import nidaqmx


class DAQController:
    # DEFAULT DEVICE IS Dev1
    def __init__(self, device_name="Dev1"):
        self.device_name = device_name

    def set_device_name(self, device_name):
        self.device_name = device_name

    def write_voltage(self, channel, voltage):
        """Write voltage to analog output channel"""
        with nidaqmx.Task() as task:
            task.ao_channels.add_ao_voltage_chan(f"{self.device_name}/{channel}")
            task.write(voltage)

    def read_voltage(self, channel):
        """Read voltage from analog input channel"""
        with nidaqmx.Task() as task:
            task.ai_channels.add_ai_voltage_chan(f"{self.device_name}/{channel}")
            return task.read()