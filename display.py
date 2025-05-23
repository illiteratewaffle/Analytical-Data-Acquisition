import tkinter as tk

class Display:
    def __init__(self):
        root = tk.Tk()
        root.title("Signal")

        label = tk.Label(root, text="placeholder text")
        label.pack(side=tk.BOTTOM)

        root.mainloop()