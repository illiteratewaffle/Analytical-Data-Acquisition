class Settings:
    def __init__(self):
        self.runTime = 100 # cycle runtime in seconds
        self.operatorInitials = ""

    def setRunTime(self, time: int) -> None:
        self.runTime = time

    def setOperatorInitials(self, initials: str) -> None:
        self.operatorInitials = initials
