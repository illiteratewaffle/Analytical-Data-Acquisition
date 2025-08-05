import tkinter as tk
from tkinter import ttk, messagebox, Menu
import time
from datetime import datetime, timedelta
from Flowrate import MFCManager
from DAQController import DAQController
from ConfigWindow import ConfigWindow
from ValveControlFrame import ValveControlFrame
from ValveScheduler import ValveScheduler


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


class ScheduledRunTab(ttk.Frame):
    def __init__(self, parent, daq, valve_config, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.daq = daq
        self.valve_config = valve_config
        self.swap_job_ids = []
        self.recording = False
        self.auto_run_job = None
        self.next_run_time = None
        self.position_job = None

        # Configure grid for columns
        for i in range(4):
            self.columnconfigure(i, weight=1, uniform="valve_cols")

        # Valve position display (top)
        self.position_frame = ttk.LabelFrame(self, text="Current Valve Positions")
        self.position_frame.grid(row=0, column=0, columnspan=4, sticky="we", padx=5, pady=5)

        self.valve_position_vars = []
        for i in range(4):
            frame = ttk.Frame(self.position_frame)
            frame.pack(side=tk.LEFT, padx=10, pady=5)
            ttk.Label(frame, text=f"Valve {i + 1}:").pack(side=tk.LEFT)
            pos_var = tk.StringVar(value="OFF")
            ttk.Label(frame, textvariable=pos_var, width=5).pack(side=tk.LEFT)
            self.valve_position_vars.append(pos_var)

        # Run controls frame (middle)
        self.control_frame = ttk.LabelFrame(self, text="Run Controls", padding=10)
        self.control_frame.grid(row=1, column=0, columnspan=4, sticky="we", padx=5, pady=10)

        # Run duration
        ttk.Label(self.control_frame, text="Run Duration (s):").grid(row=0, column=0, padx=(0, 5))
        self.duration_var = tk.StringVar(value="60")
        ttk.Entry(self.control_frame, width=8, textvariable=self.duration_var).grid(row=0, column=1)

        # Start/Stop buttons
        self.start_btn = ttk.Button(self.control_frame, text="Start Run", command=self.start_recording)
        self.start_btn.grid(row=0, column=2, padx=10)

        self.stop_btn = ttk.Button(self.control_frame, text="Stop Run", command=self.stop_recording, state="disabled")
        self.stop_btn.grid(row=0, column=3)

        # Auto-run controls
        auto_frame = ttk.Frame(self.control_frame)
        auto_frame.grid(row=0, column=4, padx=(20, 0))

        self.auto_run_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(auto_frame, text="Auto-run every", variable=self.auto_run_var,
                        command=self.toggle_auto_run).pack(side=tk.LEFT)

        self.interval_var = tk.StringVar(value="300")
        ttk.Entry(auto_frame, width=5, textvariable=self.interval_var).pack(side=tk.LEFT, padx=5)
        ttk.Label(auto_frame, text="seconds").pack(side=tk.LEFT)

        self.next_run_var = tk.StringVar(value="Next run: --:--:--")
        ttk.Label(auto_frame, textvariable=self.next_run_var).pack(side=tk.LEFT, padx=(10, 0))

        # Valve schedulers (bottom)
        self.valve_schedulers = []
        for i in range(4):
            scheduler = ValveScheduler(
                self, i, daq, valve_config,
                padding=10,
                relief="groove"
            )
            scheduler.grid(row=2, column=i, padx=5, pady=5, sticky="nsew")
            self.valve_schedulers.append(scheduler)

    def toggle_auto_run(self):
        if self.auto_run_var.get():
            self.start_auto_run_scheduler()
        elif self.auto_run_job:
            self.master.after_cancel(self.auto_run_job)
            self.auto_run_job = None
            self.next_run_time = None
            self.next_run_var.set("Next run: --:--:--")

    def calculate_next_run(self):
        """Calculate next run time at exact second interval."""
        now = datetime.now()
        try:
            interval_seconds = int(self.interval_var.get())
        except ValueError:
            interval_seconds = 300

        current_seconds = now.hour * 3600 + now.minute * 60 + now.second
        remainder = current_seconds % interval_seconds

        if remainder == 0:
            next_seconds = current_seconds
        else:
            next_seconds = current_seconds + interval_seconds - remainder

        next_hour = next_seconds // 3600
        next_minute = (next_seconds % 3600) // 60
        next_second = next_seconds % 60

        next_run = now.replace(hour=next_hour, minute=next_minute,
                               second=next_second, microsecond=0)

        if next_hour >= 24:
            next_run = next_run + timedelta(days=1)

        return next_run

    def start_auto_run_scheduler(self):
        if not self.auto_run_var.get():
            return

        self.next_run_time = self.calculate_next_run()
        self.next_run_var.set(f"Next run: {self.next_run_time.strftime('%H:%M:%S')}")

        now = datetime.now()
        delay_ms = int((self.next_run_time - now).total_seconds() * 1000)

        if self.auto_run_job:
            self.master.after_cancel(self.auto_run_job)
        self.auto_run_job = self.master.after(delay_ms, self.execute_auto_run)

    def execute_auto_run(self):
        if not self.auto_run_var.get():
            return

        self.start_recording()
        self.auto_run_job = self.master.after(
            int(self.interval_var.get()) * 1000,
            self.start_auto_run_scheduler
        )

    def start_recording(self):
        if self.recording:
            return

        self.recording = True
        self.start_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        # Set initial states for all valves
        for scheduler in self.valve_schedulers:
            scheduler.set_initial_state()

        # Schedule valve swaps
        for scheduler in self.valve_schedulers:
            scheduler.schedule_actions(self.master)

        # Schedule run end
        try:
            duration = float(self.duration_var.get())
            job_id = self.master.after(
                int(duration * 1000),
                self.stop_recording
            )
            self.swap_job_ids.append(job_id)
        except ValueError:
            messagebox.showerror("Invalid Duration", "Please enter a valid number for run duration")

        # Start updating valve positions
        self.update_valve_positions()

    def update_valve_positions(self):
        """Update valve position display"""
        for i, scheduler in enumerate(self.valve_schedulers):
            self.valve_position_vars[i].set("ON" if scheduler.current_state else "OFF")

        # Continue updating if recording
        if self.recording:
            self.position_job = self.after(500, self.update_valve_positions)

    def stop_recording(self):
        if not self.recording:
            return

        self.recording = False

        # Cancel all swap jobs
        for job_id in self.swap_job_ids:
            self.master.after_cancel(job_id)
        self.swap_job_ids = []

        # Cancel valve schedules
        for scheduler in self.valve_schedulers:
            scheduler.cancel_schedules()
            scheduler.turn_off()

        # Cancel position updates
        if self.position_job:
            self.after_cancel(self.position_job)

        self.start_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

        # Final position update
        self.update_valve_positions()


class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MFC & Valve Control System")
        self.geometry("1000x700")

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

        # Default valve configuration
        self.valve_config = [
            {"name": "Valve 1", "port_line": "port1/line0"},
            {"name": "Valve 2", "port_line": "port1/line1"},
            {"name": "Valve 3", "port_line": "port1/line2"},
            {"name": "Valve 4", "port_line": "port1/line3"},
        ]

        # Add available MFCs with output range 5.0V
        self.populate_mfcs()

        # Create menu
        self.create_menu()

        # Create notebook (tabs)
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)

        # Tab 1: MFC Control
        self.mfc_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.mfc_tab, text="MFC Control")

        # Create MFC control frames
        self.control_frames = []
        for i in range(4):
            frame = MFCControlFrame(
                self.mfc_tab, i, self.daq, self.mfc_manager, self.channel_config,
                text=f"MFC Controller {i + 1}", padx=10, pady=10
            )
            frame.grid(row=i // 2, column=i % 2, padx=10, pady=10, sticky="nsew")
            self.control_frames.append(frame)

        # Configure grid weights for MFC tab
        for i in range(2):
            self.mfc_tab.rowconfigure(i, weight=1)
            self.mfc_tab.columnconfigure(i, weight=1)

        # Tab 2: Valve Control
        self.valve_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.valve_tab, text="Valve Control")

        # Create valve control frame
        self.valve_frame = ValveControlFrame(
            self.valve_tab, self.daq, self.valve_config,
            text="Manual Valve Controls", padx=20, pady=20
        )
        self.valve_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Tab 3: Scheduled Runs
        self.schedule_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.schedule_tab, text="Scheduled Runs")

        # Create scheduled run frame
        self.schedule_frame = ScheduledRunTab(
            self.schedule_tab, self.daq, self.valve_config,
            padding=10
        )
        self.schedule_frame.pack(fill='both', expand=True)

        # Setup periodic updates for MFC readings
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
        ConfigWindow(self, self.daq, self.channel_config, self.valve_config)

    def update_channel_labels(self):
        """Update channel info in all control frames"""
        for frame in self.control_frames:
            frame.update_channel_info()

    def update_valve_config(self):
        """Update valve configuration in frames"""
        self.valve_frame.update_valve_ports()
        self.schedule_frame.valve_config = self.valve_config
        for i, scheduler in enumerate(self.schedule_frame.valve_schedulers):
            scheduler.port_line = self.valve_config[i]['port_line']

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