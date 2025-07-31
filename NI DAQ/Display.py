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
            row=0, column=0, columnspan=4, sticky="w", padx=5
        )

        # MFC selection
        ttk.Label(self, text="MFC Type:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.mfc_var = tk.StringVar()
        self.mfc_dropdown = ttk.Combobox(self, textvariable=self.mfc_var, state="readonly", width=12)
        self.mfc_dropdown['values'] = self.mfc_manager.get_all_mfc_names()
        self.mfc_dropdown.grid(row=1, column=1, padx=5, pady=5, columnspan=3, sticky="w")

        # Set flow section
        ttk.Label(self, text="Set Flow:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.flow_var = tk.StringVar()
        self.flow_entry = ttk.Entry(self, textvariable=self.flow_var, width=8)
        self.flow_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        # Set flow unit display
        self.set_unit_var = tk.StringVar(value="SCCM")
        ttk.Label(self, textvariable=self.set_unit_var, width=6).grid(row=2, column=2, padx=5, pady=5, sticky="w")

        # Set button
        self.set_btn = ttk.Button(self, text="Set", command=self.set_flow, width=6)
        self.set_btn.grid(row=2, column=3, padx=5, pady=5, sticky="w")

        # Actual flow section
        ttk.Label(self, text="Actual Flow:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.actual_flow_var = tk.StringVar(value="0.0")
        ttk.Label(self, textvariable=self.actual_flow_var, width=8).grid(row=3, column=1, padx=5, pady=5, sticky="w")

        # Actual flow unit display
        self.actual_unit_var = tk.StringVar(value="SCCM")
        ttk.Label(self, textvariable=self.actual_unit_var).grid(row=3, column=2, padx=5, pady=5, sticky="w")

        # Scaling information
        self.scaling_info = tk.StringVar()
        ttk.Label(self, textvariable=self.scaling_info, font=("Arial", 8)).grid(
            row=4, column=0, columnspan=4, sticky="w", padx=5
        )

        # Initialize
        if self.mfc_dropdown['values']:
            self.mfc_var.set(self.mfc_dropdown['values'][0])
            self.update_unit_display()
            self.update_scaling_info()

        # Bind MFC selection change
        self.mfc_var.trace_add("write", self.on_mfc_change)

        # Update channel labels
        self.update_channel_info()

    def on_mfc_change(self, *args):
        self.update_unit_display()
        self.update_scaling_info()

    def update_scaling_info(self):
        """Update scaling information display"""
        mfc = self.get_current_mfc()
        if mfc:
            self.scaling_info.set(f"5V = {mfc.max_flow} {mfc.unit}, 0V = 0 {mfc.unit}")

    def update_unit_display(self):
        """Update unit displays based on MFC selection"""
        mfc = self.get_current_mfc()
        if mfc:
            unit = mfc.unit
            self.set_unit_var.set(unit)
            self.actual_unit_var.set(unit)

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
            if not mfc:
                messagebox.showerror("Selection Error", "No MFC selected")
                return

            flow = float(self.flow_var.get())
            voltage = mfc.flow_to_voltage(flow)
            ao_channel = self.channel_config[self.index]['ao']
            self.daq.write_voltage(ao_channel, voltage)
        except (ValueError, AttributeError) as e:
            messagebox.showerror("Input Error", f"Invalid flow value: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to set flow: {str(e)}")

    def update_reading(self):
        try:
            mfc = self.get_current_mfc()
            if not mfc:
                return

            ai_channel = self.channel_config[self.index]['ai']
            voltage = self.daq.read_voltage(ai_channel)
            flow = mfc.voltage_to_flow(voltage)
            self.actual_flow_var.set(f"{flow:.2f}")
        except Exception as e:
            # Fail silently for read errors to avoid spamming
            pass


class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MFC Control System")
        self.geometry("750x550")

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

        # Add available MFCs with output range 5.0V
        self.populate_mfcs()

        # Create menu
        self.create_menu()

        # Create control frames
        self.control_frames = []
        for i in range(4):
            frame = MFCControlFrame(
                self, i, self.daq, self.mfc_manager, self.channel_config,
                text=f"MFC Controller {i + 1}", padx=10, pady=10
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
        # Add all MFC types with output range 5.0V
        mfc_specs = [
            ("30 SLPM", 30, 5.0),
            ("15 SLPM", 15, 5.0),
            ("5 SLPM", 5, 5.0),
            ("1 SLPM", 1, 5.0),
            ("500 SCCM", 500, 5.0),
            ("100 SCCM", 100, 5.0),
            ("20 SCCM", 20, 5.0),
            ("10 SCCM", 10, 5.0)
        ]
        for name, max_flow, output_range in mfc_specs:
            self.mfc_manager.add_mfc(name, max_flow, output_range)

    def update_readings(self):
        for frame in self.control_frames:
            frame.update_reading()
        self.after(self.update_interval, self.update_readings)