# Vega Mission Control Bridge

A modular Python application designed to bridge motion telemetry to a **Vega/IMAX Multi-Axis Motion Controller**.

This software runs a strict UDP networking loop, allowing you to seamlessly switch between automated game telemetry and manual testing, read and flash internal controller parameters, and visualize your rig's physical movements in real-time.

## ✨ Key Features

* **Adjustable Control Loop:** Runs independently of the UI at a tunable 20Hz, ensuring smooth motion data delivery.
* **Adjustable Parking & Slew Rates:** Features a strict state machine (`STARTING` -> `ACTIVE` -> `PARKING` -> `STOPPED`). Uses split Max Delta limits to ensure fast in-game response while keeping manual slider movements and parking sequences smooth and safe.
* **Hardware Stroke Limits:** User-definable Minimum and Maximum limits prevent the rig from exceeding desired boundaries during gameplay and manual testing.
* **Auto-Saving Configuration:** Automatically generates a `vega_config.json` file to remember your IP bindings, ports, and tuning parameters between sessions.
* **Live 3D Visualization:** Spawns an isolated Matplotlib process to render your actuator movements in real-time without slowing down the main control loop. Fully compatible with single-file `.exe` builds via process multiplexing.
* **Two-Way Controller Flashing:** Read and write PA hex parameters directly to the controller's memory via the GUI.
* **Packet Debugging:** A rate-limited, auto-trimming verbose log that outputs raw hex payloads, timing warnings, and live actuator feedback without crashing the app.

---

## 🛠️ Prerequisites (If running from source)

Ensure you have **Python 3.8+** installed. You will also need the `matplotlib` library for the 3D visualizer to function.

Install the required dependency via terminal/command prompt:

bash
pip install matplotlib


📂 File Architecture
The project is split into distinct modules to separate the user interface, hardware protocols, and network timing. Ensure all files are kept in the same directory.

main.py - The Entry Point. Initializes queues, starts the network backend, and handles PyInstaller subprocess routing for the visualizer.

network.py - The Engine. A dedicated thread running the state machine. Handles UDP socket binding, telemetry parsing, parking logic, and data broadcasting.

gui.py - The Interface. A modern Tkinter UI with three distinct tabs for Motion Control, Parameter Flashing, and Debugging.

protocol.py - The Translator. Handles the exact byte-packing required by the IMAX controller (0x1301 for motion, 0x1101/0x1201 for flash settings).

visualizer.py - The Renderer. A standalone background process that listens on a local port (9001) and draws a 3D representation of the rig.

vega_config.json - (Auto-Generated) Stores your saved network and tuning settings.

🚀 How to Run
Option A: From Source

Power on your Vega/IMAX controller and ensure it is connected to your local network.

Open your terminal/command prompt and navigate to the project folder.

Run: python main.py

Option B: Standalone Executable
Simply double-click VegaMissionControl.exe downloaded from Releases

🎮 Usage Guide
Tab 1: Motion & Control
Network & Tuning Configuration: Select your local network interface, define your ports, and set your hardware limits (Hz, Stroke Limits, and Deltas). Click Apply & Save Settings to write them to disk.

System Control: * Click START RIG to initialize the hardware. The rig will slowly rise to the Mid (Safe) Position.

Click STOP & PARK to disengage. The rig will smoothly lower itself to absolute zero and lock the network stream.

Manual Override: Check "Enable Manual Mode" to detach FlyPT telemetry. Use the sliders to manually test the actuators. The blue text shows your target position; the green text shows the live physical feedback from the controller.

Live 3D Motion: Launches the external 3D viewer. Close the viewer by clicking the 'X' on its window, and the main app will safely pause the visualizer data stream to save CPU.

Tab 2: Controller Flash
Allows you to read/write internal PA parameters (e.g., Maximum Speed, Safety Strokes).
## Your PC must be on the Controllers Master IP Address. ##

Click Read All to fetch the current state of the rig.

To change a value, type the new integer into the entry box and click Write.

Tab 3: Debug & Logs
Check the Verbose Logging box to see every UDP packet entering and leaving the system.

Note: The system logs roughly 40+ lines per second. To prevent memory crashes, the GUI automatically deletes old logs, keeping only the most recent 1,000 lines visible.

⚠️ Troubleshooting
"NET BIND ERROR" in Logs: You are likely trying to bind to an IP or port that is already in use. Ensure FlyPT is not trying to bind to the exact same Receive port as this app.

Visualizer doesn't open (Source): Ensure matplotlib is installed (pip install matplotlib).

Rig feels sluggish in-game: Increase the Auto Max Delta setting.

Rig is too violent when using sliders: Decrease the Manual/Park Delta setting.
