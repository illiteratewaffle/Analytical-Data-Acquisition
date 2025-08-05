import tkinter as tk
from tkinter import ttk


class ValveScheduler(ttk.LabelFrame):
    def __init__(self, parent, valve_index, daq, valve_config, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.daq = daq
        self.valve_index = valve_index
        self.valve_config = valve_config
        self.port_line = valve_config[valve_index]['port_line']
        self.swap_job_ids = []
        self.current_state = False  # Track current valve state

        # Configure grid for column layout
        self.columnconfigure(0, weight=1)

        # Valve label
        ttk.Label(self, text=f"Valve {valve_index + 1} Schedule", font=("Arial", 10, "bold")).grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )

        # Initial state
        ttk.Label(self, text="Initial State:").grid(row=1, column=0, sticky="w", padx=5)
        self.initial_state_var = tk.StringVar(value="OFF")
        initial_frame = ttk.Frame(self)
        initial_frame.grid(row=2, column=0, sticky="w", padx=5, pady=(0, 10))
        ttk.Radiobutton(initial_frame, text="OFF", variable=self.initial_state_var,
                        value="OFF").pack(side=tk.LEFT)
        ttk.Radiobutton(initial_frame, text="ON", variable=self.initial_state_var,
                        value="ON").pack(side=tk.LEFT, padx=(10, 0))

        # Swap schedule header
        header = ttk.Frame(self)
        header.grid(row=3, column=0, sticky="we", padx=5)
        ttk.Label(header, text="Time (s)", width=8).pack(side=tk.LEFT)
        ttk.Label(header, text="Action", width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(header, text="Remove", width=8).pack(side=tk.RIGHT)

        # Container for swap rows
        self.swap_rows_frame = ttk.Frame(self)
        self.swap_rows_frame.grid(row=4, column=0, sticky="we", padx=5, pady=5)

        # Add/remove buttons
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=5, column=0, sticky="w", padx=5, pady=(0, 10))
        ttk.Button(btn_frame, text="+ Add Swap", command=self.add_swap_row).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="- Remove Last", command=self.remove_last_swap).pack(side=tk.LEFT, padx=5)

        # Store swap variables
        self.swap_vars = []

        # Add one initial row
        self.add_swap_row()

    def add_swap_row(self):
        """Add a new row to the valve schedule table"""
        row = ttk.Frame(self.swap_rows_frame)
        row.pack(fill=tk.X, pady=2)

        # Time entry
        time_var = tk.StringVar(value="0.0")
        time_ent = ttk.Entry(row, width=8, textvariable=time_var)
        time_ent.pack(side=tk.LEFT)

        # Action selection
        action_var = tk.StringVar(value="ON")
        action_cmb = ttk.Combobox(row, width=8, textvariable=action_var, state="readonly")
        action_cmb['values'] = ("ON", "OFF")
        action_cmb.pack(side=tk.LEFT, padx=5)

        # Remove button
        remove_btn = ttk.Button(row, text="Remove", width=8, command=lambda r=row: self.remove_swap_row(r))
        remove_btn.pack(side=tk.RIGHT)

        # Store variables
        self.swap_vars.append((time_var, action_var, row))

    def remove_swap_row(self, row):
        """Remove a specific row from the valve schedule"""
        for i, (time_var, action_var, row_widget) in enumerate(self.swap_vars):
            if row_widget == row:
                self.swap_vars.pop(i)
                row.destroy()
                break

    def remove_last_swap(self):
        """Remove the last swap from the schedule"""
        if self.swap_vars:
            _, _, row = self.swap_vars.pop()
            row.destroy()

    def get_schedule(self):
        """Get the schedule for this valve"""
        schedule = []
        for time_var, action_var, _ in self.swap_vars:
            try:
                time_val = float(time_var.get())
                action_val = action_var.get()
                if time_val >= 0:
                    schedule.append((time_val, action_val))
            except ValueError:
                pass  # Skip invalid entries
        return sorted(schedule, key=lambda x: x[0])

    def set_initial_state(self):
        """Set the initial state for this valve"""
        state = self.initial_state_var.get() == "ON"
        self.current_state = state
        self.daq.write_digital(self.port_line, state)

    def schedule_actions(self, master):
        """Schedule all actions for this valve"""
        schedule = self.get_schedule()
        for time_val, action_val in schedule:
            state = action_val == "ON"
            job_id = master.after(
                int(time_val * 1000),
                lambda s=state: self.set_valve_state(s)
            )
            self.swap_job_ids.append(job_id)

    def set_valve_state(self, state):
        """Set valve state and track current state"""
        self.current_state = state
        self.daq.write_digital(self.port_line, state)

    def cancel_schedules(self):
        """Cancel all scheduled jobs for this valve"""
        for job_id in self.swap_job_ids:
            self.master.after_cancel(job_id)
        self.swap_job_ids = []

    def turn_off(self):
        """Turn off this valve"""
        self.current_state = False
        self.daq.write_digital(self.port_line, False)