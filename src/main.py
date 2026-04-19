import tkinter as tk
import queue
import atexit
from network import NetworkBackend
from gui import VegaGUI


def main():
    root = tk.Tk()

    # Thread-safe queues for cross-module communication
    gui_queue = queue.Queue()
    cmd_queue = queue.Queue()

    # Initialize Backend
    backend = NetworkBackend(gui_queue, cmd_queue)
    backend.start()

    # Ensure threads close cleanly
    atexit.register(backend.stop)

    # Initialize GUI (Assignment removed to clear linter warning)
    VegaGUI(root, gui_queue, cmd_queue)

    # Start Application
    root.mainloop()


if __name__ == "__main__":
    main()
