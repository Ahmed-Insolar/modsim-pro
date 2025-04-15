ModSim Pro
ModSim Pro is a Python-based Modbus TCP simulator designed for testing, development, and debugging of industrial control systems, SCADA systems, and PLCs. It supports dynamic register updates, writable registers, accumulative registers, and expression-based calculations, with a live-updating UI for real-time monitoring.
Features

Modbus TCP Server: Simulate multiple Modbus TCP devices with configurable IP, port, and slave ID.
Dynamic Registers:
Randomized values for simulating sensor fluctuations.
Accumulative registers for tracking cumulative metrics (e.g., energy usage).
Expression-based calculations (e.g., voltage * current * 1.25).


Writable Registers: Supports external writes with configurable value clamping.
Live UI: Real-time display of simulation status and register values using the rich library.
Flexible Configuration: Define simulations using a config.yaml file.

Installation
Prerequisites

Python: Version 3.6 or higher.
Operating System: Compatible with Windows, macOS, and Linux.

Steps

Clone the Repository:
git clone https://github.com/your-username/modsim-pro.git
cd modsim-pro


Install Dependencies:
pip install -r requirements.txt

Dependencies include:

pymodbus>=3.7.0
pyyaml>=5.1
rich>=10.0
keyboard>=0.13.5

Note: On Linux/macOS, the keyboard library may require root privileges. Run with sudo if needed:
sudo pip install -r requirements.txt


Prepare the Configuration File:

A sample config.yaml is provided in the root directory. Customize it as needed (see Configuration).



Usage

Run ModSim Pro:
python src/sim-exec.py

On Linux/macOS, you may need sudo due to the keyboard library:
sudo python src/sim-exec.py


Configure Simulations:

The simulator will prompt for the IP address, port, and slave ID for each simulation.

Defaults are loaded from config.yaml, but you can override them:
Enter IP address [127.0.0.1]:
Enter port [502]:
Enter slave ID [1]:


Add more simulations by pressing y when prompted:
Add another simulation? (y/N):




Interact with the UI:

The UI displays running simulations and register values.
Keyboard Controls:
Press 1, 2, ..., N to select a simulation.
Press Left or Right arrow keys to cycle through simulations.
Press a to add a new simulation.
Press Ctrl+C to stop.




Connect via Modbus Client:

Use a Modbus client (e.g., Modbus Poll) to connect to the simulated devices.
Example connection: IP 127.0.0.1, Port 502, Slave ID 1.
Read/write registers (e.g., read 40001 for voltage_l1_n, write 40011 to update setpoint).



Configuration
ModSim Pro uses a config.yaml file to define simulation parameters. A sample configuration is provided:
defaults:
  ip: "127.0.0.1"
  port: 502
  slave_id: 1

registers:
  - address: 0
    name: voltage_l1_n
    description: Voltage L1-N
    type: uint16
    scale: 10
    base_value: 230.0
    randomize: true
    fluctuation: 0.05
  - address: 10
    name: setpoint
    description: Setpoint Percentage (0-100)
    type: uint16
    scale: 1
    base_value: 25
    writable: true
    variable_name: sp
    min_value: 0
    max_value: 100

For detailed configuration options, see the full documentation.
Documentation

User Manual: modsim-pro-v1.5-documentation.md
Datasheet: modsim-pro-v1.5-datasheet.md

License
This project is licensed under the MIT License - see the LICENSE file for details.
Contributing
Contributions are welcome! Please submit a pull request or open an issue on GitHub.
Contact
For questions or support, please open an issue on GitHub or contact ahmad.a.alghannam@gmail.com.
Last updated: April 14, 2025
