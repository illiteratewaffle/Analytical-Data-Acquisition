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
    OPEN_CLR   = "#90EE90"   # light-green when valve is open
    CLOSED_CLR = "#D3D3D3"   # light-grey  when valve is closed

    # ────────────────────────────────────────────────────────────
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Real-Time Signal Monitor")

        # -- DAQ back-end --
        self.daq       = DataAcquisition()
        self.dataQueue = queue.Queue(maxsize=1000)
        self.daq.attach_queue(self.dataQueue)

        self.blockMS = max(
            1,
            round(1000 * self.daq.blockSize / self.daq.samplingFrequency),
        )

        # Run-state
        self.recording    = False
        self.maxDuration  = 30.0
        self.swapAfterSec = 15.0
        self.currentValve = "A"
        self.swapJobId    = None  # stores the scheduled after() id

        # Build GUI & start periodic refresh
        self._build_widgets()
        self.jobId = self.root.after(self.blockMS, self.updateLoop)
        self.root.protocol("WM_DELETE_WINDOW", self.closeWindow)

    # ────────────────────────────────────────────────────────────
    #  GUI construction  (unchanged except comments removed)
    # ────────────────────────────────────────────────────────────
    def _build_widgets(self):
        top = ttk.Frame(self.root, padding=(10, 5));  top.pack(fill=tk.X)
        ttk.Label(top, text="Operator Initials:").grid(row=0, column=0, sticky="w")
        self.initialsVar = tk.StringVar()
        ttk.Entry(top, width=5, textvariable=self.initialsVar).grid(
            row=0, column=1, padx=(2, 15)
        )
        self.startBtn = ttk.Button(top, text="Start", command=self.startRecording)
        self.startBtn.grid(row=0, column=2, padx=(10, 2))
        self.stopBtn  = ttk.Button(top, text="Stop",  command=self.stopRecording,
                                   state="disabled")
        self.stopBtn.grid(row=0, column=3)
        ttk.Separator(self.root, orient="horizontal").pack(fill=tk.X, pady=4)

        main = ttk.Frame(self.root);  main.pack(fill=tk.X, padx=10)
        info = ttk.Frame(main);       info.pack(side=tk.LEFT, expand=True)

        # ── live readouts
        ttk.Label(info, text="Time Elapsed (s):").grid(row=0, column=0, sticky="w")
        self.timeVar = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.timeVar).grid(row=0, column=1, padx=(4, 20))

        ttk.Label(info, text="Current Signal (V):").grid(row=0, column=2, sticky="w")
        self.signalVar = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.signalVar).grid(row=0, column=3, padx=(4, 20))

        ttk.Label(info, text="Time Remaining (s):").grid(row=0, column=4, sticky="w")
        self.remainingVar = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.remainingVar).grid(row=0, column=5)

        # ── run-duration row
        durRow = ttk.Frame(info);  durRow.grid(row=1, column=0, columnspan=6,
                                               sticky="w", pady=(6, 0))
        ttk.Label(durRow, text="Run Duration (s):").pack(side=tk.LEFT, padx=(0, 2))
        self.durationVar = tk.StringVar(value="30")
        ttk.Entry(durRow, width=7, textvariable=self.durationVar).pack(side=tk.LEFT)
        ttk.Label(durRow, text="Presets:").pack(side=tk.LEFT, padx=(10, 2))
        for mins in (2, 5, 10):
            ttk.Button(durRow, text=f"{mins} min", width=7,
                       command=lambda m=mins: self.durationVar.set(str(m*60))
            ).pack(side=tk.LEFT, padx=2 if mins != 2 else 0)

        # ── valve-schedule row (3 columns)
        valveCfg = ttk.Frame(info);  valveCfg.grid(row=2, column=0, columnspan=6,
                                                   sticky="w", pady=(6, 0))
        # column 0 – start valve
        col0 = ttk.Frame(valveCfg);  col0.grid(row=0, column=0, sticky="w")
        ttk.Label(col0, text="Start Valve:").pack(anchor="w")
        self.startValveVar = tk.StringVar(value="A")
        for v in ("A", "B"):
            ttk.Radiobutton(col0, text=f"Valve {v}", value=v, variable=self.startValveVar,
                            command=self._updateScheduleLabel).pack(anchor="w")

        # column 1 – swap-after entry
        col1 = ttk.Frame(valveCfg);  col1.grid(row=0, column=1, padx=(25, 0), sticky="w")
        ttk.Label(col1, text="Swap after (s):").pack(anchor="w")
        self.swapTimeVar = tk.StringVar(value="15")
        swapEntry = ttk.Entry(col1, width=7, textvariable=self.swapTimeVar)
        swapEntry.pack(anchor="w")
        swapEntry.bind("<FocusOut>", lambda *_: self._updateScheduleLabel())
        swapEntry.bind("<Return>",   lambda *_: self._updateScheduleLabel())

        # column 2 – read-only summary
        col2 = ttk.Frame(valveCfg);  col2.grid(row=0, column=2, padx=(25, 0), sticky="w")
        self.scheduleDispVar = tk.StringVar();  ttk.Label(col2,
            textvariable=self.scheduleDispVar).pack(anchor="w")
        self._updateScheduleLabel()

        # ── Y-axis controls
        yctrl = ttk.Frame(info);  yctrl.grid(row=3, column=0, columnspan=6,
                                             sticky="w", pady=(6, 0))
        self.autoscaleVar = tk.BooleanVar(value=True)
        ttk.Checkbutton(yctrl, text="Autoscale Y", variable=self.autoscaleVar,
                        command=self._toggleAutoscale).pack(side=tk.LEFT)
        ttk.Label(yctrl, text="Y min:").pack(side=tk.LEFT, padx=(10, 2))
        self.yMinVar = tk.StringVar(value="0")
        self.yMinEntry = ttk.Entry(yctrl, width=7, textvariable=self.yMinVar,
                                   state="disabled"); self.yMinEntry.pack(side=tk.LEFT)
        ttk.Label(yctrl, text="Y max:").pack(side=tk.LEFT, padx=(6, 2))
        self.yMaxVar = tk.StringVar(value="1")
        self.yMaxEntry = ttk.Entry(yctrl, width=7, textvariable=self.yMaxVar,
                                   state="disabled"); self.yMaxEntry.pack(side=tk.LEFT)

        # ── manual override buttons (right side)
        valve_f = ttk.Frame(main, padding=(20, 0));  valve_f.pack(side=tk.RIGHT,
                                                                  anchor="ne")
        self.valves = Valves()
        self.buttonA = tk.Button(valve_f, text="Open A", width=10,
                                 bg=self.CLOSED_CLR, command=self.toggleValveA)
        self.buttonA.pack(pady=(0, 5))
        self.buttonB = tk.Button(valve_f, text="Open B", width=10,
                                 bg=self.CLOSED_CLR, command=self.toggleValveB)
        self.buttonB.pack()

        # ── plot
        self.fig, self.ax = plt.subplots(figsize=(6, 4))
        self.ax.set_xlabel("Time (s)");  self.ax.set_ylabel("Signal (V)")
        self.line, = self.ax.plot([], [], lw=1.3)
        FigureCanvasTkAgg(self.fig, master=self.root).get_tk_widget().pack(fill=tk.BOTH,
                                                                           expand=True)
        self.xData, self.yData = [], []

    # ────────────────────────────────────────────────────────────
    #  Helpers
    # ────────────────────────────────────────────────────────────
    def _updateScheduleLabel(self):
        start = self.startValveVar.get()
        try:
            swap = float(self.swapTimeVar.get());  assert swap >= 0
        except (ValueError, AssertionError):
            swap = 0.0;  self.swapTimeVar.set("0")
        self.scheduleDispVar.set(f"Starts at Valve {start} | Swap at {swap:.0f} s")

    def _setValveState(self, valve: str):
        """Open the requested valve ('A' or 'B') and recolour buttons."""
        if valve == "A":
            self.valves.set_valve_position_a()
            self.buttonA.config(bg=self.OPEN_CLR);  self.buttonB.config(bg=self.CLOSED_CLR)
        else:
            self.valves.set_valve_position_b()
            self.buttonB.config(bg=self.OPEN_CLR);  self.buttonA.config(bg=self.CLOSED_CLR)
        self.currentValve = valve

    def _autoSwapValves(self):
        """Callback scheduled with root.after — swaps once, then forgets."""
        self._setValveState("B" if self.currentValve == "A" else "A")
        self.swapJobId = None  # finished

    # ────────────────────────────────────────────────────────────
    #  Y-axis helpers
    # ────────────────────────────────────────────────────────────
    def _toggleAutoscale(self):
        state = "disabled" if self.autoscaleVar.get() else "normal"
        self.yMinEntry.config(state=state);  self.yMaxEntry.config(state=state)
        if not self.autoscaleVar.get():
            lims = self._manualYLimits();  self.ax.set_ylim(lims or self.ax.get_ylim())
            self.fig.canvas.draw_idle()

    def _manualYLimits(self):
        try:
            ymin = float(self.yMinVar.get());  ymax = float(self.yMaxVar.get())
            if ymin >= ymax:  raise ValueError
            return ymin, ymax
        except ValueError:
            return None

    # ────────────────────────────────────────────────────────────
    #  Start / Stop
    # ────────────────────────────────────────────────────────────
    def startRecording(self):
        if self.recording:
            return

        # duration
        try:  self.maxDuration = max(0.1, float(self.durationVar.get()))
        except ValueError:  self.maxDuration = 30.0;  self.durationVar.set("30")

        # schedule
        self.currentValve = self.startValveVar.get()
        try:  self.swapAfterSec = max(0.0, float(self.swapTimeVar.get()))
        except ValueError:  self.swapAfterSec = 15.0;  self.swapTimeVar.set("15")

        # hardware & colours
        self._setValveState(self.currentValve)

        # schedule automatic swap
        if self.swapAfterSec > 0:
            self.swapJobId = self.root.after(int(self.swapAfterSec*1000),
                                             self._autoSwapValves)
        else:
            self.swapJobId = None

        # DAQ bookkeeping
        self.daq.operatorInitials = (self.initialsVar.get().strip().upper() or "NULL")
        self.daq.startValve, self.daq.swapAfterSec = self.currentValve, self.swapAfterSec

        # reset plot & start DAQ
        self.xData.clear();  self.yData.clear();  self.line.set_data([], [])
        self.startTime  = time.perf_counter();  self.recording = True;  self.daq.start()
        self.startBtn.config(state="disabled");  self.stopBtn.config(state="normal")

    def stopRecording(self):
        if not self.recording:
            return
        self.recording = False;  self.daq.stop()
        if self.swapJobId:  self.root.after_cancel(self.swapJobId);  self.swapJobId = None
        self.startBtn.config(state="normal");  self.stopBtn.config(state="disabled")

    # ────────────────────────────────────────────────────────────
    #  Periodic GUI refresh
    # ────────────────────────────────────────────────────────────
    def updateLoop(self):
        while not self.dataQueue.empty():
            t_rel, v = self.dataQueue.get_nowait()
            self.xData.append(t_rel);  self.yData.append(v)

        if self.xData:
            elapsed = self.xData[-1];  remaining = max(0.0, self.maxDuration - elapsed)
            self.timeVar.set(f"{elapsed:.4f}");     self.remainingVar.set(f"{remaining:.4f}")
            self.signalVar.set(f"{self.yData[-1]:.4f}")
            self.line.set_data(self.xData, self.yData)
            (self.ax.relim() or self.ax.autoscale_view()) if self.autoscaleVar.get() else \
                self.ax.set_ylim(self._manualYLimits() or self.ax.get_ylim())
            self.fig.canvas.draw_idle()
            if self.recording and elapsed >= self.maxDuration:
                self.stopRecording()

        self.jobId = self.root.after(self.blockMS, self.updateLoop)

    # ────────────────────────────────────────────────────────────
    #  Manual overrides
    # ────────────────────────────────────────────────────────────
    def toggleValveA(self):
        if self.currentValve != "A":
            self._setValveState("A")

    def toggleValveB(self):
        if self.currentValve != "B":
            self._setValveState("B")

    # ────────────────────────────────────────────────────────────
    #  Shutdown
    # ────────────────────────────────────────────────────────────
    def closeWindow(self):
        if self.recording:  self.stopRecording()
        if self.jobId:      self.root.after_cancel(self.jobId)
        if self.swapJobId:  self.root.after_cancel(self.swapJobId)
        self.root.destroy()


def main():
    root = tk.Tk();  Display(root);  root.mainloop()


if __name__ == "__main__":
    main()
