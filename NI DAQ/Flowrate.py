class MFC:
    def __init__(self, name, max_flow, output_range=5.0):
        self.name = name
        self.max_flow = max_flow
        self.unit = "SLPM" if "SLPM" in name else "SCCM"
        self.output_range = output_range  # Voltage range for feedback signal

    def flow_to_voltage(self, flow_rate):
        """Convert flow rate to voltage (0-5V scale) based on MFC capacity"""
        if self.max_flow <= 0:
            return 0.0

        # Calculate voltage proportionally to max flow
        voltage = (flow_rate / self.max_flow) * 5.0

        # Clamp between 0-5V to prevent out-of-range errors
        return max(0.0, min(5.0, voltage))

    def voltage_to_flow(self, voltage):
        """Convert voltage to flow rate based on MFC capacity and output range"""
        if self.max_flow <= 0:
            return 0.0
        # Scale based on MFC output range
        raw_value = (voltage / self.output_range) * self.max_flow

        # voltage to flow rate not reading correct values? lets calibrate it.
        calibration_constant = (-0.2681 * self.max_flow) - 0.1454

        calibrated_value = raw_value - calibration_constant

        return calibrated_value

class MFCManager:
    def __init__(self):
        self.mfcs = {}

    def add_mfc(self, name, max_flow, output_range=5.0):
        self.mfcs[name] = MFC(name, max_flow, output_range)

    def get_mfc(self, name):
        return self.mfcs.get(name)

    def get_all_mfc_names(self):
        return list(self.mfcs.keys())