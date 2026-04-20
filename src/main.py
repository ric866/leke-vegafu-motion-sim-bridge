import tkinter as tk
import queue
import atexit
import sys
from network import NetworkBackend
from gui import VegaGUI


def main():
    # =========================================================================
    # PYINSTALLER SUBPROCESS CATCH:
    # If running as a compiled .exe, it uses this block to spawn the visualizer
    # =========================================================================
    if "--run-visualizer" in sys.argv:
        from visualizer import LiveVisualizer

        # Default fallback values
        port = 9001
        is_debug = False

        # Parse arguments passed by the GUI process
        if len(sys.argv) > 2:
            try:
                port = int(sys.argv[2])
            except ValueError:
                pass
        if len(sys.argv) > 3:
            is_debug = sys.argv[3] == "1"

        # Run visualizer loop, and instantly kill the process when closed
        vis = LiveVisualizer(port, debug=is_debug)
        vis.start()
        sys.exit(0)
    # =========================================================================

    # Normal Main GUI Startup
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
