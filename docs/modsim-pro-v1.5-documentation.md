ModSim Pro v1.5 Documentation
Overview
ModSim Pro v1.5 is a Python-based tool designed to simulate Modbus TCP devices, making it ideal for testing, development, and debugging of industrial control systems, SCADA systems, and PLCs. It allows users to define simulated devices via a YAML configuration file, supporting dynamic register updates, writable registers, accumulative registers, and expression-based calculations. The simulator features a live-updating UI built with the rich library, providing real-time visibility into register values and simulation status.
Key Features

Modbus TCP Server: Simulates one or more Modbus TCP devices, each running on a specified IP address, port, and slave ID.
Dynamic Register Updates:
Randomized values for simulating sensor fluctuations.
Accumulative registers for tracking cumulative metrics (e.g., energy usage).
Expression-based calculations using register values and global variables.


Writable Registers: Supports writable registers with configurable value clamping.
Live UI: Displays simulation status and register values in a real-time, color-coded table.
Flexible Configuration: All simulation parameters are defined in a config.yaml file, supporting a wide range of register types and behaviors.
Logging: Detailed logs for debugging, written to simulator.log.

Use Cases

Testing Modbus clients (e.g., SCADA systems, HMIs) by simulating real-world devices.
Simulating PLC behavior with interdependent register logic.
Debugging Modbus communication issues in a controlled environment.
Educational purposes for learning about Modbus protocols and industrial automation.


Installation
Prerequisites

Operating System: Compatible with Windows, macOS, and Linux.
Python Version: Python 3.6 or higher.
Dependencies:
pymodbus>=3.7.0: For Modbus TCP server functionality.
pyyaml>=5.1: For parsing the YAML configuration file.
rich>=10.0: For the live-updating UI.
keyboard>=0.13.5: For handling keyboard inputs (requires root/admin privileges on some systems).



Installation Steps

Install Python:

Ensure Python 3.6+ is installed on your system. Download from python.org if needed.
Verify installation:python --version




Clone or Download ModSim Pro:

Download the simulator source code (sim-exec.py) to a directory of your choice.
Alternatively, if using a version control system like Git:git clone <repository-url>
cd <repository-directory>




Install Dependencies:

Use pip to install the required packages:pip install pymodbus pyyaml rich keyboard


Note: On some systems, you may need to use pip3 instead of pip.


Prepare the Configuration File:

Ensure a config.yaml file exists in the same directory as sim-exec.py.
A sample config.yaml is provided below under Configuration.



Restrictions and Notes

Python Version: ModSim Pro requires Python 3.6 or higher due to the use of f-strings (introduced in 3.6).
Root Privileges for keyboard: On Linux or macOS, the keyboard library may require root privileges to capture keypresses. Run the script with sudo if necessary:sudo python sim-exec.py


Network Access: The simulator binds to network ports (default: 502). Ensure these ports are not blocked by a firewall and are not in use by other applications.
File Permissions: The script writes logs to simulator.log. Ensure the directory has write permissions.


Configuration
ModSim Pro is configured via a config.yaml file, which defines the default settings and the registers to simulate. Below is a detailed explanation of the configuration structure, including all possible fields, their meanings, and restrictions.
Sample config.yaml
Here’s the current config.yaml as of version 1.5:
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
  - address: 1
    name: current_l1
    description: Current L1
    type: uint16
    scale: 100
    base_value: 5.0
    randomize: true
    fluctuation: 0.1
  - address: 2
    name: power_l1
    description: Power L1
    type: uint32
    scale: 1000
    expression: voltage_l1_n * current_l1
  - address: 4
    name: power_l2
    description: Power L2
    type: uint32
    scale: 1000
    expression: voltage_l1_n * current_l1 * 1.25
  - address: 6
    name: total_kwh_l1
    description: Total Energy L1
    type: uint32
    scale: 1000
    accumulate: true
    source: adjusted_power
  - address: 8
    name: total_kwh_l2
    description: Total Energy L2
    type: uint32
    scale: 1000
    accumulate: true
    source: power_l2
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
  - address: 12
    name: adjusted_power
    description: Power adjusted by setpoint percentage
    type: uint32
    scale: 1000
    expression: power_l1 * (sp / 100.0)

Configuration Structure
defaults Section
Defines default settings for new simulations.

ip (string, required):

Default IP address for the Modbus server.
Example: "127.0.0.1"
Restriction: Must be a valid IPv4 address. The simulator does not support IPv6.


port (integer, required):

Default port for the Modbus server.
Example: 502
Restriction: Must be a valid port number (1-65535). Port 502 is the standard Modbus TCP port, but ensure it’s not in use by another application.


slave_id (integer, required):

Default slave ID for the Modbus server.
Example: 1
Restriction: Must be between 1 and 247 (Modbus protocol limit).



registers Section
A list of register definitions. Each register must include the following required fields, with additional optional fields depending on the register’s behavior.
Required Fields for All Registers

address (integer):

The Modbus register address (0-based internally, displayed as 40001-based in the UI).
Example: 0 (corresponds to holding register 40001)
Restriction: Must be a non-negative integer. Addresses must not overlap, considering the register type (e.g., uint32 occupies 2 addresses).


name (string):

Unique name for the register, used for internal referencing and logging.
Example: "voltage_l1_n"
Restriction: Must be unique across all registers. Must be a non-empty string.


description (string):

Human-readable description of the register, displayed in the UI.
Example: "Voltage L1-N"
Restriction: Must be a non-empty string.


type (string):

Data type of the register.
Allowed values: "uint16", "uint32", "int16", "int32", "float32"
Example: "uint16"
Restriction: Must be one of the allowed values. Affects the number of Modbus addresses occupied:
uint16, int16: 1 address
uint32, int32, float32: 2 addresses




scale (number):

Scaling factor to convert between raw Modbus values and scaled values.
Example: 10 (raw value 2300 = scaled value 230.0)
Restriction: Must be a positive number (integer or float). Zero or negative values will cause a configuration error.



Optional Fields (Depending on Behavior)

base_value (number, optional):

Initial value for the register (scaled).
Example: 230.0
Default: 0 if not specified.
Restriction: Must be a number (integer or float). Ignored for registers with an expression.


randomize (boolean, optional):

If true, the register’s value fluctuates randomly around its base_value.
Example: true
Default: false
Restriction: Requires base_value to be specified. Cannot be used with writable, accumulate, or expression.


fluctuation (float, optional):

The percentage (as a decimal) by which a randomized register’s value fluctuates.
Example: 0.05 (5% fluctuation)
Restriction: Required if randomize: true. Must be a positive float between 0 and 1.


accumulate (boolean, optional):

If true, the register accumulates its value over time based on a source register.
Example: true
Default: false
Restriction: Cannot be used with writable or randomize. Requires source.


source (string, optional):

The name of the register to use as the source for accumulation.
Example: "adjusted_power"
Restriction: Required if accumulate: true. The source register must exist in the configuration.


expression (string, optional):

A mathematical expression to compute the register’s value based on other registers or global variables.
Example: "voltage_l1_n * current_l1"
Restriction: Cannot be used with randomize or accumulate. The expression must reference valid register names or global variables (from variable_name).


writable (boolean, optional):

If true, the register can be written to via Modbus (e.g., using function code 06 or 16).
Example: true
Default: false
Restriction: Cannot be used with randomize, accumulate, or expression. Requires variable_name.


variable_name (string, optional):

A unique name for the writable register’s value in the global variables dictionary, allowing it to be referenced in expressions.
Example: "sp"
Restriction: Required if writable: true. Must be a unique, non-empty string across all registers.


min_value (number, optional):

Minimum allowed value for a writable register (scaled).
Example: 0
Restriction: Optional for writable registers. Must be a number. Requires max_value if specified.


max_value (number, optional):

Maximum allowed value for a writable register (scaled).
Example: 100
Restriction: Optional for writable registers. Must be a number. Requires min_value if specified. Must be greater than or equal to min_value.



Configuration Restrictions

Address Overlap:

Registers must not overlap in address space. For example, a uint32 register at address 0 occupies addresses 0-1, so the next register must start at address 2 or higher.
Violation will cause a configuration error: "Duplicate address <address>: <name>".


Unique Names:

The name field must be unique for each register.
Violation will cause a configuration error: "Duplicate address <address>: <name>".


Unique Variable Names:

The variable_name field for writable registers must be unique across all registers.
Violation will cause a configuration error: "Duplicate variable_name '<variable_name>' for <name>".


Expression Dependencies:

Expressions must reference existing register names or global variables (via variable_name).
Circular dependencies (e.g., register A depends on B, and B depends on A) may cause crashes or undefined behavior.


Writable Register Constraints:

Writable registers cannot have randomize, accumulate, or expression properties, as these would conflict with external writes.
Violation will not cause an error but may lead to unexpected behavior (e.g., the simulator prioritizes external writes over internal updates).


File Existence:

The config.yaml file must exist in the same directory as sim-exec.py.
If missing or invalid, ModSim Pro will exit with an error: "Failed to load configuration: <error>".


YAML Syntax:

The config.yaml file must be valid YAML.
Syntax errors will cause ModSim Pro to exit with an error.




Usage
Running ModSim Pro

Start ModSim Pro:

Run the script from the command line:python sim-exec.py


On Linux/macOS, you may need sudo due to the keyboard library:sudo python sim-exec.py




Configure Simulations:

ModSim Pro prompts for the IP address, port, and slave ID for each simulation.
Defaults are loaded from config.yaml, but you can override them:Enter IP address [127.0.0.1]:
Enter port [502]:
Enter slave ID [1]:


After configuring one simulation, you can add more by pressing y when prompted:Add another simulation? (y/N):




Interact with the UI:

Once simulations are configured, the UI displays:
Header: ModSim Pro version and banner.
Configurations Table: List of running simulations (Sim #, IP Address, Port, Slave ID, Status).
Live Registers Table: Register values for the selected simulation (Address, Value, Scaled Value, Description, Writable).
Footer: Instructions for navigation.


Keyboard Controls:
Press 1, 2, ..., N to select a simulation (e.g., 1 to view Sim #1).
Press Left or Right arrow keys to cycle through simulations.
Press a to add a new simulation at runtime.
Press Ctrl+C to stop ModSim Pro.




Interact via Modbus:

Use a Modbus client (e.g., Modbus Poll, mbpoll, or a SCADA system) to connect to the simulated devices.
Example connection:
IP: 127.0.0.1
Port: 502
Slave ID: 1


Read holding registers (function code 03) to view values.
Write to writable registers (function code 06 or 16) to update values (e.g., setpoint at address 40011).



Example Workflow

Start ModSim Pro and configure one simulation using defaults (127.0.0.1:502, Slave ID 1).
The UI shows the "Configurations" table with one simulation and the "Live Registers" table with register values.
Use Modbus Poll to read register 40001 (address 0, voltage_l1_n); it should return a value around 2300 (230.0 V scaled by 10).
Write 50 to register 40011 (address 10, setpoint); the UI updates to show 50.00, and adjusted_power recalculates based on the new setpoint.

Output Files

simulator.log:
Detailed logs of all actions, including register updates and errors.
Example entry:2025-04-14 12:00:00 - DEBUG - Sim-1@127.0.0.1:502 - Writable setpoint updated: 50.0





Restrictions and Notes

Single-Threaded UI Updates:
The UI updates 10 times per second (refresh_per_second=10). This may cause high CPU usage on slower systems.


Keyboard Input:
The keyboard library captures keypresses globally, which may interfere with other applications.
On Linux/macOS, root privileges are required for keypress detection.


Port Conflicts:
If the specified port (e.g., 502) is in use, ModSim Pro will fail to start the server and prompt you to try a different port.


Simulation Limit:
There’s no hard limit on the number of simulations, but each simulation runs a Modbus server thread, which increases resource usage (CPU, memory, network sockets).
Practical Limit: Around 50-100 simulations, depending on system resources.


Writable Register Updates:
Writable registers are updated every UPDATE_INTERVAL_SECONDS (0.3 seconds). Rapid writes from a Modbus client may not be reflected immediately in the UI due to this interval.


Memory Usage:
Large numbers of simulations or registers may increase memory usage significantly.




Restrictions and Limitations
Configuration Restrictions

Address Overlap:
uint16 and int16 registers occupy 1 address; uint32, int32, and float32 occupy 2 addresses.
Overlapping addresses will cause a configuration error.
Example: A uint32 register at address 0 uses addresses 0-1. Another register at address 1 will cause an error.


Register Type Limits:
uint16: 0 to 65,535
uint32: 0 to 4,294,967,295
int16: -32,768 to 32,767
int32: -2,147,483,648 to 2,147,483,647
float32: Standard 32-bit float range (approximately ±3.4e38)
Values outside these ranges will be truncated or cause undefined behavior.


Expression Limitations:
Expressions are evaluated using Python’s eval(), which supports basic arithmetic (+, -, *, /) and variable references, as well as math module functions (e.g., math.sin), max, and min.
Complex expressions (e.g., conditionals, loops, or function calls) are not supported.
Example: "voltage_l1_n * current_l1 * 1.25" is valid, but "if voltage_l1_n > 200: 1 else: 0" is not.


Circular Dependencies:
Expressions that create circular dependencies (e.g., register A depends on B, and B depends on A) may cause crashes or undefined behavior.


Scale Factor:
The scale factor must be positive. Zero or negative values will cause a configuration error.


Randomized Registers:
Randomized registers (randomize: true) cannot be writable, accumulative, or expression-based.
Fluctuation must be between 0 and 1 (e.g., 0.05 for 5% fluctuation).



Runtime Restrictions

Update Interval:
ModSim Pro updates register values every UPDATE_INTERVAL_SECONDS (0.3 seconds). This limits the responsiveness of the UI and register updates.
Rapid changes (e.g., writing to a register faster than ~3 times per second) may not be fully captured.


Thread Safety:
ModSim Pro uses locks to ensure thread safety, but concurrent writes to the same register from multiple Modbus clients may lead to race conditions.
Recommendation: Use a single Modbus client per simulation to avoid conflicts.


Network Limitations:
ModSim Pro does not support IPv6 addresses.
Only one simulation can bind to a given IP:port combination. Attempting to start multiple simulations on the same port will fail.


Memory Usage:
Each simulation instance stores register values in memory.
With many simulations or registers, memory usage can grow significantly.
Practical Limit: Monitor simulator.log for memory usage. If memory exceeds available system resources, reduce the number of simulations.


CPU Usage:
The live UI updates 10 times per second, which may cause high CPU usage on slower systems.
Each simulation runs a Modbus server thread, increasing CPU usage as more simulations are added.


Logging Overhead:
ModSim Pro logs extensively to simulator.log, which can grow large over time.
Recommendation: Periodically archive or truncate log files to manage disk space.



UI Restrictions

Terminal Width:
The UI adjusts column widths dynamically, but very narrow terminal windows may cause text wrapping or truncation.
Recommendation: Use a terminal window with at least 80 columns for best readability.


Keyboard Conflicts:
The keyboard library captures keypresses globally, which may interfere with other applications running on the same system.
Workaround: Run ModSim Pro in a dedicated terminal or virtual machine.


Simulation Selection:
Keyboard shortcuts (1, 2, ..., N) are limited to single-digit numbers in the current implementation.
Restriction: Simulations numbered 10 and above cannot be selected directly using a single keypress. Use arrow keys to cycle instead.



Modbus Protocol Restrictions

Supported Function Codes:
ModSim Pro supports reading holding registers (function code 03) and writing single/multiple registers (function codes 06 and 16).
Other function codes (e.g., coils, discrete inputs) are not supported.


Slave ID Range:
Slave IDs must be between 1 and 247, per the Modbus protocol.


Register Access:
Only holding registers (addresses 40001 and above) are supported.
Input registers, coils, and discrete inputs are not supported.


Maximum Address:
ModSim Pro calculates the maximum address based on the highest address in config.yaml plus the register size (e.g., 2 for uint32).
Attempting to read beyond this address via Modbus will return an error or zeros.



File System Restrictions

Log Files:
ModSim Pro writes to simulator.log in the current directory.
If the directory is not writable, ModSim Pro will fail with an error.


Configuration File:
The config.yaml file must be in the same directory as sim-exec.py.
ModSim Pro does not support specifying a different path for the configuration file.




Troubleshooting
Common Issues and Solutions

"Failed to load configuration: ":

Cause: The config.yaml file is missing, has invalid YAML syntax, or contains invalid fields.
Solution:
Ensure config.yaml exists in the same directory as sim-exec.py.
Validate the YAML syntax using an online YAML validator.
Check for missing required fields or invalid values (e.g., negative scale).




"Failed to create simulation: ":

Cause: The specified port (e.g., 502) is already in use by another application.
Solution:
Choose a different port when prompted.
Use netstat to identify and free the port:netstat -tuln | grep 502


On Linux, kill the process using the port:sudo kill -9 <pid>






Keyboard Inputs Not Working on Linux/macOS:

Cause: The keyboard library requires root privileges on some systems.
Solution:
Run the script with sudo:sudo python sim-exec.py


Alternatively, disable the keyboard library and modify the script to use a different input method (e.g., console input).




High CPU Usage:

Cause: Too many simulations, frequent UI updates, or large numbers of registers.
Solution:
Reduce the number of simulations.
Increase UPDATE_INTERVAL_SECONDS (default: 0.3) to reduce update frequency (requires code modification).





