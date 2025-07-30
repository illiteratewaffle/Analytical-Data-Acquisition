import tkinter as tk
from tkinter import ttk


class ConfigWindow(tk.Toplevel):
    def __init__(self, parent, daq, channel_config):
        super().__init__(parent)
        self.title("DAQ Configuration")
        self.daq = daq
        self.channel_config = channel_config
        self.parent = parent

        # Device configuration
        ttk.Label(self, text="Device Name:").grid(row=0, column=0, padx=5, pady=5)
        self.device_var = tk.StringVar(value=self.daq.device_name)
        ttk.Entry(self, textvariable=self.device_var).grid(row=0, column=1, padx=5, pady=5)

        # Channel mapping
        ttk.Label(self, text="Controller").grid(row=1, column=0)
        ttk.Label(self, text="Output Channel").grid(row=1, column=1)
        ttk.Label(self, text="Input Channel").grid(row=1, column=2)

        self.ao_vars = []
        self.ai_vars = []

        for i, config in enumerate(self.channel_config):
            ttk.Label(self, text=f"Controller {i + 1}").grid(row=i + 2, column=0, padx=5, pady=5)

            ao_var = tk.StringVar(value=config['ao'])
            ai_var = tk.StringVar(value=config['ai'])

            ttk.Entry(self, textvariable=ao_var, width=8).grid(row=i + 2, column=1, padx=5, pady=5)
            ttk.Entry(self, textvariable=ai_var, width=8).grid(row=i + 2, column=2, padx=5, pady=5)

            self.ao_vars.append(ao_var)
            self.ai_vars.append(ai_var)

        # Save button
        ttk.Button(self, text="Save Configuration", command=self.save_config).grid(
            row=len(self.channel_config) + 2, column=0, columnspan=3, pady=10
        )

    def save_config(self):
        """Save configuration to main application"""
        self.daq.set_device_name(self.device_var.get())

        for i in range(len(self.channel_config)):
            self.channel_config[i]['ao'] = self.ao_vars[i].get()
            self.channel_config[i]['ai'] = self.ai_vars[i].get()

        self.parent.update_channel_labels()
        self.destroy()