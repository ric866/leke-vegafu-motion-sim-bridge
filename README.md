**ESPHome Vega/IMAX Motion Bridge**

This project implements a UDP bridge using an ESP32 and ESPHome to interface between motion simulation software (SimTools, FlyPT Mover, SimMotion) and Vegafu/IMAX-style motion controllers (in my case an SMC_X24). 
It has two modes of operation:
- Pass-Through Mode: Forwarding of simulator packets to the motion controller.
- Manual Override Mode: Direct control of motor positions via sliders, useful for testing movement without a running simulator **Caution - Movement is instant to the position of the slider, be gentle**.
  
Features
- Dynamic UDP Bridging: Receives motion data on a fixed port and forwards it to a configurable target IP/Port.
- Protocol Translation: Decodes raw 16-bit motor data (0-65535) and scales it to the controller's required format (0-100,000).
- Session Stability: Binds to a fixed Source Port (8410) to maintain a stable UDP session, the chinese standard PC->Sim traffic to prevent controller timeouts.
- Packet Engineering: Generates 50-byte packets (see below) with correct confirmCode, objectChannel, replyCode, absTime counters, and padding required by the controller.
- Other Stuff / Systems:
  - Automatically cuts the air relays and holds the rig position if data stream is lost for >2 seconds.
  - Throttles manual mode packets (10Hz) to prevent network flooding.
  - Boots with "Booth Lights ON" until valid data is received.
  - GPIO Control: Maps incoming telemetry bits to 8 physical relays for effects (in my case Wind, Vibration, Back Pressure, Ticklers).

Hardware
- Microcontroller: ESP32 Powered Board (I got one with 8 relays)
- Relays: 8-Channel Relay Module (Active Low/High depending on wiring)
- Motion Controller: Vega / IMAX / 3-DOF or 6-DOF (you'll need to fiddle with the code) Motion Driver requiring 50-byte UDP packets.

Protocol Details

The core challenge of this project was reverse-engineering the specific packet structure required by the controller. The ESP32 generates packets matching this 50-byte structure:
struct ImaxPacket {

  uint16_t confirmCode;   // 0x55AA
  
  uint16_t passCode;      // 0x0000
  
  uint16_t functionCode;  // 0x1301
  
  uint16_t objectChannel; // 0x0001 (Critical for acceptance)
  
  uint16_t acceptCode;    // 0xFFFF
  
  uint16_t replyCode;     // 0xFFFF
  
  uint32_t absTime;       // millis()
  
  uint32_t portOut;       // millis() & 0xFFFF (Running Counter)
  
  int32_t axis1;          // Motor 1 Position (0-100000)
  
  int32_t axis2;          // Motor 2 Position (0-100000)
  
  int32_t axis3;          // Motor 3 Position (0-100000)
  
  int32_t axis4;          // Unused
  
  int32_t axis5;          // Unused
  
  int32_t axis6;          // Unused
  
  uint16_t padding;       // 0x0000 (Critical 2-byte alignment)
  
  uint32_t footer;        // 0x5678ABCD
  
};

Usage 

The ESP32 exposes the following entities on it's little web portal:
- Relay Control Switches (which do what you'd think).
- Target IP / Port: Set the IP of your Motion Controller (e.g., 192.168.15.201).
- Manual Override Mode (Switch): Toggle ON to ignore simulator data and use sliders.
- Motor 1/2/3 Position (Sliders): Manually move the rig (0-100%) when in Manual Mode.
- Debug Logging (Switch): Enable verbose logs to see incoming/outgoing packet data.

Simulator Setup (SimTools / FlyPT)
- Interface Type: Network / UDP
- IP Address: [ESP32_IP_ADDRESS]
- Port: 8410 (Matches the ESP32's listening and source binding port)
- Output Format: Binary/Raw Integers (16-bit big-endian)
Troubleshooting
- Rig not moving in Manual Mode?
  - Enable "Enable Debug Logging" and check the logs in the web page. You should see messages like:[manual] Sent to 192.168.15.201:7408 | M1:50000 M2:0 M3:0
  - Ensure "Target Controller IP" is correct.
- Rig moves in Manual but not Sim?
  - Check the "Pass-Through" logs:[bridge] In: 32768 32768 0 -> Out: 50000 50000 0
  - If In is always 0, your Simulator is not sending data to the ESP32's IP.
  - Ensure the Simulator Output Port matches the udp.begin(8410) port in the YAML.
  
License
- This project is open-source. Feel free to modify and use it for your own motion rig projects.
