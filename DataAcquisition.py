from mcculw import ul
from mcculw.enums import ULRange
from mcculw.ul import ULError
from mcculw.device_info import DaqDeviceInfo

import time
from datetime import datetime

class DataAcquisition:
    def __init__(self):
        # board number: found in InstaCal
        self.board_num = 0
        # channel/range: see ports in MCCDAQ manual
        self.channel = 0
        self.ai_range = ULRange.BIP20VOLTS  # "ai" = analog input

        self.data = []
        self.startTime = time.perf_counter()

        self.operatorInitials = "NULL"

    def mainLoop(self):
        self.startTime = time.perf_counter()
        
        # todo: make it run for x amount of time
        #while (1 == 1):
        for i in range(3000):
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

    def recordData(self, time: float, signal: float):
        self.data.append([time, signal])

    def writeData(self, data: list):

        fullFilename = self.operatorInitials + "_" + self.getSystemTime() + ".txt"
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