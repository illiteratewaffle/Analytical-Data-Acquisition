class MFC:
    def __init__(self, name, max_flow):
        self.name = name
        self.max_flow = max_flow

    def flow_to_voltage(self, flow_rate):
        """Convert flow rate to voltage (0-5V scale)"""
        return min(5.0, max(0.0, flow_rate / self.max_flow * 5.0))

    def voltage_to_flow(self, voltage):
        """Convert voltage to flow rate"""
        return voltage / 5.0 * self.max_flow


class MFCManager:
    def __init__(self):
        self.mfcs = {}

    def add_mfc(self, name, max_flow):
        self.mfcs[name] = MFC(name, max_flow)

    def get_mfc(self, name):
        return self.mfcs.get(name)

    def get_all_mfc_names(self):
        return list(self.mfcs.keys())