import tkinter as tk
from tkinter import ttk, messagebox


class ValveControlFrame(tk.LabelFrame):
    def __init__(self, parent, daq, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.daq = daq
        self.valve_states = {}

        # Title
        ttk.Label(self, text="Valve Control", font=("Arial", 12, "bold")).grid(
            row=0, column=0, columnspan=3, pady=10
        )

        # Valve configuration
        self.valve_config = [
            {"name": "Valve 1", "port_line": "port1/line0"},
            {"name": "Valve 2", "port_line": "port1/line1"},
            {"name": "Valve 3", "port_line": "port1/line2"},
            {"name": "Valve 4", "port_line": "port1/line3"},
        ]

        # Create valve controls
        for i, valve in enumerate(self.valve_config):
            # Valve name
            ttk.Label(self, text=valve["name"]).grid(row=i + 1, column=0, padx=10, pady=5, sticky="w")

            # ON button
            on_btn = ttk.Button(
                self,
                text="ON",
                width=6,
                command=lambda v=valve["port_line"]: self.set_valve(v, True)
            )
            on_btn.grid(row=i + 1, column=1, padx=5, pady=5)

            # OFF button
            off_btn = ttk.Button(
                self,
                text="OFF",
                width=6,
                command=lambda v=valve["port_line"]: self.set_valve(v, False)
            )
            off_btn.grid(row=i + 1, column=2, padx=5, pady=5)

            # Store state indicator
            self.valve_states[valve["port_line"]] = tk.StringVar(value="OFF")
            state_label = ttk.Label(self, textvariable=self.valve_states[valve["port_line"]], width=8)
            state_label.grid(row=i + 1, column=3, padx=5, pady=5)

            # Set default state to OFF
            self.set_valve(valve["port_line"], False)

    def set_valve(self, port_line, state):
        try:
            self.daq.write_digital(port_line, state)
            self.valve_states[port_line].set("ON" if state else "OFF")
        except Exception as e:
            messagebox.showerror("Valve Error", f"Failed to control valve: {str(e)}")