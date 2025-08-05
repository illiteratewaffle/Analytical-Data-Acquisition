import tkinter as tk
from tkinter import ttk, messagebox


class ValveControlFrame(tk.LabelFrame):
    def __init__(self, parent, daq, valve_config, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.daq = daq
        self.valve_config = valve_config
        self.valve_states = {}
        self.on_buttons = {}
        self.off_buttons = {}

        # Title
        ttk.Label(self, text="Valve Control", font=("Arial", 12, "bold")).grid(
            row=0, column=0, columnspan=4, pady=10
        )

        # Create regular buttons (not ttk) for full color control
        for i, valve in enumerate(self.valve_config):
            # Valve name
            ttk.Label(self, text=valve["name"]).grid(row=i + 1, column=0, padx=10, pady=5, sticky="w")

            # ON button (regular tk.Button)
            on_btn = tk.Button(
                self,
                text="ON",
                width=6,
                bg="SystemButtonFace",  # Default color
                activebackground="SystemButtonFace",
                command=lambda v=valve["port_line"]: self.set_valve(v, True)
            )
            on_btn.grid(row=i + 1, column=1, padx=5, pady=5)
            self.on_buttons[valve["port_line"]] = on_btn

            # OFF button (regular tk.Button)
            off_btn = tk.Button(
                self,
                text="OFF",
                width=6,
                bg="SystemButtonFace",  # Default color
                activebackground="SystemButtonFace",
                command=lambda v=valve["port_line"]: self.set_valve(v, False)
            )
            off_btn.grid(row=i + 1, column=2, padx=5, pady=5)
            self.off_buttons[valve["port_line"]] = off_btn

            # Store state indicator
            self.valve_states[valve["port_line"]] = tk.StringVar(value="OFF")
            state_label = ttk.Label(self, textvariable=self.valve_states[valve["port_line"]], width=8)
            state_label.grid(row=i + 1, column=3, padx=5, pady=5)

            # Set initial state to OFF
            self.set_valve(valve["port_line"], False)

    def set_valve(self, port_line, state):
        try:
            self.daq.write_digital(port_line, state)
            self.valve_states[port_line].set("ON" if state else "OFF")

            # Update button colors directly
            if state:
                self.on_buttons[port_line].config(bg="#39FF14", activebackground="#39FF14")  # Neon green
                self.off_buttons[port_line].config(bg="SystemButtonFace", activebackground="SystemButtonFace")
            else:
                self.on_buttons[port_line].config(bg="SystemButtonFace", activebackground="SystemButtonFace")
                self.off_buttons[port_line].config(bg="#FF5F1F", activebackground="#FF5F1F")  # Neon orange

        except Exception as e:
            messagebox.showerror("Valve Error", f"Failed to control valve: {str(e)}")

    def update_valve_ports(self):
        """Update valve ports after configuration change"""
        for i, valve in enumerate(self.valve_config):
            port_line = valve['port_line']
            state = self.daq.read_digital_state(port_line)
            self.valve_states[port_line].set("ON" if state else "OFF")

            # Update button colors
            if state:
                self.on_buttons[port_line].config(bg="#39FF14", activebackground="#39FF14")
                self.off_buttons[port_line].config(bg="SystemButtonFace", activebackground="SystemButtonFace")
            else:
                self.on_buttons[port_line].config(bg="SystemButtonFace", activebackground="SystemButtonFace")
                self.off_buttons[port_line].config(bg="#FF5F1F", activebackground="#FF5F1F")