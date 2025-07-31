import time
import queue
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import math

import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

from DataAcquisition import DataAcquisition
from Valves import Valves
from Settings import settings


class Display:
    """Real-time GUI with variable valve-swap schedules, X/Y autoscaling, and auto-run."""

    OPEN_CLR = "#90EE90"
    CLOSED_CLR = "#D3D3D3"

    # ──────────────────────────────────────────────────────────
    #  Construction
    # ──────────────────────────────────────────────────────────
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Real-Time Signal Monitor")

        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create control tab
        self.control_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.control_tab, text="Control")

        # Create config tab
        self.config_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.config_tab, text="Configuration")

        self.daq = DataAcquisition()
        self.dataQueue = queue.Queue()
        self.daq.attach_queue(self.dataQueue)

        self.blockMS = max(
            1,
            round(1000 * self.daq.blockSize / self.daq.samplingFrequency),
        )

        # Run-state
        self.recording = False
        self.maxDuration = settings.effective_run_duration
        self.currentValve = "A"
        self.swap_job_ids = []  # List to store all swap job IDs

        # Auto-run state
        self.auto_run_job = None
        self.next_run_time = None

        # Initialize valves after settings
        self.valves = Valves()
        if not hasattr(self.daq, '_hardware_available') or not self.daq._hardware_available:
            messagebox.showwarning("Hardware Not Found",
                                   f"Analog input board {settings.ai_board_number} not found. Running in simulation mode.")

        if not hasattr(self.valves, '_hardware_available') or not self.valves._hardware_available:
            messagebox.showwarning("Hardware Not Found",
                                   f"Digital I/O board {settings.dio_board_number} not found. Valve controls will be simulated.")

        # Build GUI
        self._build_widgets()

        self.jobId = self.root.after(self.blockMS, self.updateLoop)
        self.root.protocol("WM_DELETE_WINDOW", self.closeWindow)

        # Start auto-run scheduler if enabled
        if settings.auto_run:
            self._start_auto_run_scheduler()

    # ──────────────────────────────────────────────────────────
    #  GUI layout
    # ──────────────────────────────────────────────────────────
    def _build_widgets(self):
        # Build configuration tab first
        self._build_config_tab()

        # Build control tab
        self._build_control_tab()

    def _build_config_tab(self):
        """Build the configuration tab"""
        config_frm = ttk.LabelFrame(self.config_tab, text="Board Configuration", padding=10)
        config_frm.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # AI Board
        ai_frm = ttk.Frame(config_frm)
        ai_frm.pack(fill=tk.X, pady=5)
        ttk.Label(ai_frm, text="AI Board Number:").pack(side=tk.LEFT, padx=(0, 10))
        self.ai_board_var = tk.IntVar(value=settings.ai_board_number)
        ai_board_spin = ttk.Spinbox(ai_frm, from_=0, to=15, width=5,
                                    textvariable=self.ai_board_var)
        ai_board_spin.pack(side=tk.LEFT)

        # DIO Board
        dio_frm = ttk.Frame(config_frm)
        dio_frm.pack(fill=tk.X, pady=5)
        ttk.Label(dio_frm, text="DIO Board Number:").pack(side=tk.LEFT, padx=(0, 10))
        self.dio_board_var = tk.IntVar(value=settings.dio_board_number)
        dio_board_spin = ttk.Spinbox(dio_frm, from_=0, to=15, width=5,
                                     textvariable=self.dio_board_var)
        dio_board_spin.pack(side=tk.LEFT)

        # AI Channel
        chan_frm = ttk.Frame(config_frm)
        chan_frm.pack(fill=tk.X, pady=5)
        ttk.Label(chan_frm, text="AI Channel:").pack(side=tk.LEFT, padx=(0, 10))
        self.ai_channel_var = tk.IntVar(value=settings.ai_channel)
        ai_channel_spin = ttk.Spinbox(chan_frm, from_=0, to=15, width=5,
                                      textvariable=self.ai_channel_var)
        ai_channel_spin.pack(side=tk.LEFT)

        # Apply Button
        btn_frm = ttk.Frame(config_frm)
        btn_frm.pack(fill=tk.X, pady=(20, 5))
        apply_btn = ttk.Button(btn_frm, text="Apply Configuration",
                               command=self._apply_config)
        apply_btn.pack(pady=10)

        # Status message
        self.config_status = tk.StringVar(value="")
        ttk.Label(config_frm, textvariable=self.config_status, foreground="blue").pack()

    def _build_control_tab(self):
        """Build the main control tab"""
        # Top bar
        top = ttk.Frame(self.control_tab, padding=(10, 5))
        top.pack(fill=tk.X)

        ttk.Label(top, text="Operator Initials:").grid(row=0, column=0, sticky="w")
        self.initialsVar = tk.StringVar()
        ttk.Entry(top, width=5, textvariable=self.initialsVar).grid(
            row=0,
            column=1,
            padx=(2, 15),
        )

        self.startBtn = ttk.Button(top, text="Start", command=self.startRecording)
        self.startBtn.grid(row=0, column=2, padx=(10, 2))

        self.stopBtn = ttk.Button(top, text="Stop", command=self.stopRecording, state="disabled")
        self.stopBtn.grid(row=0, column=3)

        ttk.Label(top, text="File:").grid(row=0, column=4, padx=(10, 2))
        self.filenameVar = tk.StringVar(value="")
        self.filenameLabel = ttk.Label(top, textvariable=self.filenameVar, foreground="blue")
        self.filenameLabel.grid(row=0, column=5, sticky="w")

        ttk.Separator(self.control_tab, orient="horizontal").pack(fill=tk.X, pady=4)

        # Main frame
        main = ttk.Frame(self.control_tab)
        main.pack(fill=tk.X, padx=10)

        info = ttk.Frame(main)
        info.pack(side=tk.LEFT, expand=True)

        # Live readouts
        ttk.Label(info, text="Time Elapsed (s):").grid(row=0, column=0, sticky="w")
        self.timeVar = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.timeVar).grid(row=0, column=1, padx=(4, 20))

        ttk.Label(info, text="Current Signal (V):").grid(row=0, column=2, sticky="w")
        self.signalVar = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.signalVar).grid(row=0, column=3, padx=(4, 20))

        ttk.Label(info, text="Time Remaining (s):").grid(row=0, column=4, sticky="w")
        self.remainingVar = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.remainingVar).grid(row=0, column=5)

        # Run-duration row
        dur = ttk.Frame(info)
        dur.grid(row=1, column=0, columnspan=6, sticky="w", pady=(6, 0))

        ttk.Label(dur, text="Run Duration (s):").pack(side=tk.LEFT, padx=(0, 2))
        self.durationVar = tk.StringVar(value=str(settings.run_duration))
        self.durationEntry = ttk.Entry(dur, width=7, textvariable=self.durationVar)
        self.durationEntry.pack(side=tk.LEFT)
        self.durationEntry.bind("<FocusOut>", self._update_duration)
        self.durationEntry.bind("<Return>", self._update_duration)

        ttk.Label(dur, text="Presets:").pack(side=tk.LEFT, padx=(10, 2))
        preset_btns = [
            ("2 min", 120),
            ("5 min", 300),
            ("10 min", 600)
        ]
        for text, sec in preset_btns:
            ttk.Button(
                dur,
                text=text,
                width=7,
                command=lambda s=sec: self._set_duration(s)
            ).pack(side=tk.LEFT, padx=(0, 2))

        # Valve schedule controls
        valve_schedule_frm = ttk.LabelFrame(info, text="Valve Schedule")
        valve_schedule_frm.grid(row=2, column=0, columnspan=6, sticky="we", pady=(10, 5), padx=5)

        # Initial valve
        initial_frm = ttk.Frame(valve_schedule_frm)
        initial_frm.pack(fill=tk.X, padx=5, pady=(5, 0))
        ttk.Label(initial_frm, text="Initial Valve:").pack(side=tk.LEFT, padx=(0, 5))
        self.initialValveVar = tk.StringVar(value="A")
        ttk.Radiobutton(initial_frm, text="A", variable=self.initialValveVar, value="A").pack(side=tk.LEFT)
        ttk.Radiobutton(initial_frm, text="B", variable=self.initialValveVar, value="B").pack(side=tk.LEFT)

        # Valve swap table
        swap_frm = ttk.Frame(valve_schedule_frm)
        swap_frm.pack(fill=tk.X, padx=5, pady=5)

        # Table header
        header = ttk.Frame(swap_frm)
        header.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(header, text="Swap #", width=8).pack(side=tk.LEFT)
        ttk.Label(header, text="Time (s)", width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(header, text="Valve", width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(header, text="Action", width=8).pack(side=tk.LEFT)

        # Container for swap rows
        self.swap_rows_frame = ttk.Frame(swap_frm)
        self.swap_rows_frame.pack(fill=tk.X)

        # Add/remove controls
        ctrl_frm = ttk.Frame(valve_schedule_frm)
        ctrl_frm.pack(fill=tk.X, padx=5, pady=(0, 5))
        ttk.Button(ctrl_frm, text="+ Add Swap", command=self._add_swap_row).pack(side=tk.LEFT)
        ttk.Button(ctrl_frm, text="- Remove Last", command=self._remove_last_swap).pack(side=tk.LEFT, padx=5)

        # Populate with existing schedule
        self.swap_vars = []
        for time, valve in settings.valve_schedule:
            self._add_swap_row(time, valve)

        # Auto-run row
        auto_run_f = ttk.Frame(info)
        auto_run_f.grid(row=3, column=0, columnspan=6, sticky="w", pady=(10, 0))

        self.autoRunVar = tk.BooleanVar(value=settings.auto_run)
        ttk.Checkbutton(
            auto_run_f,
            text="Auto-run every",
            variable=self.autoRunVar,
            command=self._toggle_auto_run
        ).pack(side=tk.LEFT)

        # Interval entry
        self.autoIntVar = tk.StringVar(value=str(settings.auto_run_interval))
        self.autoIntEntry = ttk.Entry(auto_run_f, width=5, textvariable=self.autoIntVar)
        self.autoIntEntry.pack(side=tk.LEFT)
        self.autoIntEntry.bind("<FocusOut>", self._update_auto_interval)
        self.autoIntEntry.bind("<Return>", self._update_auto_interval)

        ttk.Label(auto_run_f, text="seconds").pack(side=tk.LEFT, padx=(0, 2))

        # Next run display
        self.nextRunVar = tk.StringVar(value="Next run: --:--:--")
        ttk.Label(auto_run_f, textvariable=self.nextRunVar).pack(side=tk.LEFT, padx=(10, 0))

        # Y-axis controls
        yctrl = ttk.Frame(info)
        yctrl.grid(row=4, column=0, columnspan=6, sticky="w", pady=(6, 0))

        self.autoscaleVar = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            yctrl,
            text="Autoscale Y",
            variable=self.autoscaleVar,
            command=self._toggleAutoscale,
        ).pack(side=tk.LEFT)

        ttk.Label(yctrl, text="Y min:").pack(side=tk.LEFT, padx=(10, 2))
        self.yMinVar = tk.StringVar(value="0")
        self.yMinEntry = ttk.Entry(yctrl, width=7, textvariable=self.yMinVar, state="disabled")
        self.yMinEntry.pack(side=tk.LEFT)

        ttk.Label(yctrl, text="Y max:").pack(side=tk.LEFT, padx=(6, 2))
        self.yMaxVar = tk.StringVar(value="1")
        self.yMaxEntry = ttk.Entry(yctrl, width=7, textvariable=self.yMaxVar, state="disabled")
        self.yMaxEntry.pack(side=tk.LEFT)

        # Manual valve buttons
        valve_f = ttk.Frame(main, padding=(20, 0))
        valve_f.pack(side=tk.RIGHT, anchor="ne")

        self.buttonA = tk.Button(valve_f, text="Open A", width=10, bg=self.CLOSED_CLR, command=self.toggleValveA)
        self.buttonA.pack(pady=(0, 5))

        self.buttonB = tk.Button(valve_f, text="Open B", width=10, bg=self.CLOSED_CLR, command=self.toggleValveB)
        self.buttonB.pack()

        # Matplotlib figure
        self.fig, self.ax = plt.subplots(figsize=(6, 4))
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Signal (V)")

        self.line, = self.ax.plot([], [], lw=1.3)

        FigureCanvasTkAgg(self.fig, master=self.control_tab).get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.xData = []
        self.yData = []

    # ──────────────────────────────────────────────────────────
    #  Configuration methods
    # ──────────────────────────────────────────────────────────
    def _apply_config(self):
        """Apply new configuration settings"""
        try:
            if self.recording:
                messagebox.showerror("Error", "Cannot change configuration while recording")
                return

            # Validate inputs
            ai_board = int(self.ai_board_var.get())
            dio_board = int(self.dio_board_var.get())
            ai_channel = int(self.ai_channel_var.get())

            if not (0 <= ai_board <= 15):
                raise ValueError("AI board number must be 0-15")
            if not (0 <= dio_board <= 15):
                raise ValueError("DIO board number must be 0-15")
            if not (0 <= ai_channel <= 15):
                raise ValueError("AI channel must be 0-15")

            # Update settings
            settings.ai_board_number = ai_board
            settings.dio_board_number = dio_board
            settings.ai_channel = ai_channel

            # Reinitialize hardware
            self.valves = Valves()
            self.daq = DataAcquisition()
            self.daq.attach_queue(self.dataQueue)

            self.config_status.set("Configuration updated successfully")
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid configuration: {str(e)}")

    # ──────────────────────────────────────────────────────────
    #  Valve schedule management
    # ──────────────────────────────────────────────────────────
    def _add_swap_row(self, time_val: float = 0.0, valve_val: str = "B"):
        """Add a new row to the valve schedule table"""
        row = ttk.Frame(self.swap_rows_frame)
        row.pack(fill=tk.X, pady=2)

        # Swap number
        swap_num = len(self.swap_vars) + 1
        ttk.Label(row, text=f"#{swap_num}", width=8).pack(side=tk.LEFT)

        # Time entry
        time_var = tk.StringVar(value=str(time_val))
        time_ent = ttk.Entry(row, width=8, textvariable=time_var)
        time_ent.pack(side=tk.LEFT, padx=5)

        # Valve selection
        valve_var = tk.StringVar(value=valve_val)
        valve_cmb = ttk.Combobox(row, width=8, textvariable=valve_var, state="readonly")
        valve_cmb['values'] = ("A", "B")
        valve_cmb.pack(side=tk.LEFT, padx=5)

        # Remove button
        remove_btn = ttk.Button(row, text="Remove", width=8,
                                command=lambda r=row: self._remove_swap_row(r))
        remove_btn.pack(side=tk.LEFT)

        # Store variables
        self.swap_vars.append((time_var, valve_var, row))

    def _remove_swap_row(self, row):
        """Remove a specific row from the valve schedule"""
        # Find and remove the row from our list
        for i, (time_var, valve_var, row_widget) in enumerate(self.swap_vars):
            if row_widget == row:
                self.swap_vars.pop(i)
                row.destroy()
                break

        # Renumber remaining swaps
        for i, (_, _, row_widget) in enumerate(self.swap_vars):
            swap_num_label = row_widget.winfo_children()[0]
            swap_num_label.config(text=f"#{i + 1}")

    def _remove_last_swap(self):
        """Remove the last swap from the schedule"""
        if self.swap_vars:
            _, _, row = self.swap_vars.pop()
            row.destroy()

    def _get_valve_schedule(self) -> list[tuple[float, str]]:
        """Get the current valve schedule from the UI"""
        schedule = []
        for time_var, valve_var, _ in self.swap_vars:
            try:
                time_val = float(time_var.get())
                valve_val = valve_var.get()
                if time_val >= 0 and valve_val in ("A", "B"):
                    schedule.append((time_val, valve_val))
                else:
                    messagebox.showerror("Invalid Input",
                                         f"Invalid valve schedule: time={time_val}, valve={valve_val}")
            except ValueError:
                messagebox.showerror("Invalid Input", "Time must be a number")
        return sorted(schedule, key=lambda x: x[0])

    # ──────────────────────────────────────────────────────────
    #  Duration and interval synchronization
    # ──────────────────────────────────────────────────────────
    def _set_duration(self, seconds: float):
        """Set duration without affecting auto-run interval"""
        settings.run_duration = seconds
        self.durationVar.set(str(seconds))

    def _update_duration(self, event=None):
        """Update from GUI entry"""
        try:
            seconds = float(self.durationVar.get())
            settings.run_duration = seconds
        except ValueError:
            pass

    def _update_auto_interval(self, event=None):
        """Update auto-run interval from GUI"""
        try:
            interval = int(self.autoIntVar.get())
            settings.auto_run_interval = interval
        except ValueError:
            pass

    # ──────────────────────────────────────────────────────────
    #  Auto-run methods
    # ──────────────────────────────────────────────────────────
    def _toggle_auto_run(self):
        settings.auto_run = self.autoRunVar.get()
        if settings.auto_run:
            # Update settings from GUI
            try:
                settings.auto_run_interval = int(self.autoIntVar.get())
            except ValueError:
                pass  # Keep previous value
            self._start_auto_run_scheduler()
        elif self.auto_run_job:
            self.root.after_cancel(self.auto_run_job)
            self.auto_run_job = None
            self.next_run_time = None
            self.nextRunVar.set("Next run: --:--:--")

    def _calculate_next_run(self):
        """Calculate next run time at exact second interval."""
        now = datetime.now()
        interval_seconds = settings.auto_run_interval

        # Calculate next time that is multiple of interval seconds
        current_seconds = now.hour * 3600 + now.minute * 60 + now.second
        remainder = current_seconds % interval_seconds

        if remainder == 0:
            # Already at interval, run immediately
            next_seconds = current_seconds
        else:
            next_seconds = current_seconds + interval_seconds - remainder

        # Convert seconds back to time
        next_hour = next_seconds // 3600
        next_minute = (next_seconds % 3600) // 60
        next_second = next_seconds % 60

        # Create next run time
        next_run = now.replace(hour=next_hour, minute=next_minute, second=next_second, microsecond=0)

        # Handle day rollover
        if next_hour >= 24:
            next_run = next_run + timedelta(days=1)

        return next_run

    def _start_auto_run_scheduler(self):
        if not settings.auto_run:
            return

        # Calculate next run time
        self.next_run_time = self._calculate_next_run()
        self.nextRunVar.set(f"Next run: {self.next_run_time.strftime('%H:%M:%S')}")

        # Calculate delay in milliseconds
        now = datetime.now()
        delay_ms = int((self.next_run_time - now).total_seconds() * 1000)

        # Schedule next run
        if self.auto_run_job:
            self.root.after_cancel(self.auto_run_job)
        self.auto_run_job = self.root.after(delay_ms, self._execute_auto_run)

    def _execute_auto_run(self):
        if not settings.auto_run:
            return

        # Start recording
        self.startRecording()

        # Schedule next run after current run completes
        self.auto_run_job = self.root.after(
            int(settings.auto_run_interval * 1000),  # Use full interval
            self._start_auto_run_scheduler
        )

    # ──────────────────────────────────────────────────────────
    #  Valve helpers
    # ──────────────────────────────────────────────────────────
    def _setValveState(self, valve: str):
        if valve == "A":
            self.valves.set_valve_position_a()
            self.buttonA.config(bg=self.OPEN_CLR)
            self.buttonB.config(bg=self.CLOSED_CLR)
        else:
            self.valves.set_valve_position_b()
            self.buttonB.config(bg=self.OPEN_CLR)
            self.buttonA.config(bg=self.CLOSED_CLR)

        self.currentValve = valve

    # ──────────────────────────────────────────────────────────
    #  Autoscale toggle
    # ──────────────────────────────────────────────────────────
    def _toggleAutoscale(self):
        state = "disabled" if self.autoscaleVar.get() else "normal"
        self.yMinEntry.config(state=state)
        self.yMaxEntry.config(state=state)

    # ──────────────────────────────────────────────────────────
    #  Start / Stop
    # ──────────────────────────────────────────────────────────
    def startRecording(self):
        if self.recording:
            return

        # Set operator initials from GUI
        settings.operator_initials = self.initialsVar.get().strip() or "NULL"

        # Generate filename for this run
        initials = settings.operator_initials.upper()
        stamp = datetime.now().strftime("%y%m%d_%H%M%S")
        self.current_filename = f"{initials}_{stamp}"

        # Show filename in UI
        self.filenameVar.set(self.current_filename)

        # Set filename in DAQ
        self.daq.set_filename(self.current_filename)

        # Use effective duration (with 5s buffer)
        self.maxDuration = settings.effective_run_duration

        # Get valve schedule from UI
        settings.valve_schedule = self._get_valve_schedule()

        # Set initial valve
        self.currentValve = self.initialValveVar.get()
        self._setValveState(self.currentValve)

        # Clear any existing swap jobs
        for job_id in self.swap_job_ids:
            self.root.after_cancel(job_id)
        self.swap_job_ids = []

        # Schedule all valve swaps
        for swap_time, valve_target in settings.valve_schedule:
            if swap_time > 0 and swap_time < self.maxDuration:
                job_id = self.root.after(
                    int(swap_time * 1000),
                    lambda v=valve_target: self._setValveState(v)
                )
                self.swap_job_ids.append(job_id)

        self.xData.clear()
        self.yData.clear()
        self.line.set_data([], [])

        self.startTime = time.perf_counter()
        self.recording = True
        self.daq.start()

        self.startBtn.config(state="disabled")
        self.stopBtn.config(state="normal")

    def stopRecording(self):
        if not self.recording:
            return

        self.recording = False
        self.daq.stop()

        # Cancel all swap jobs
        for job_id in self.swap_job_ids:
            self.root.after_cancel(job_id)
        self.swap_job_ids = []

        self.startBtn.config(state="normal")
        self.stopBtn.config(state="disabled")

        # Clear filename after short delay to show it was saved
        self.root.after(2000, lambda: self.filenameVar.set(""))

    # ──────────────────────────────────────────────────────────
    #  Main update loop
    # ──────────────────────────────────────────────────────────
    def updateLoop(self):
        while not self.dataQueue.empty():
            t_rel, v = self.dataQueue.get_nowait()
            self.xData.append(t_rel)
            self.yData.append(v)

        if self.xData:
            elapsed = self.xData[-1]
            remaining = max(0.0, self.maxDuration - elapsed)

            self.timeVar.set(f"{elapsed:.4f}")
            self.remainingVar.set(f"{remaining:.4f}")
            self.signalVar.set(f"{self.yData[-1]:.4f}")

            self.line.set_data(self.xData, self.yData)

            xmin = self.xData[0]
            xmax = self.xData[-1]
            pad_x = max(1e-6, (xmax - xmin) * 0.02)
            self.ax.set_xlim(xmin - pad_x, xmax + pad_x)

            if self.autoscaleVar.get():
                ymin = min(self.yData)
                ymax = max(self.yData)
                pad_y = max(1e-6, (ymax - ymin) * 0.05)
                self.ax.set_ylim(ymin - pad_y, ymax + pad_y)
            else:
                lims = self._manualYLimits()
                if lims:
                    self.ax.set_ylim(lims)

            self.fig.canvas.draw_idle()

            if self.recording and elapsed >= self.maxDuration:
                self.stopRecording()

        self.jobId = self.root.after(self.blockMS, self.updateLoop)

    # ──────────────────────────────────────────────────────────
    #  Utility helpers
    # ──────────────────────────────────────────────────────────
    def _manualYLimits(self):
        try:
            ymin = float(self.yMinVar.get())
            ymax = float(self.yMaxVar.get())
            if ymin >= ymax:
                raise ValueError
            return ymin, ymax
        except ValueError:
            return None

    def _safe_float(self, tk_var: tk.StringVar, default: float) -> float:
        try:
            return float(tk_var.get())
        except ValueError:
            return default

    # Manual override buttons
    def toggleValveA(self):
        self._setValveState("A")

    def toggleValveB(self):
        self._setValveState("B")

    # Clean shutdown
    def closeWindow(self):
        if self.recording:
            self.stopRecording()

        if self.jobId:
            self.root.after_cancel(self.jobId)

        for job_id in self.swap_job_ids:
            if job_id:
                self.root.after_cancel(job_id)

        if self.auto_run_job:
            self.root.after_cancel(self.auto_run_job)

        self.root.destroy()


# Stand-alone entry point
def main():
    root = tk.Tk()
    Display(root)
    root.mainloop()


if __name__ == "__main__":
    main()