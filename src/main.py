import sys
import tkinter as tk
import queue
import atexit
from network import NetworkBackend
from gui import VegaGUI


def main():
    # --- PYINSTALLER EXECUTABLE SUBPROCESS CATCHER ---
    # When compiled to an .exe, we use this to safely launch the visualizer
    if len(sys.argv) > 1 and sys.argv[1] == "--visualizer":
        from visualizer import LiveVisualizer

        port = int(sys.argv[2]) if len(sys.argv) > 2 else 9001
        debug = True if len(sys.argv) > 3 and sys.argv[3] == "1" else False
        vis = LiveVisualizer(port, debug=debug)
        vis.start()
        sys.exit(0)

    # --- NORMAL GUI STARTUP ---
    print("[MAIN] Starting Vega Mission Control Initialization...")
    root = tk.Tk()

    print("[MAIN] Creating thread-safe message queues...")
    gui_queue = queue.Queue()
    cmd_queue = queue.Queue()

    print("[MAIN] Spawning NetworkBackend thread...")
    backend = NetworkBackend(gui_queue, cmd_queue)
    backend.start()

    atexit.register(backend.stop)
    print("[MAIN] Registered exit handlers.")

    print("[MAIN] Building Tkinter GUI...")
    VegaGUI(root, gui_queue, cmd_queue)

    print("[MAIN] Handing over to Tkinter mainloop...")
    root.mainloop()


if __name__ == "__main__":
    main()
