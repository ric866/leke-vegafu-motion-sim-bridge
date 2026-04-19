import socket
import threading
import time
import select
import struct
from protocol import IMAXProtocol


class NetworkBackend:
    def __init__(self, gui_queue, cmd_queue):
        self.gui_queue = gui_queue
        self.cmd_queue = cmd_queue
        self.running = True
        self.scale_factor = 240000 / 65535.0

        # ADDED 'bind_ip' defaulting to localhost for safety
        self.config = {
            "bind_ip": "127.0.0.1",
            "rx_port": 10000,
            "tx_port": 8410,
            "vega_ip": "192.168.15.201",
            "vega_port": 7408,
            "safe_pos": 120000,
        }

        self.thread = threading.Thread(target=self._network_worker, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.running = False

    def _network_worker(self):
        sock_rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        out_m1 = out_m2 = out_m3 = self.config["safe_pos"]
        active = manual = debug = False
        silence_countdown = 40
        last_log_time = 0  # Track when we last printed to the log

        try:
            sock_rx.bind((self.config["bind_ip"], self.config["rx_port"]))
            sock_tx.bind((self.config["bind_ip"], self.config["tx_port"]))
            sock_rx.setblocking(False)
            sock_tx.setblocking(False)
        except Exception as e:
            self.gui_queue.put({"type": "LOG", "data": f"NET BIND ERROR: {e}"})

        while self.running:
            loop_start = time.time()
            loop_start = time.time()
            should_send_motion = False

            # --- 1. Process GUI Commands ---
            while not self.cmd_queue.empty():
                cmd = self.cmd_queue.get()
                if cmd["type"] == "CONFIG":
                    # Update config, close old sockets, and rebind
                    self.config.update(
                        {
                            k: cmd[k]
                            for k in [
                                "bind_ip",
                                "rx_port",
                                "tx_port",
                                "vega_ip",
                                "vega_port",
                                "safe_pos",
                            ]
                        }
                    )
                    sock_rx.close()
                    sock_tx.close()
                    sock_rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock_tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    try:
                        # USE THE NEW BIND IP HERE
                        sock_rx.bind((self.config["bind_ip"], self.config["rx_port"]))
                        sock_tx.bind((self.config["bind_ip"], self.config["tx_port"]))
                        sock_rx.setblocking(False)
                        sock_tx.setblocking(False)
                        self.gui_queue.put(
                            {
                                "type": "LOG",
                                "data": f"NET RECONFIGURED (Listening on {self.config['bind_ip']})",
                            }
                        )
                    except Exception as e:
                        self.gui_queue.put(
                            {"type": "LOG", "data": f"NET REBIND FAIL: {e}"}
                        )

                elif cmd["type"] == "STATE":
                    active, manual, debug = (
                        cmd["active"],
                        cmd["manual"],
                        cmd.get("debug", False),
                    )
                    if active or manual:
                        silence_countdown = 40
                elif cmd["type"] == "MANUAL_POS":
                    out_m1, out_m2, out_m3 = cmd["m1"], cmd["m2"], cmd["m3"]
                elif cmd["type"] == "READ_PARAM":
                    pkt = IMAXProtocol.pack_read_register(cmd["address"])
                    sock_tx.sendto(
                        pkt, (self.config["vega_ip"], self.config["vega_port"])
                    )
                    if debug:
                        self.gui_queue.put(
                            {
                                "type": "LOG",
                                "data": f"[CMD] Read PA{cmd['address']:02X} sent.",
                            }
                        )
                elif cmd["type"] == "WRITE_PARAM":
                    pkt = IMAXProtocol.pack_write_register(cmd["address"], cmd["value"])
                    sock_tx.sendto(
                        pkt, (self.config["vega_ip"], self.config["vega_port"])
                    )
                    if debug:
                        self.gui_queue.put(
                            {
                                "type": "LOG",
                                "data": f"[CMD] Write PA{cmd['address']:02X} = {cmd['value']} sent.",
                            }
                        )

            # --- 2. Read Network ---
            readable, _, _ = select.select([sock_rx, sock_tx], [], [], 0)
            flypt_data = False
            raw_in = [0, 0, 0]

            for s in readable:
                if s is sock_rx:
                    try:
                        while True:
                            data, _ = s.recvfrom(1024)
                            if len(data) >= 8 and data[0] == 0xFF:
                                raw_in[0] = (data[2] << 8) | data[3]
                                raw_in[1] = (data[4] << 8) | data[5]
                                raw_in[2] = (data[6] << 8) | data[7]
                                flypt_data = True
                    except BlockingIOError:
                        pass

                elif s is sock_tx:
                    try:
                        while True:
                            data, _ = s.recvfrom(1024)
                            if len(data) >= 16 and data[0:2] == b"\x55\xaa":
                                func_code = (data[2] << 8) | data[3]

                                if func_code in (0x1102, 0x1202):
                                    reg_addr = (data[8] << 8) | data[9]
                                    reg_val = struct.unpack(">I", data[12:16])[0]
                                    self.gui_queue.put(
                                        {
                                            "type": "PARAM_UPDATE",
                                            "address": reg_addr,
                                            "value": reg_val,
                                        }
                                    )

                                    if debug:
                                        action = (
                                            "READ" if func_code == 0x1102 else "WRITE"
                                        )
                                        self.gui_queue.put(
                                            {
                                                "type": "LOG",
                                                "data": f"[CONTROLLER {action} OK] PA{reg_addr:02X} = {reg_val}",
                                            }
                                        )
                    except BlockingIOError:
                        pass

            # --- 3. Determine Output ---
            if active or manual:
                should_send_motion = True
                silence_countdown = 40
                if not manual and flypt_data:
                    out_m1 = int(raw_in[0] * self.scale_factor)
                    out_m2 = int(raw_in[1] * self.scale_factor)
                    out_m3 = int(raw_in[2] * self.scale_factor)
                    self.gui_queue.put(
                        {
                            "type": "TARGET_UPDATE",
                            "m1": out_m1,
                            "m2": out_m2,
                            "m3": out_m3,
                        }
                    )
            else:
                out_m1 = out_m2 = out_m3 = self.config["safe_pos"]
                if silence_countdown > 0:
                    should_send_motion = True
                    silence_countdown -= 1

            # --- 4. Send Motion Packet ---
            if should_send_motion:
                pkt = IMAXProtocol.pack_motion_data(out_m1, out_m2, out_m3)
                sock_tx.sendto(pkt, (self.config["vega_ip"], self.config["vega_port"]))

            # --- 5. Debug Logging (RE-ADDED) ---
            if debug and (time.time() - last_log_time > 0.5):
                if should_send_motion:
                    if active and not manual:
                        log_msg = f"[AUTO] In: {raw_in} -> Out: [{out_m1}, {out_m2}, {out_m3}]"
                    elif manual:
                        log_msg = f"[MANUAL] Out: [{out_m1}, {out_m2}, {out_m3}]"
                    else:
                        log_msg = f"[PARKING] Out: [{out_m1}, {out_m2}, {out_m3}]"
                else:
                    log_msg = "[SILENT] Network Idle"

                self.gui_queue.put({"type": "LOG", "data": log_msg})
                last_log_time = time.time()

            # --- 6. 20Hz Timing ---
            elapsed = time.time() - loop_start
            if elapsed < 0.050:
                time.sleep(0.050 - elapsed)
