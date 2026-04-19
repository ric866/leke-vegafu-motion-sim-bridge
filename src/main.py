import tkinter as tk
import queue
import atexit
from network import NetworkBackend
from gui import VegaGUI


def main():
    print("[MAIN] Starting Vega Mission Control Initialization...")
    root = tk.Tk()

    # Thread-safe queues for cross-module communication
    print("[MAIN] Creating thread-safe message queues...")
    gui_queue = queue.Queue()
    cmd_queue = queue.Queue()

    # Initialize Backend
    print("[MAIN] Spawning NetworkBackend thread...")
    backend = NetworkBackend(gui_queue, cmd_queue)
    backend.start()

    # Ensure threads close cleanly
    atexit.register(backend.stop)
    print("[MAIN] Registered exit handlers.")

    # Initialize GUI
    print("[MAIN] Building Tkinter GUI...")
    VegaGUI(root, gui_queue, cmd_queue)

    # Start Application
    print("[MAIN] Handing over to Tkinter mainloop...")
    root.mainloop()


if __name__ == "__main__":
    main()
