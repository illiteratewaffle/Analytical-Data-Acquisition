import time
import queue
import tkinter as tk
from tkinter import ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

from DataAcquisition import DataAcquisition
from Valves           import Valves


class Display:
    """GUI front-end (no direct DAQ calls) with Y-axis scaling panel."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Real-Time Signal Monitor")

        # ---------------- Acquisition back-end ------------------
        self.daq       = DataAcquisition()
        self.dataQueue = queue.Queue(maxsize=1000)
        self.daq.attach_queue(self.dataQueue)

        # GUI refresh period (ms) = one DAQ block duration
        self.blockMS = max(
            1,
            round(1000 * self.daq.blockSize / self.daq.samplingFrequency),
        )

        # run-state
        self.recording   = False
        self.startTime   = 0.0
        self.maxDuration = 30  # s

        # Build all widgets
        self._build_widgets()

        # periodic GUI refresh
        self.jobId = self.root.after(self.blockMS, self.updateLoop)
        self.root.protocol("WM_DELETE_WINDOW", self.closeWindow)

    # GUI construction
    def _build_widgets(self):
        # top bar
        top = ttk.Frame(self.root, padding=(10, 5))
        top.pack(fill=tk.X)

        ttk.Label(top, text="Operator Initials:").grid(row=0, column=0, sticky="w")
        self.initialsVar = tk.StringVar()
        ttk.Entry(top, width=5, textvariable=self.initialsVar).grid(
            row=0, column=1, padx=(2, 15)
        )

        self.startBtn = ttk.Button(top, text="Start", command=self.startRecording)
        self.startBtn.grid(row=0, column=2, padx=(10, 2))

        self.stopBtn = ttk.Button(
            top, text="Stop", command=self.stopRecording, state="disabled"
        )
        self.stopBtn.grid(row=0, column=3)

        ttk.Separator(self.root, orient="horizontal").pack(fill=tk.X, pady=4)

        # info + valve panel
        main = ttk.Frame(self.root)
        main.pack(fill=tk.X, padx=10)

        info = ttk.Frame(main)
        info.pack(side=tk.LEFT, expand=True)

        ttk.Label(info, text="Time Elapsed (s):").grid(row=0, column=0, sticky="w")
        self.timeVar = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.timeVar).grid(
            row=0, column=1, padx=(4, 20)
        )

        ttk.Label(info, text="Current Signal (V):").grid(row=0, column=2, sticky="w")
        self.signalVar = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.signalVar).grid(
            row=0, column=3, padx=(4, 20)
        )

        ttk.Label(info, text="Time Remaining (s):").grid(row=0, column=4, sticky="w")
        self.remainingVar = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.remainingVar).grid(row=0, column=5)

        # Y-axis scaling controls
        yctrl = ttk.Frame(info)
        yctrl.grid(row=1, column=0, columnspan=6, sticky="w", pady=(6, 0))

        self.autoscaleVar = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            yctrl,
            text="Autoscale Y",
            variable=self.autoscaleVar,
            command=self._toggleAutoscale,
        ).pack(side=tk.LEFT)

        ttk.Label(yctrl, text="Y min:").pack(side=tk.LEFT, padx=(10, 2))
        self.yMinVar = tk.StringVar(value="0")
        self.yMinEntry = ttk.Entry(
            yctrl, width=7, textvariable=self.yMinVar, state="disabled"
        )
        self.yMinEntry.pack(side=tk.LEFT)

        ttk.Label(yctrl, text="Y max:").pack(side=tk.LEFT, padx=(6, 2))
        self.yMaxVar = tk.StringVar(value="1")
        self.yMaxEntry = ttk.Entry(
            yctrl, width=7, textvariable=self.yMaxVar, state="disabled"
        )
        self.yMaxEntry.pack(side=tk.LEFT)

        # valve buttons
        valve_f = ttk.Frame(main, padding=(20, 0))
        valve_f.pack(side=tk.RIGHT, anchor="ne")

        self.valves = Valves()
        self.valveA_on = self.valveB_on = False

        self.buttonA = tk.Button(
            valve_f, text="Open A", width=10, bg="#D3D3D3", command=self.toggleValveA
        )
        self.buttonA.pack(pady=(0, 5))

        self.buttonB = tk.Button(
            valve_f, text="Open B", width=10, bg="#D3D3D3", command=self.toggleValveB
        )
        self.buttonB.pack()

        # matplotlib figure
        self.fig, self.ax = plt.subplots(figsize=(6, 4))
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Signal (V)")
        self.line, = self.ax.plot([], [], lw=1.3)

        FigureCanvasTkAgg(self.fig, master=self.root).get_tk_widget().pack(
            fill=tk.BOTH, expand=True
        )

        # data buffers
        self.xData, self.yData = [], []

    # Y-axis helpers
    def _toggleAutoscale(self):
        state = "disabled" if self.autoscaleVar.get() else "normal"
        self.yMinEntry.config(state=state)
        self.yMaxEntry.config(state=state)

        if not self.autoscaleVar.get():
            lims = self._getManualYLimits()
            if lims:
                self.ax.set_ylim(lims)
                self.fig.canvas.draw_idle()

    def _getManualYLimits(self):
        try:
            ymin = float(self.yMinVar.get())
            ymax = float(self.yMaxVar.get())
            if ymin >= ymax:
                raise ValueError
            return ymin, ymax
        except ValueError:
            # ignore bad limits
            return None

    # Start / Stop callbacks
    def startRecording(self):
        if self.recording:
            return

        self.daq.operatorInitials = (
            self.initialsVar.get().strip().upper() or "NULL"
        )

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

        self.startBtn.config(state="normal")
        self.stopBtn.config(state="disabled")

    # Periodic update loop
    def updateLoop(self):
        # pull any queued samples
        while not self.dataQueue.empty():
            t_rel, v = self.dataQueue.get_nowait()
            self.xData.append(t_rel)
            self.yData.append(v)

        # update plot and readouts if we have data
        if self.xData:
            elapsed = self.xData[-1]
            remaining = max(0.0, self.maxDuration - elapsed)

            self.timeVar.set(f"{elapsed:.4f}")
            self.remainingVar.set(f"{remaining:.4f}")
            self.signalVar.set(f"{self.yData[-1]:.4f}")

            self.line.set_data(self.xData, self.yData)

            if self.autoscaleVar.get():
                self.ax.relim()
                self.ax.autoscale_view()
            else:
                lims = self._getManualYLimits()
                if lims:
                    self.ax.set_ylim(lims)

            self.fig.canvas.draw_idle()

            if self.recording and elapsed >= self.maxDuration:
                self.stopRecording()

        # schedule next update
        self.jobId = self.root.after(self.blockMS, self.updateLoop)

    # Valve buttons
    def toggleValveA(self):
        self.valveA_on = not self.valveA_on
        if self.valveA_on:
            self.valves.set_valve_position_a()
            self.buttonA.config(bg="#90EE90")
            self.valveB_on = False
            self.buttonB.config(bg="#D3D3D3")
        else:
            self.buttonA.config(bg="#D3D3D3")

    def toggleValveB(self):
        self.valveB_on = not self.valveB_on
        if self.valveB_on:
            self.valves.set_valve_position_b()
            self.buttonB.config(bg="#90EE90")
            self.valveA_on = False
            self.buttonA.config(bg="#D3D3D3")
        else:
            self.buttonB.config(bg="#D3D3D3")

    # Graceful shutdown
    def closeWindow(self):
        if self.recording:
            self.stopRecording()
        if self.jobId:
            self.root.after_cancel(self.jobId)
        self.root.destroy()


# Stand-alone entry point
def main():
    root = tk.Tk()
    Display(root)
    root.mainloop()


if __name__ == "__main__":
    main()
