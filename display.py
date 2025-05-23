import time
import tkinter as tk
from tkinter import ttk, messagebox

import matplotlib
matplotlib.use("TkAgg") # use Tk backend for embedding
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

from DataAcquisition import DataAcquisition


class Display:
    # GUI refresh rate (ms)
    UPDATE_MS = 100  # 10 Hz

    def __init__(self, root):
        self.root = root
        self.root.title("Real‑Time Signal Monitor")

        # Data acquisition object
        self.daq = DataAcquisition()

        # acquisition state
        self.recording = True
        self.startTime = time.perf_counter()

        # gui construction
        # operator initials, start / stop button
        top = ttk.Frame(root, padding=(10, 5))
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="Operator Initials:").grid(row=0, column=0, sticky="w")
        self.initialsVar = tk.StringVar()
        initialsEntry = ttk.Entry(top, width=5, textvariable=self.initialsVar)
        initialsEntry.grid(row=0, column=1, sticky="w", padx=(2, 15))
        initialsEntry.focus_set()

        ttk.Separator(root, orient="horizontal").pack(fill=tk.X, pady=4)

        # elapsed‑time / signal read‑outs
        info = ttk.Frame(root, padding=(10, 0))
        info.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(info, text="Time Elapsed (s):").grid(row=0, column=0, sticky="w")
        self.timeVar = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.timeVar).grid(row=0, column=1, sticky="w", padx=(4, 20))

        ttk.Label(info, text="Current Signal (V):").grid(row=0, column=2, sticky="w")
        self.signalVar = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.signalVar).grid(row=0, column=3, sticky="w")

        # matplotlib figure embedded in Tk
        self.fig, self.ax = plt.subplots(figsize=(6, 4))
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Signal (V)")
        self.line, = self.ax.plot([], [], lw=1.3)

        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # data containers
        self.xData = []
        self.yData = []

        # schedule first GUI update
        self.jobId = self.root.after(self.UPDATE_MS, self.updateLoop)

        # close handler
        self.root.protocol("WM_DELETE_WINDOW", self.closeWindow)

    def toggleRecording(self):
        # toggles acquisition on/off
        self.recording = not self.recording

        # write immediately when stopping
        if not self.recording:
            self.writeDataToFile()

    def updateLoop(self):
        if self.recording:
            try:
                signal = self.daq.getSignalData()
            except Exception as exc:
                print("Error reading signal:", exc)
                signal = None

            if signal is not None:
                t = time.perf_counter() - self.startTime
                self.xData.append(t)
                self.yData.append(signal)

                # update read‑outs
                self.timeVar.set(f"{t:.4f}")
                self.signalVar.set(f"{signal:.4f}")

                # update plot
                self.line.set_data(self.xData, self.yData)
                self.ax.relim()
                self.ax.autoscale_view()
                self.canvas.draw_idle()

        # reschedule next refresh
        self.jobId = self.root.after(self.UPDATE_MS, self.updateLoop)

    def writeDataToFile(self):
        if not self.xData:
            return # nothing to save

        initials = self.initialsVar.get().strip().upper() or "NULL"
        self.daq.operatorInitials = initials

        self.daq.data = list(zip(self.xData, self.yData))
        try:
            self.daq.writeData(self.daq.data)
            print("Data written to disk.")
        except Exception as exc:
            messagebox.showerror("Write Error", f"Could not write data file:\n{exc}")

    def closeWindow(self):
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