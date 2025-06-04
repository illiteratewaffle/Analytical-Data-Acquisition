from mcculw import ul
from mcculw.enums import ULRange
from mcculw.ul import ULError
from mcculw.device_info import DaqDeviceInfo

import time
import threading
from datetime import datetime

class DataAcquisition:

    SAMPLING_RATE_HZ = 10000 # 10 kHz target

    def __init__(self):
        # board number: found in InstaCal
        self.board_num = 0

        # channel/range: see ports in MCCDAQ manual
        self.channel = 0
        self.ai_range = ULRange.BIP20VOLTS  # "ai" = analog input

        # sampling rate config
        self._logging      = False
        self._log_thread   = None
        self._log_lock     = threading.Lock()

        self.data = []
        self.startTime = time.perf_counter()

        self.operatorInitials = "NULL"

    def mainLoop(self) -> None:
        self.startTime = time.perf_counter()

        # todo: make it run for x amount of time
        #while (1 == 1):
        for i in range(1):
            signalValue = self.getSignalData()
            timeValue = self.getTimeData(self.startTime)
            self.recordData(timeValue, signalValue)

        self.writeData(self.data)


    def getSignalData(self) -> (float | None):
        try:
            # GETS SIGNAL VALUE (in voltage)
            # Get a value from the device
            value = ul.a_in(self.board_num, self.channel, self.ai_range)
            # Convert the raw value to normal units
            units_value = ul.to_eng_units(self.board_num, self.ai_range, value)

            return units_value

        except ULError as e:  # Display the error (if needed)
            print("A UL error occurred. Code: " + str(e.errorcode) + " Message: " + e.message)

            return None

    def getTimeData(self, startTime) -> float:
        currentTime = time.perf_counter()
        timeElapsed = currentTime - startTime

        return timeElapsed

    def recordData(self, time: float, signal: float) -> None:
        self.data.append([time, signal])

    def writeData(self, data: list) -> None:

        fullFilename = self.operatorInitials.upper() + "_" + self.getSystemTime() # no file extension name
        dataFile = open(fullFilename, "w")

        # Data formatting and writes to file
        # TO FORMAT: [TIME] <TAB> [SIGNAL] <NEW LINE>
        for i in range(len(data)):
            time_i = self.data[i][0]
            signal_i = self.data[i][1]

            message = f"{time_i:.4f}\t{signal_i:.4f}\n"
            dataFile.write(message)

        dataFile.close()

    def getSystemTime(self) -> str:
        now = datetime.now()
        formatted = now.strftime("%y%m%d_%H%M%S")

        return formatted

    def _log_loop(self, duration_s: float):
        interval   = 1.0 / self.SAMPLING_RATE_HZ
        start      = time.perf_counter()
        next_tick  = start
        while self._logging and time.perf_counter() - start < duration_s:
            t_rel   = time.perf_counter() - start
            value   = self.getSignalData()
            with self._log_lock:
                self.data.append((t_rel, value))
            next_tick += interval
            time.sleep(max(0.0, next_tick - time.perf_counter()))
        self._logging = False           # finishes automatically

    def start_logging(self, duration_s: float):
        if self._logging:      # already running
            return
        self.data     = []     # clear previous run
        self._logging = True
        self._log_thread = threading.Thread(
            target=self._log_loop, args=(duration_s,), daemon=True)
        self._log_thread.start()

    def stop_logging(self):
        self._logging = False
        if self._log_thread:
            self._log_thread.join()

    def is_logging(self) -> bool:       # helper for GUI
        return self._logging