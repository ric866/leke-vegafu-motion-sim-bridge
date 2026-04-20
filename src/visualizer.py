import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import socket
import json
import threading
import sys

# Calibration
MAX_PULSE = 240000
SCALE_FACTOR = 10.0 / MAX_PULSE

# Rig Geometry
MOTOR_X = [0, 5, -5]
MOTOR_Y = [5, -5, -5]


class LiveVisualizer:
    def __init__(self, port=9001, debug=False):
        self.port = port
        self.debug = debug
        self.running = True
        self.current_frame = [120000, 120000, 120000]  # Safe Pos Start

        if self.debug:
            print(f"[VIS INIT] Starting Visualizer Engine on Port {self.port}")

        self.fig = plt.figure(figsize=(8, 6))
        self.ax = self.fig.add_subplot(111, projection="3d")

        self.rx_thread = threading.Thread(target=self._receive_data, daemon=True)
        self.rx_thread.start()

    def _receive_data(self):
        if self.debug:
            print("[VIS THREAD] Receiver thread started.")
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", self.port))
        sock.settimeout(0.5)

        while self.running:
            try:
                data, addr = sock.recvfrom(1024)
                msg = json.loads(data.decode("utf-8"))
                if "m1" in msg:
                    self.current_frame = [msg["m1"], msg["m2"], msg["m3"]]
            except socket.timeout:
                pass
            except Exception as e:
                if self.debug:
                    print(f"[VIS RX ERROR] {e}")
        sock.close()

    def update_scene(self, frame_idx):
        self.ax.clear()

        self.ax.set_title("Live Vega Rig Motion")
        self.ax.set_xlim(-10, 10)
        self.ax.set_ylim(-10, 10)
        self.ax.set_zlim(0, 15)
        self.ax.set_xlabel("Left/Right")
        self.ax.set_ylabel("Front/Back")
        self.ax.set_zlabel("Height")

        z_vals = [m * SCALE_FACTOR for m in self.current_frame]

        for i in range(3):
            self.ax.plot(
                [MOTOR_X[i], MOTOR_X[i]],
                [MOTOR_Y[i], MOTOR_Y[i]],
                [0, z_vals[i]],
                color="black",
                linestyle="--",
                linewidth=2,
                alpha=0.5,
            )

        vertices = [list(zip(MOTOR_X, MOTOR_Y, z_vals))]
        seat = Poly3DCollection(vertices, alpha=0.8)

        height_avg = sum(z_vals) / 3
        if height_avg > 8:
            seat.set_facecolor("red")
        elif height_avg < 2:
            seat.set_facecolor("blue")
        else:
            seat.set_facecolor("cyan")

        self.ax.add_collection3d(seat)
        self.ax.text2D(
            0.05,
            0.95,
            f"M1: {self.current_frame[0]}\nM2: {self.current_frame[1]}\nM3: {self.current_frame[2]}",
            transform=self.ax.transAxes,
        )

    def start(self):
        if self.debug:
            print("[VIS START] Attaching animation loop to Matplotlib figure.")
        self.fig.canvas.mpl_connect("close_event", self.on_close)
        self.ani = animation.FuncAnimation(
            self.fig, self.update_scene, interval=50, cache_frame_data=False
        )
        plt.show()

        self.running = False
        if self.debug:
            print("[VIS SHUTDOWN] Safely exiting visualizer process.")
        sys.exit(0)

    def on_close(self, event):
        self.running = False


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9001
    is_debug = True if len(sys.argv) > 2 and sys.argv[2] == "1" else False
    vis = LiveVisualizer(port, debug=is_debug)
    vis.start()
