import time
import tkinter as tk
from tkinter import ttk

import matplotlib
matplotlib.use("TkAgg") # Embed matplotlib in Tkinter
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

from DataAcquisition import DataAcquisition


class Display:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Real‑Time Signal Monitor")

        self.daq = DataAcquisition()
        self.daq.startTime = time.perf_counter() # reset time start

        # Figure/Canvas
        self.fig, self.ax = plt.subplots(figsize=(6, 4))
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Signal (V)")
        self.line, = self.ax.plot([], [], lw=1.5)

        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Labels
        info = ttk.Frame(root)
        info.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)

        ttk.Label(info, text="Time Elapsed (s):").grid(row=0, column=0, sticky="w")
        self.time_var = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.time_var).grid(row=0, column=1, sticky="w", padx=(4, 20))

        ttk.Label(info, text="Current Signal (V):").grid(row=0, column=2, sticky="w")
        self.signal_var = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.signal_var).grid(row=0, column=3, sticky="w")

        # data containers
        self.xdata: list[float] = [] # time stamps
        self.ydata: list[float] = [] # signal values

        # Update interval in milliseconds
        self.update_ms = 100 # 10 Hz refresh

        # Begin periodic update loop
        self._job = self.root.after(self.update_ms, self._update_loop)

        # Proper cleanup on close
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _update_loop(self):
        try:
            signal = self.daq.getSignalData()
        except Exception as exc:
            # Hardware call failed ‑ fall back to None so UI keeps running
            print("Error reading signal:", exc)
            signal = None

        if signal is not None:
            # Compute elapsed time
            t = time.perf_counter() - self.daq.startTime

            # Store data
            self.xdata.append(t)
            self.ydata.append(signal)

            # Update read‑outs
            self.time_var.set(f"{t:.4f}")
            self.signal_var.set(f"{signal:.4f}")

            # Update plot line
            self.line.set_data(self.xdata, self.ydata)
            self.ax.relim() # Recompute axes limits
            self.ax.autoscale_view() # Autoscale to new data range
            self.canvas.draw_idle()

        # Schedule the next update
        self._job = self.root.after(self.update_ms, self._update_loop)

    def close(self):
        if self._job is not None:
            self.root.after_cancel(self._job)
            self._job = None

        # Persist the collected data using the DAQ class's writer
        if self.xdata and self.ydata:
            self.daq.data = list(zip(self.xdata, self.ydata))
            try:
                self.daq.writeData(self.daq.data)
            except Exception as exc:
                print("Could not write data file:", exc)

        self.root.destroy()

def main():
    root = tk.Tk()
    Display(root) # create and start GUI
    root.mainloop()


if __name__ == "__main__":
    main()
