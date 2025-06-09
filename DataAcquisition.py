from __future__ import annotations

from mcculw import ul
from mcculw.enums import ULRange, ScanOptions, FunctionType
from mcculw.ul import ULError
from mcculw.device_info import DaqDeviceInfo

import time
from datetime import datetime
from ctypes import cast, POINTER, c_ushort
from typing import List, Tuple

__all__ = ["DataAcquisition"]

class DataAcquisition:

    TIME_FORMAT = "%y%m%d_%H%M%S"

    def __init__(self) -> None:
        # board number: found in InstaCal
        self.board_num = 0

        # channel/range: see ports in MCCDAQ manual
        self.channel = 0
        self.ai_range = ULRange.BIP20VOLTS  # "ai" = analog input

        # sampling rate
        self.sample_rate = 10000 #Hz

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
            raw = ul.a_in(self.board_num, self.channel, self.ai_range)
            processed = ul.to_eng_units(self.board_num, self.ai_range, raw)
            return processed

        except ULError as e:  # Display the error (if needed)
            print("A UL error occurred. Code: " + str(e.errorcode) + " Message: " + e.message)

            return None

    def getTimeData(self) -> float:
        now = datetime.now()
        theBeginning = datetime(1904, 1, 1, 0, 0, 0)
        seconds_since_1904 = (now - theBeginning).total_seconds()
        return seconds_since_1904

    def recordData(self, time: float, signal: float) -> None:
        self.data.append([time, signal])

    def writeData(self, data: list = None) -> None:

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