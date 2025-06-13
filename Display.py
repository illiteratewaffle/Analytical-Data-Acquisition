import time
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

import matplotlib
matplotlib.use("TkAgg")  # use Tk backend for embedding
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

from DataAcquisition import DataAcquisition
from Valves import Valves


class Display:
    """Main GUI / plotting class."""

    def __init__(self, root):
        self.root = root
        self.root.title("Real‑Time Signal Monitor")

        # Data acquisition object
        self.daq = DataAcquisition()

        # GUI refresh rate depends on DAQ update size
        self.blockMS = max(1, int(round(1000 * self.daq.blockSize / self.daq.samplingFrequency)))

        # Acquisition state
        self.recording = True
        self.startTime = time.perf_counter()

        # Duration of recording data (seconds)
        self.maxDuration = 30

        # ---- TOP BAR: operator initials ----
        top = ttk.Frame(root, padding=(10, 5))
        top.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top, text="Operator Initials:").grid(row=0, column=0, sticky="w")
        self.initialsVar = tk.StringVar()
        initialsEntry = ttk.Entry(top, width=5, textvariable=self.initialsVar)
        initialsEntry.grid(row=0, column=1, sticky="w", padx=(2, 15))
        initialsEntry.focus_set()

        ttk.Separator(root, orient="horizontal").pack(fill=tk.X, pady=4)

        # ---- MAIN AREA: information (left) + valve controls (right) ----
        main = ttk.Frame(root)
        main.pack(side=tk.TOP, fill=tk.X, padx=10)

        # Info panel (left)
        info = ttk.Frame(main)
        info.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Time / signal readouts
        ttk.Label(info, text="Time Elapsed (s):").grid(row=0, column=0, sticky="w")
        self.timeVar = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.timeVar).grid(row=0, column=1, sticky="w", padx=(4, 20))

        ttk.Label(info, text="Current Signal (V):").grid(row=0, column=2, sticky="w")
        self.signalVar = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.signalVar).grid(row=0, column=3, sticky="w", padx=(4, 20))

        ttk.Label(info, text="Time Remaining (s):").grid(row=0, column=4, sticky="w")
        self.remainingVar = tk.StringVar(value="0.0000")
        ttk.Label(info, textvariable=self.remainingVar).grid(row=0, column=5, sticky="w")

        # ---- Y‑axis controls (new) ----
        yctrl = ttk.Frame(info)
        yctrl.grid(row=1, column=0, columnspan=6, sticky="w", pady=(6, 0))

        self.autoscaleVar = tk.BooleanVar(value=True)
        auto_cb = ttk.Checkbutton(yctrl, text="Autoscale Y", variable=self.autoscaleVar, command=self._toggleAutoscale)
        auto_cb.pack(side=tk.LEFT)

        ttk.Label(yctrl, text="Y min:").pack(side=tk.LEFT, padx=(10, 2))
        self.yMinVar = tk.StringVar(value="0")
        self.yMinEntry = ttk.Entry(yctrl, width=7, textvariable=self.yMinVar, state="disabled")
        self.yMinEntry.pack(side=tk.LEFT)

        ttk.Label(yctrl, text="Y max:").pack(side=tk.LEFT, padx=(6, 2))
        self.yMaxVar = tk.StringVar(value="1")
        self.yMaxEntry = ttk.Entry(yctrl, width=7, textvariable=self.yMaxVar, state="disabled")
        self.yMaxEntry.pack(side=tk.LEFT)

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

        # ---- Matplotlib figure ----
        self.fig, self.ax = plt.subplots(figsize=(6, 4))
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("Signal (V)")
        self.line, = self.ax.plot([], [], lw=1.3)

        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Data containers
        self.xData: list[float] = []
        self.yData: list[float] = []

        # Schedule first GUI update
        self.jobId: str | None = self.root.after(self.blockMS, self.updateLoop)

        # Close handler
        self.root.protocol("WM_DELETE_WINDOW", self.closeWindow)

    # ------------------------------------------------------------------
    # Valve handling
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Y‑axis scaling helpers
    # ------------------------------------------------------------------
    def _toggleAutoscale(self) -> None:
        """Enable/disable the manual Y‑limit entry fields."""
        state = "disabled" if self.autoscaleVar.get() else "normal"
        self.yMinEntry.config(state=state)
        self.yMaxEntry.config(state=state)

        # Apply limits immediately when switching to manual
        if not self.autoscaleVar.get():
            limits = self._getManualYLimits()
            if limits:
                self.ax.set_ylim(limits)
                self.canvas.draw_idle()

    def _getManualYLimits(self):
        """Parse manual Y‑axis limits; return (ymin, ymax) or None if invalid."""
        try:
            ymin = float(self.yMinVar.get())
            ymax = float(self.yMaxVar.get())
            if ymin >= ymax:
                raise ValueError
            return ymin, ymax
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Main update loop
    # ------------------------------------------------------------------
    def updateLoop(self) -> None:
        if self.recording:
            elapsed = time.perf_counter() - self.startTime

            # Stop after maxDuration
            if elapsed >= self.maxDuration:
                self.recording = False
                self.writeDataToFile()
                return

            try:
                meanVoltage = self.daq.getSignalData()
            except Exception as exc:
                print("Error reading signal:", exc)
                meanVoltage = None

            if meanVoltage is not None:
                remaining = max(0.0, self.maxDuration - elapsed)

                # Store data
                self.xData.append(elapsed)
                self.yData.append(meanVoltage)

                # Update readouts
                self.timeVar.set(f"{elapsed:.4f}")
                self.remainingVar.set(f"{remaining:.4f}")
                self.signalVar.set(f"{meanVoltage:.4f}")

                # Update plot data
                self.line.set_data(self.xData, self.yData)

                if self.autoscaleVar.get():
                    # Dynamic autoscale
                    self.ax.relim()
                    self.ax.autoscale_view()
                else:
                    limits = self._getManualYLimits()
                    if limits:
                        self.ax.set_ylim(limits)

                self.canvas.draw_idle()

        # Reschedule next refresh
        self.jobId = self.root.after(self.blockMS, self.updateLoop)

    # ------------------------------------------------------------------
    # File IO helpers
    # ------------------------------------------------------------------
    def writeDataToFile(self) -> None:
        if not self.xData:  # nothing collected
            return

        initials = self.initialsVar.get().strip().upper() or "NULL"
        self.daq.operatorInitials = initials

        mac_epoch = datetime(1904, 1, 1)
        run_start = datetime.now() - timedelta(seconds=self.xData[-1])
        out_records: list[tuple[float, float]] = []
        for t_rel, v in zip(self.xData, self.yData):
            epoch_secs = (run_start + timedelta(seconds=t_rel) - mac_epoch).total_seconds()
            out_records.append((epoch_secs, v))

        self.daq.writeData(out_records)

    # ------------------------------------------------------------------
    # Window / application shutdown
    # ------------------------------------------------------------------
    def closeWindow(self) -> None:
        if self.jobId is not None:
            self.root.after_cancel(self.jobId)
            self.jobId = None

        if self.xData:
            self.writeDataToFile()

        self.root.destroy()


# --------------------------------------------------
# Stand‑alone execution
# --------------------------------------------------

def main():
    root = tk.Tk()
    Display(root)
    root.mainloop()


if __name__ == "__main__":
    main()
