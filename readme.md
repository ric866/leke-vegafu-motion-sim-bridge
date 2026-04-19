
Vega Mission Control Bridge
A modular, robust Python application designed to bridge motion telemetry from FlyPT to a Vega/IMAX Multi-Axis Motion Controller.

This software runs a strict, robust 20Hz UDP networking loop, allowing you to seamlessly switch between automated game telemetry and manual testing, read and flash internal controller parameters on the fly, and visualize your rig's physical movements in real-time.

✨ Features
Strict 20Hz Control Loop: Independent network backend ensures smooth motion data delivery regardless of UI lag.

Live 3D Visualization: Spawns an isolated Matplotlib process to render your actuator movements in real-time without slowing down the main control loop.

Dynamic Network Binding: Select your local network interface on the fly to securely bridge local loopback data (FlyPT) to external Ethernet hardware (Vega Rig).

Two-Way Controller Flashing: Read and write PA hex parameters directly to the controller's memory via the GUI.

Deep Packet Debugging: A rate-limited, auto-trimming verbose log that outputs raw hex payloads, timing warnings, and live actuator feedback without crashing the app.

🛠️ Prerequisites
Ensure you have Python 3.8+ installed. You will also need the matplotlib library for the 3D visualizer to function.

Install the required dependency via terminal/command prompt:

Bash
pip install matplotlib
📂 File Architecture
The project is split into five distinct modules to separate the user interface, hardware protocols, and network timing. Ensure all five files are kept in the same directory.

main.py - The Entry Point. Initializes thread-safe message queues, starts the network backend, and launches the Tkinter GUI. Run this file to start the app.

network.py - The Engine. A dedicated thread running at a strict 20Hz. Handles all UDP socket binding, reads FlyPT telemetry, parses hardware feedback, and broadcasts to the visualizer.

gui.py - The Interface. A modern Tkinter UI with three distinct tabs for Motion Control, Parameter Flashing, and Debugging.

protocol.py - The Translator. Handles the exact byte-packing and unpacking required by the IMAX controller manual (0x1301 for motion, 0x1101/0x1201 for flash settings).

visualizer.py - The Renderer. A standalone background process that listens on a local port (9001) and draws a 3D representation of the rig.

🚀 How to Run
Power on your Vega/IMAX controller and ensure it is connected to your local network.

Open your terminal or command prompt and navigate to the project folder.

Run the main script:

Bash
python main.py
🎮 Usage Guide
Tab 1: Motion & Control
Network Configuration: Select the specific network interface your PC is using to talk to FlyPT and the Controller. Click Apply Network Settings.

System Status: Click the large red "SYSTEM STOPPED" button to arm the rig. It will turn green.

Manual Override: Check "Enable Manual Mode" to instantly detach FlyPT telemetry. Use the sliders to manually push the actuators. The blue text shows your target position; the green text shows the live physical feedback from the controller.

Start 3D Visualizer: Launches the external 3D viewer. Close the viewer by clicking the 'X' on its window, and the main app will safely pause the visualizer data stream.

Tab 2: Controller Flash
Allows you to read/write internal PA parameters (e.g., Maximum Speed, Safety Strokes).

Click Read All to fetch the current state of the rig.

To change a value, type the new integer into the entry box and click Write.

Tab 3: Debug & Logs
Check the Verbose Logging box to see every UDP packet entering and leaving the system.

Note: The system logs roughly 40+ lines per second. To prevent memory crashes, the GUI automatically deletes old logs, keeping only the most recent 1,000 lines visible.

⚠️ Troubleshooting
"NET BIND ERROR" in Logs: You are likely trying to bind to an IP or port that is already in use. Ensure FlyPT is not trying to bind to the exact same Receive port as this app.

Visualizer doesn't open: Ensure matplotlib is installed (pip install matplotlib). Check the terminal console for syntax errors.

System stays in [SILENT] mode: Ensure the big red "SYSTEM STOPPED" button is toggled to Active, and that FlyPT is actively sending UDP packets to the correct port.
