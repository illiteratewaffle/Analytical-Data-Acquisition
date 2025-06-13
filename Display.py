import time
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

import matplotlib
matplotlib.use("TkAgg") # use Tk backend for embedding
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

from DataAcquisition import DataAcquisition
from Valves import Valves

class Display:
    # GUI refresh rate (ms)
    UPDATE_MS = 1  # 10 Hz

    def __init__(self, root):
        self.root = root
        self.root.title("Real‑Time Signal Monitor")

        # Data acquisition object
        self.daq = DataAcquisition()

        # acquisition state
        self.recording = True
        self.startTime = time.perf_counter()

        # Duration of recording data
        self.maxDuration = 30  # seconds

        # Top panel: Operator initials
        top = ttk.Frame(root, padding=(10, 5))
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="Operator Initials:").grid(row=0, column=0, sticky="w")
        self.initialsVar = tk.StringVar()
        initialsEntry = ttk.Entry(top, width=5, textvariable=self.initialsVar)
        initialsEntry.grid(row=0, column=1, sticky="w", padx=(2, 15))
        initialsEntry.focus_set()

        ttk.Separator(root, orient="horizontal").pack(fill=tk.X, pady=4)

        # Main content area: Info on left, valves on right
        main = ttk.Frame(root)
        main.pack(side=tk.TOP, fill=tk.X, padx=10)

        # Info panel (left)
        info = ttk.Frame(main)
        info.pack(side=tk.LEFT, fill=tk.X, expand=True)

        ttk.Label(info, text="Time Elapsed (s):").grid(row=0, column=0, sticky="w")
        self.timeVar = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.timeVar).grid(row=0, column=1, sticky="w", padx=(4, 20))

        ttk.Label(info, text="Current Signal (V):").grid(row=0, column=2, sticky="w")
        self.signalVar = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.signalVar).grid(row=0, column=3, sticky="w", padx=(4, 20))

        ttk.Label(info, text="Time Remaining (s):").grid(row=0, column=4, sticky="w")
        self.remainingVar = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.remainingVar).grid(row=0, column=5, sticky="w")

        # Valve control panel (right)
        valve_frame = ttk.Frame(main, padding=(20, 0))
        valve_frame.pack(side=tk.RIGHT, anchor="ne")

        self.valves = Valves()
        self.valveA_on = False
        self.valveB_on = False

        self.buttonA = tk.Button(valve_frame, text="Open A", width=10, bg="#D3D3D3", command=self.toggleValveA)
        self.buttonA.pack(side=tk.TOP, pady=(0, 5))

        self.buttonB = tk.Button(valve_frame, text="Open B", width=10, bg="#D3D3D3", command=self.toggleValveB)
        self.buttonB.pack(side=tk.TOP)

        # Matplotlib graph
        self.fig, self.ax = plt.subplots(figsize=(6, 4))
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Signal (V)")
        self.line, = self.ax.plot([], [], lw=1.3)

        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Data containers
        self.xData = []
        self.yData = []

        # Schedule first GUI update
        self.jobId = self.root.after(self.UPDATE_MS, self.updateLoop)

        # Close handler
        self.root.protocol("WM_DELETE_WINDOW", self.closeWindow)

    def toggleRecording(self) -> None:
        # toggles acquisition on/off
        self.recording = not self.recording

        # write immediately when stopping
        if not self.recording:
            self.writeDataToFile()

    def toggleValveA(self) -> None:
        self.valveA_on = not self.valveA_on
        if self.valveA_on:
            self.valves.set_valve_position_a()
            self.buttonA.config(bg="#90EE90")
            self.valveB_on = False
            self.buttonB.config(bg="#D3D3D3")
        else:
            self.buttonA.config(bg="#D3D3D3")

    def toggleValveB(self) -> None:
        self.valveB_on = not self.valveB_on
        if self.valveB_on:
            self.valves.set_valve_position_b()
            self.buttonB.config(bg="#90EE90")
            self.valveA_on = False
            self.buttonA.config(bg="#D3D3D3")
        else:
            self.buttonB.config(bg="#D3D3D3")

    def updateLoop(self) -> None:
        if self.recording:
            elapsed = time.perf_counter() - self.startTime

            if elapsed >= self.maxDuration:
                self.recording = False
                self.writeDataToFile()
                return  # stop scheduling further updates

            try:
                signal = self.daq.getSignalData()
            except Exception as exc:
                print("Error reading signal:", exc)
                signal = None

            if signal is not None:
                remaining = max(0.0, self.maxDuration - elapsed)  # calculate time remaining

                self.xData.append(elapsed)
                self.yData.append(signal)

                self.timeVar.set(f"{elapsed:.4f}")
                self.remainingVar.set(f"{remaining:.4f}")  # update time remaining display
                self.signalVar.set(f"{signal:.4f}")

                self.line.set_data(self.xData, self.yData)
                self.ax.relim()
                self.ax.autoscale_view()
                self.canvas.draw_idle()

        # reschedule next refresh
        self.jobId = self.root.after(self.UPDATE_MS, self.updateLoop)

    def writeDataToFile(self) -> None:
        if not self.xData:
            return # nothing to save

        initials = self.initialsVar.get().strip().upper() or "NULL"
        self.daq.operatorInitials = initials

        epoch = datetime(1904, 1, 1)
        data_with_epoch_times = []
        for _, y in zip(self.xData, self.yData):
            now = datetime.now()
            timestamp = (now - epoch).total_seconds()
            data_with_epoch_times.append([timestamp, y])

        self.daq.data = data_with_epoch_times
        try:
            self.daq.writeData(self.daq.data)
            print("Data written to disk.")
        except Exception as exc:
            messagebox.showerror("Write Error", f"Could not write data file:\n{exc}")

    def closeWindow(self) -> None:
        # cancel scheduled callback
        if self.jobId is not None:
            self.root.after_cancel(self.jobId)
            self.jobId = None

        # always attempt to save any collected data
        if self.xData:
            self.writeDataToFile()

        self.root.destroy()

def main():
    root = tk.Tk()
    Display(root)
    root.mainloop()

if __name__ == "__main__":
    main()