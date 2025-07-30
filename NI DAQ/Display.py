import tkinter as tk
from tkinter import ttk, messagebox, Menu
from Flowrate import MFCManager
from DAQController import DAQController
from ConfigWindow import ConfigWindow


class MFCControlFrame(tk.LabelFrame):
    def __init__(self, parent, index, daq, mfc_manager, channel_config, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.daq = daq
        self.mfc_manager = mfc_manager
        self.index = index
        self.channel_config = channel_config

        # Channel info labels
        self.channel_info = tk.StringVar()
        ttk.Label(self, textvariable=self.channel_info, font=("Arial", 8)).grid(
            row=0, column=0, columnspan=3, sticky="w", padx=5
        )

        # MFC selection
        ttk.Label(self, text="MFC Type:").grid(row=1, column=0, padx=5, pady=5)
        self.mfc_var = tk.StringVar()
        self.mfc_dropdown = ttk.Combobox(self, textvariable=self.mfc_var, state="readonly")
        self.mfc_dropdown['values'] = self.mfc_manager.get_all_mfc_names()
        self.mfc_dropdown.grid(row=1, column=1, padx=5, pady=5)

        # Flow rate control
        ttk.Label(self, text="Set Flow:").grid(row=2, column=0, padx=5, pady=5)
        self.flow_var = tk.StringVar()
        self.flow_entry = ttk.Entry(self, textvariable=self.flow_var)
        self.flow_entry.grid(row=2, column=1, padx=5, pady=5)

        # Set button
        self.set_btn = ttk.Button(self, text="Set", command=self.set_flow)
        self.set_btn.grid(row=2, column=2, padx=5, pady=5)

        # Actual flow display
        ttk.Label(self, text="Actual Flow:").grid(row=3, column=0, padx=5, pady=5)
        self.actual_flow_var = tk.StringVar(value="0.0")
        ttk.Label(self, textvariable=self.actual_flow_var).grid(row=3, column=1, padx=5, pady=5)

        # Unit display
        self.unit_var = tk.StringVar(value="SCCM")
        ttk.Label(self, textvariable=self.unit_var).grid(row=3, column=2, padx=5, pady=5)

        # Initialize
        if self.mfc_dropdown['values']:
            self.mfc_var.set(self.mfc_dropdown['values'][0])
            self.update_unit_display()

        # Bind MFC selection change
        self.mfc_var.trace_add("write", self.on_mfc_change)

        # Update channel labels
        self.update_channel_info()

    def on_mfc_change(self, *args):
        self.update_unit_display()

    def update_unit_display(self):
        """Update unit display based on MFC selection"""
        mfc_name = self.mfc_var.get()
        if "SLPM" in mfc_name:
            self.unit_var.set("SLPM")
        else:
            self.unit_var.set("SCCM")

    def update_channel_info(self):
        """Update channel information display"""
        ao = self.channel_config[self.index]['ao']
        ai = self.channel_config[self.index]['ai']
        self.channel_info.set(f"Output: {ao} | Input: {ai}")

    def get_current_mfc(self):
        return self.mfc_manager.get_mfc(self.mfc_var.get())

    def set_flow(self):
        try:
            mfc = self.get_current_mfc()
            flow = float(self.flow_var.get())
            voltage = mfc.flow_to_voltage(flow)
            ao_channel = self.channel_config[self.index]['ao']
            self.daq.write_voltage(ao_channel, voltage)
        except (ValueError, AttributeError) as e:
            messagebox.showerror("Input Error", f"Invalid flow value: {e}")

    def update_reading(self):
        try:
            mfc = self.get_current_mfc()
            ai_channel = self.channel_config[self.index]['ai']
            voltage = self.daq.read_voltage(ai_channel)
            flow = mfc.voltage_to_flow(voltage)
            self.actual_flow_var.set(f"{flow:.2f}")
        except Exception as e:
            print(f"Read error: {e}")


class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MFC Control System")
        self.geometry("650x450")

        # Initialize managers
        self.mfc_manager = MFCManager()
        self.daq = DAQController()

        # Default channel configuration
        self.channel_config = [
            {'ao': 'ao0', 'ai': 'ai0'},
            {'ao': 'ao1', 'ai': 'ai1'},
            {'ao': 'ao2', 'ai': 'ai2'},
            {'ao': 'ao3', 'ai': 'ai3'}
        ]

        # Add available MFCs
        self.populate_mfcs()

        # Create menu
        self.create_menu()

        # Create control frames
        self.control_frames = []
        for i in range(4):
            frame = MFCControlFrame(
                self, i, self.daq, self.mfc_manager, self.channel_config,
                text=f"MFC Controller {i + 1}"
            )
            frame.grid(row=i // 2, column=i % 2, padx=10, pady=10, sticky="nsew")
            self.control_frames.append(frame)

        # Configure grid weights
        for i in range(2):
            self.rowconfigure(i, weight=1)
            self.columnconfigure(i, weight=1)

        # Setup periodic updates
        self.update_interval = 1000  # ms
        self.update_readings()

    def create_menu(self):
        """Create the menu bar"""
        menubar = Menu(self)

        config_menu = Menu(menubar, tearoff=0)
        config_menu.add_command(label="Device Configuration", command=self.open_config)
        menubar.add_cascade(label="Configuration", menu=config_menu)

        self.config(menu=menubar)

    def open_config(self):
        """Open the configuration window"""
        ConfigWindow(self, self.daq, self.channel_config)

    def update_channel_labels(self):
        """Update channel info in all control frames"""
        for frame in self.control_frames:
            frame.update_channel_info()

    def populate_mfcs(self):
        # Add all MFC types
        mfc_specs = [
            ("30 SLPM", 30),
            ("15 SLPM", 15),
            ("5 SLPM", 5),
            ("1 SLPM", 1),
            ("500 SCCM", 500),
            ("100 SCCM", 100),
            ("20 SCCM", 20),
            ("10 SCCM", 10)
        ]
        for name, max_flow in mfc_specs:
            self.mfc_manager.add_mfc(name, max_flow)

    def update_readings(self):
        for frame in self.control_frames:
            frame.update_reading()
        self.after(self.update_interval, self.update_readings)