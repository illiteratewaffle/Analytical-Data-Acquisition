import time
import queue
import tkinter as tk
from tkinter import ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

from DataAcquisition import DataAcquisition
from Valves import Valves


class Display:
    """Real-time GUI with two valve-swap schedules and X/Y autoscaling."""

    OPEN_CLR = "#90EE90"
    CLOSED_CLR = "#D3D3D3"

    # ──────────────────────────────────────────────────────────
    #  Construction
    # ──────────────────────────────────────────────────────────
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Real-Time Signal Monitor")

        self.daq = DataAcquisition()
        self.dataQueue = queue.Queue()
        self.daq.attach_queue(self.dataQueue)

        self.blockMS = max(
            1,
            round(1000 * self.daq.blockSize / self.daq.samplingFrequency),
        )

        # Run-state
        self.recording = False
        self.maxDuration = 30.0
        self.currentValve = "A"
        self.swapJobId1 = None
        self.swapJobId2 = None
        self.swap1Time = 0.0
        self.swap2Time = 0.0

        # Build GUI
        self._build_widgets()

        self.jobId = self.root.after(self.blockMS, self.updateLoop)
        self.root.protocol("WM_DELETE_WINDOW", self.closeWindow)

    # ──────────────────────────────────────────────────────────
    #  GUI layout
    # ──────────────────────────────────────────────────────────
    def _build_widgets(self):
        # Top bar
        top = ttk.Frame(self.root, padding=(10, 5))
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

        ttk.Separator(self.root, orient="horizontal").pack(fill=tk.X, pady=4)

        # Main frame
        main = ttk.Frame(self.root)
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
        self.durationVar = tk.StringVar(value="30")
        ttk.Entry(dur, width=7, textvariable=self.durationVar).pack(side=tk.LEFT)

        ttk.Label(dur, text="Presets:").pack(side=tk.LEFT, padx=(10, 2))
        ttk.Button(dur, text="2 min", width=7, command=lambda: self.durationVar.set(str(2 * 60))).pack(side=tk.LEFT)
        ttk.Button(dur, text="5 min", width=7, command=lambda: self.durationVar.set(str(5 * 60))).pack(side=tk.LEFT, padx=2)
        ttk.Button(dur, text="10 min", width=7, command=lambda: self.durationVar.set(str(10 * 60))).pack(side=tk.LEFT)

        # Valve-swap rows
        self._build_schedule_row(
            info,
            row=2,
            start_label="Swap #1 – initial valve:",
            time_label="Swap #1 in (s):",
            prefix="1",
        )

        self._build_schedule_row(
            info,
            row=3,
            start_label="Swap #2 – target valve:",
            time_label="Swap #2 in (s):",
            prefix="2",
        )

        self._updateScheduleLabels()

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

        self.valves = Valves()

        self.buttonA = tk.Button(valve_f, text="Open A", width=10, bg=self.CLOSED_CLR, command=self.toggleValveA)
        self.buttonA.pack(pady=(0, 5))

        self.buttonB = tk.Button(valve_f, text="Open B", width=10, bg=self.CLOSED_CLR, command=self.toggleValveB)
        self.buttonB.pack()

        # Matplotlib figure
        self.fig, self.ax = plt.subplots(figsize=(6, 4))
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Signal (V)")

        self.line, = self.ax.plot([], [], lw=1.3)

        FigureCanvasTkAgg(self.fig, master=self.root).get_tk_widget().pack(fill=tk.BOTH, expand=True)

        self.xData = []
        self.yData = []

    # Helper to build each schedule row
    def _build_schedule_row(self, parent, row: int, start_label: str, time_label: str, prefix: str):
        frm = ttk.Frame(parent)
        frm.grid(row=row, column=0, columnspan=6, sticky="w", pady=(6, 0))

        col0 = ttk.Frame(frm)
        col0.grid(row=0, column=0, sticky="w")
        ttk.Label(col0, text=start_label).pack(anchor="w")

        setattr(self, f"startValveVar{prefix}", tk.StringVar(value="A"))
        for v in ("A", "B"):
            ttk.Radiobutton(
                col0,
                text=f"Valve {v}",
                value=v,
                variable=getattr(self, f"startValveVar{prefix}"),
                command=self._updateScheduleLabels,
            ).pack(anchor="w")

        col1 = ttk.Frame(frm)
        col1.grid(row=0, column=1, padx=(25, 0), sticky="w")
        ttk.Label(col1, text=time_label).pack(anchor="w")

        setattr(self, f"swapTimeVar{prefix}", tk.StringVar(value="15"))
        ent = ttk.Entry(col1, width=7, textvariable=getattr(self, f"swapTimeVar{prefix}"))
        ent.pack(anchor="w")
        ent.bind("<FocusOut>", lambda *_: self._updateScheduleLabels())
        ent.bind("<Return>", lambda *_: self._updateScheduleLabels())

        col2 = ttk.Frame(frm)
        col2.grid(row=0, column=2, padx=(25, 0), sticky="w")
        summary_var = tk.StringVar()
        ttk.Label(col2, textvariable=summary_var).pack(anchor="w")
        setattr(self, f"scheduleDispVar{prefix}", summary_var)

    # Update summary labels without mutating entry text
    def _updateScheduleLabels(self):
        init_v = self.startValveVar1.get()
        target_v = "B" if init_v == "A" else "A"
        t1 = self._safe_float(self.swapTimeVar1, 0.0)
        self.scheduleDispVar1.set(
            f"Initial valve: {init_v} | Target valve: {target_v} in {int(t1)} seconds"
        )

        target_v2 = self.startValveVar2.get()
        t2 = self._safe_float(self.swapTimeVar2, 0.0)
        self.scheduleDispVar2.set(
            f"Target valve: {target_v2} in {int(t2)} seconds"
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

    def _autoSwap1(self):
        self._setValveState("B" if self.currentValve == "A" else "A")
        self.swapJobId1 = None

    def _autoSwap2(self):
        self._setValveState(self.startValveVar2.get())
        self.swapJobId2 = None

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

        self.maxDuration = max(0.1, self._safe_float(self.durationVar, 30.0))

        self.currentValve = self.startValveVar1.get()
        self.swap1Time = max(0.0, self._safe_float(self.swapTimeVar1, 0.0))
        self.swap2Time = max(0.0, self._safe_float(self.swapTimeVar2, 0.0))

        self._setValveState(self.currentValve)

        if self.swap1Time > 0:
            self.swapJobId1 = self.root.after(int(self.swap1Time * 1000), self._autoSwap1)

        if self.swap2Time > 0:
            self.swapJobId2 = self.root.after(int(self.swap2Time * 1000), self._autoSwap2)

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

        for jid in (self.swapJobId1, self.swapJobId2):
            if jid:
                self.root.after_cancel(jid)

        self.swapJobId1 = None
        self.swapJobId2 = None

        self.startBtn.config(state="normal")
        self.stopBtn.config(state="disabled")

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
                if self.swapJobId2 and self.swap2Time >= self.maxDuration:
                    self._autoSwap2()
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

        for jid in (self.swapJobId1, self.swapJobId2):
            if jid:
                self.root.after_cancel(jid)

        self.root.destroy()


# Stand-alone entry point
def main():
    root = tk.Tk()
    Display(root)
    root.mainloop()


if __name__ == "__main__":
    main()
