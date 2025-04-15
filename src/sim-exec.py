"""
ModSim Pro (Version 1.5.0)

This script simulates a Modbus TCP server with dynamic and writable register values,
configurable via a YAML file. It provides a live UI to monitor simulations and supports
dynamic updates for randomized values, accumulator registers, derived values (via expressions),
and writable registers with global variable interactions.

Dependencies:
- pymodbus
- pyyaml
- rich
- keyboard

Usage:
1. Ensure `config.yaml` is in the same directory as this script.
2. Run the script: `python sim-exec.py`
3. Follow the prompts to configure simulations.
4. Use Modbus Poll or another client to connect to the simulated server(s).
5. Press Ctrl+C to stop ModSim Pro.

New Features in Version 1.5.0:
- Writable registers with configurable permissions and value storage in global variables.
- Enhanced YAML configuration for register settings (e.g., writable, variable_name).
- Modular register handling with support for expressions referencing global variables.
- Robust validation and error handling for register configurations.
"""

import threading
import time
import random
import math
import logging
import traceback
import yaml
import re
from typing import Dict, Any, List
from pymodbus.server import ModbusTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadBuilder
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.console import Console
from rich.layout import Layout
from rich.padding import Padding
from rich.text import Text
from rich.style import Style

try:
    import keyboard
except ImportError:
    print("Please install the 'keyboard' library: pip install keyboard")
    exit(1)

# --- Constants ---
VERSION = "1.5.0"
UPDATE_INTERVAL_SECONDS = 0.3  # Update interval for dynamic values
LOG_FILENAME = 'simulator.log'

# --- Configure File Logging ---
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)-8s - %(name)-12s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filename=LOG_FILENAME,
    filemode='w'
)
log = logging.getLogger()

# --- Global Variables ---
simulations = []  # List of running simulation instances
lock = threading.Lock()  # Thread lock for shared resources
console = Console()  # Rich console for UI
selected_simulation_index = 0  # Index of the currently selected simulation in the UI
config = None  # Loaded configuration from YAML
register_map = {}  # Maps register addresses to info
register_names = {}  # Maps register names to addresses
global_variables = {}  # Stores values of writable registers by variable_name

# --- Load Configuration from YAML ---
def load_config(file_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Load the configuration from a YAML file and build register mappings.

    Args:
        file_path (str): Path to the YAML configuration file.

    Returns:
        Dict[str, Any]: Loaded configuration data.

    Raises:
        Exception: If the file cannot be loaded or is invalid.
    """
    try:
        with open(file_path, 'r') as f:
            config_data = yaml.safe_load(f)
        if not config_data:
            raise ValueError("Config file is empty")
        log.debug(f"Loaded config data: {config_data}")

        # Validate required fields in defaults
        defaults = config_data.get("defaults", {})
        required_defaults = ["ip", "port", "slave_id"]
        for field in required_defaults:
            if field not in defaults:
                raise ValueError(f"Missing required field '{field}' in defaults section of config.yaml")

        # Build register map and name-to-address mapping
        global register_map, register_names
        register_map = {}
        register_names = {}
        for reg in config_data.get("registers", []):
            # Validate required fields
            required_fields = ["address", "name", "description", "type", "scale"]
            for field in required_fields:
                if field not in reg:
                    raise ValueError(f"Register missing required field '{field}': {reg}")
            
            # Validate type
            valid_types = ["uint16", "uint32", "int16", "int32", "float32"]
            if reg["type"] not in valid_types:
                raise ValueError(f"Invalid register type '{reg['type']}' for {reg['name']}. Must be one of {valid_types}.")
            
            # Validate scale
            if not isinstance(reg["scale"], (int, float)) or reg["scale"] <= 0:
                raise ValueError(f"Invalid scale '{reg['scale']}' for {reg['name']}. Must be a positive number.")
            
            # Validate base_value if present
            if "base_value" in reg and not isinstance(reg["base_value"], (int, float)):
                raise ValueError(f"Invalid base_value '{reg['base_value']}' for {reg['name']}. Must be a number.")
            
            # Validate writable and variable_name
            if reg.get("writable", False):
                if "variable_name" not in reg:
                    raise ValueError(f"Writable register '{reg['name']}' must specify a 'variable_name'.")
                if not isinstance(reg["variable_name"], str) or not reg["variable_name"]:
                    raise ValueError(f"Invalid variable_name for {reg['name']}. Must be a non-empty string.")
                if reg["variable_name"] in global_variables:
                    raise ValueError(f"Duplicate variable_name '{reg['variable_name']}' for {reg['name']}.")
                global_variables[reg["variable_name"]] = reg.get("base_value", 0)

            # Validate min_value and max_value for writable registers
            if reg.get("writable", False):
                if "min_value" in reg and not isinstance(reg["min_value"], (int, float)):
                    raise ValueError(f"Invalid min_value '{reg['min_value']}' for {reg['name']}. Must be a number.")
                if "max_value" in reg and not isinstance(reg["max_value"], (int, float)):
                    raise ValueError(f"Invalid max_value '{reg['max_value']}' for {reg['name']}. Must be a number.")
                if "min_value" in reg and "max_value" in reg:
                    if reg["min_value"] > reg["max_value"]:
                        raise ValueError(f"min_value ({reg['min_value']}) must be less than or equal to max_value ({reg['max_value']}) for {reg['name']}.")

            address = reg["address"]
            if address in register_map:
                raise ValueError(f"Duplicate address {address}: {reg['name']}")
            
            register_map[address] = reg
            register_names[reg["name"]] = address

        log.info(f"Loaded registers: {list(register_map.keys())}")
        if not register_map:
            raise ValueError("No registers defined in config")
        return config_data
    except Exception as e:
        log.error(f"Failed to load config: {e}")
        raise

# --- Expression Evaluator ---
def evaluate_expression(expression: str, values: Dict[str, float], global_vars: Dict[str, float]) -> float:
    """
    Evaluate a mathematical expression using register values and global variables.

    Args:
        expression (str): The expression to evaluate (e.g., "voltage_l1_n * current_l1 + setpoint").
        values (Dict[str, float]): Current values of registers.
        global_vars (Dict[str, float]): Global variables from writable registers.

    Returns:
        float: The evaluated result.
    """
    try:
        # Combine register values and global variables
        combined_values = {**values, **global_vars}
        used_values = {k: v for k, v in combined_values.items() if k in expression}
        log.debug(f"Values for expression '{expression}': {used_values}")
        
        # Replace names with their values using word boundaries
        substituted_expression = expression
        for name in combined_values.keys():
            pattern = r'\b' + re.escape(name) + r'\b'
            value = combined_values.get(name, 0)
            substituted_expression = re.sub(pattern, str(value), substituted_expression)
        log.debug(f"Substituted expression: {substituted_expression}")
        
        # Evaluate the expression
        result = eval(substituted_expression, {"__builtins__": None, "math": math, "max": max, "min": min}, {})
        log.debug(f"Evaluated result: {result}")
        return result
    except Exception as e:
        log.error(f"Error evaluating expression '{expression}': {e}")
        return 0

# --- Helper Functions ---
def encode_value(value: float, reg_type: str, scale: float) -> List[int]:
    """
    Encode a scaled value into register words based on type.

    Args:
        value (float): The scaled value.
        reg_type (str): Register type (uint16, uint32, int16, int32, float32).
        scale (float): Scaling factor.

    Returns:
        List[int]: Register words.
    """
    raw_value = value * scale
    if reg_type == "uint16":
        capped = max(0, min(int(raw_value), 65535))
        return [capped]
    elif reg_type == "uint32":
        capped = max(0, min(int(raw_value), 0xFFFFFFFF))
        high, low = (capped >> 16) & 0xFFFF, capped & 0xFFFF
        return [high, low]
    elif reg_type == "int16":
        capped = max(-32768, min(int(raw_value), 32767))
        return [capped & 0xFFFF]
    elif reg_type == "int32":
        capped = max(-0x80000000, min(int(raw_value), 0x7FFFFFFF))
        high, low = (capped >> 16) & 0xFFFF, capped & 0xFFFF
        return [high, low]
    elif reg_type == "float32":
        builder = BinaryPayloadBuilder(byteorder=Endian.BIG, wordorder=Endian.BIG)
        builder.add_32bit_float(raw_value)
        words = builder.to_registers()
        return words
    return [0]

def decode_value(words: List[int], reg_type: str, scale: float) -> float:
    """
    Decode register words into a scaled value.

    Args:
        words (List[int]): Register words.
        reg_type (str): Register type.
        scale (float): Scaling factor.

    Returns:
        float: Decoded and scaled value.
    """
    from pymodbus.payload import BinaryPayloadDecoder
    if reg_type == "uint16":
        return words[0] / scale if words else 0
    elif reg_type == "uint32":
        if len(words) >= 2:
            return ((words[0] << 16) + words[1]) / scale
        return 0
    elif reg_type == "int16":
        value = words[0] if words else 0
        return (value if value < 32768 else value - 65536) / scale
    elif reg_type == "int32":
        if len(words) >= 2:
            value = (words[0] << 16) + words[1]
            return (value if value < 0x80000000 else value - 0x100000000) / scale
        return 0
    elif reg_type == "float32":
        if len(words) >= 2:
            decoder = BinaryPayloadDecoder.fromRegisters(words, byteorder=Endian.BIG, wordorder=Endian.BIG)
            return decoder.decode_32bit_float() / scale
        return 0
    return 0

def get_register_info(address: int) -> Dict[str, Any]:
    """
    Retrieve register information for a given address.

    Args:
        address (int): Register address.

    Returns:
        Dict[str, Any]: Register information.
    """
    reg_info = register_map.get(address, {"scale": 1, "description": "Unknown", "type": "uint16"})
    log.debug(f"Retrieved register info for address {address}: {reg_info}")
    return reg_info

# --- Simulation Instance Class ---
class SimulationInstance:
    def __init__(self, ip: str, port: int, slave_id: int):
        """
        Initialize a Modbus TCP simulation instance.

        Args:
            ip (str): IP address to bind the server to.
            port (int): TCP port to listen on.
            slave_id (int): Modbus slave ID.
        """
        self.log = logging.getLogger(f"Sim-{slave_id}@{ip}:{port}")
        self.ip = ip
        self.port = port
        self.slave_id = slave_id
        self.running = False
        self.thread_server = None
        self.thread_update = None
        self.lock = threading.Lock()
        self.values = {}  # Store scaled values (display values)
        self.max_address = max(register_map.keys(), default=-1) + 2  # +2 for 32-bit registers
        self.block = ModbusSequentialDataBlock(0, [0] * max(10, self.max_address))
        self.context = ModbusSlaveContext(
            hr=self.block,
            ir=self.block,
            di=ModbusSequentialDataBlock(0, [0]*10),
            co=ModbusSequentialDataBlock(0, [0]*10),
            zero_mode=True
        )
        self.server_context = ModbusServerContext(slaves={self.slave_id: self.context}, single=False)
        self.modbus_server = None

        # Initialize values for all registers and set initial values in the data block
        for address, reg in register_map.items():
            self.values[reg["name"]] = float(reg.get("base_value", 0))
            if reg.get("writable", False):
                global_variables[reg["variable_name"]] = self.values[reg["name"]]
            # Write initial value to the Modbus data block
            initial_value = self.values[reg["name"]]
            words = encode_value(initial_value, reg["type"], reg["scale"])
            self.block.setValues(address, words)
            self.log.debug(f"Initialized address {address} ({reg['name']}): raw={words}, scaled={initial_value}")
        
        self.log.info("Instance initialized.")

    def _update_values(self):
        with self.lock:
            # Step 1: Update randomized values
            for address, reg in register_map.items():
                if reg.get("randomize", False) and not reg.get("writable", False):
                    base_value = reg["base_value"]
                    fluctuation = reg["fluctuation"]
                    new_value = base_value * (1 + random.uniform(-fluctuation, fluctuation))
                    self.values[reg["name"]] = new_value
                    self.log.debug(f"Randomized {reg['name']}: {new_value}")

            # Step 2: Update accumulator registers
            for address, reg in register_map.items():
                if reg.get("accumulate", False) and not reg.get("writable", False):
                    source_name = reg["source"]
                    source_value = self.values.get(source_name, 0)
                    increment = source_value * UPDATE_INTERVAL_SECONDS / 3600 / 1000
                    current_value = self.values.get(reg["name"], 0)
                    self.values[reg["name"]] = current_value + increment
                    self.log.debug(f"Accumulated {reg['name']}: {self.values[reg['name']]} (increment: {increment})")

            # Step 3: Check writable registers for updates from Modbus
            for address, reg in register_map.items():
                if reg.get("writable", False):
                    words = self.context.getValues(3, address, count=2 if reg["type"] in ["uint32", "int32", "float32"] else 1)
                    new_value = decode_value(words, reg["type"], reg["scale"])
                    # Apply clamping if min_value and max_value are specified
                    if "min_value" in reg and "max_value" in reg:
                        if reg["type"] in ["uint16", "uint32"]:
                            new_value = max(reg["min_value"], min(reg["max_value"], int(new_value)))
                        else:
                            new_value = max(reg["min_value"], min(reg["max_value"], new_value))
                    if new_value != self.values[reg["name"]]:
                        self.values[reg["name"]] = new_value
                        global_variables[reg["variable_name"]] = new_value
                        self.log.debug(f"Writable {reg['name']} updated: {new_value}")

            # Step 4: Update derived values (expressions)
            for address, reg in register_map.items():
                if "expression" in reg:
                    value = evaluate_expression(reg["expression"], self.values, global_variables)
                    self.values[reg["name"]] = value
                    self.log.debug(f"Evaluated {reg['name']}: {value} (expression: {reg['expression']})")

            # Step 5: Write to Modbus registers
            for address, reg in register_map.items():
                if not reg.get("writable", False):  # Don't overwrite writable registers
                    name = reg["name"]
                    value = self.values.get(name, 0)
                    words = encode_value(value, reg["type"], reg["scale"])
                    self.block.setValues(address, words)
                    self.log.debug(f"Wrote to address {address} ({name}): words={words}, scaled={value}")

    def _update_loop(self):
        """
        Continuously update register values while the simulation is running.
        """
        self.log.info("Update loop started.")
        while self.running:
            try:
                self._update_values()
                time.sleep(UPDATE_INTERVAL_SECONDS)
            except Exception as e:
                self.log.exception("CRITICAL ERROR in update loop:")
                time.sleep(UPDATE_INTERVAL_SECONDS * 5)
        self.log.info("Update loop stopped.")

    def _run_server(self):
        """
        Run the Modbus TCP server in a separate thread.
        """
        import asyncio
        server_id = f"Sim-{self.slave_id}@{self.ip}:{self.port}"
        address = (self.ip, self.port)

        async def serve():
            try:
                self.log.info(f"{server_id} - Starting Modbus TCP server...")
                self.modbus_server = ModbusTcpServer(context=self.server_context, address=address)
                self.log.info(f"{server_id} - Modbus TCP server started and serving.")
                await self.modbus_server.serve_forever()
            except Exception as e:
                self.log.exception(f"{server_id} - CRITICAL ERROR in Modbus TCP server:")
            finally:
                self.log.info(f"{server_id} - Modbus TCP server stopped.")
                self.running = False

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(serve())
        except Exception as e:
            self.log.error(f"{server_id} - Error running asyncio event loop: {e}")
        finally:
            loop.close()

    def start(self):
        """
        Start the simulation (update loop and Modbus server).
        """
        if not self.running:
            self.running = True
            self.log.info("Starting simulation threads...")
            self.thread_update = threading.Thread(target=self._update_loop, name=f"Update-{self.slave_id}", daemon=True)
            self.thread_update.start()
            self.thread_server = threading.Thread(target=self._run_server, name=f"Server-{self.slave_id}", daemon=True)
            self.thread_server.start()
            time.sleep(0.1)
            if not self.thread_update.is_alive() or not self.thread_server.is_alive():
                self.log.error("Failed to start simulation threads")
                self.running = False
                raise RuntimeError("Simulation threads failed to start")

    def stop(self):
        """
        Stop the simulation and clean up resources.
        """
        if self.running:
            self.log.info("Stopping simulation threads...")
            self.running = False
            if self.modbus_server:
                try:
                    self.modbus_server.shutdown()
                except AttributeError:
                    self.modbus_server.close()
            if self.thread_update and self.thread_update.is_alive():
                self.thread_update.join(timeout=5)
            if self.thread_server and self.thread_server.is_alive():
                self.thread_server.join(timeout=5)
            self.log.info("Simulation threads stopped.")

    def get_register_value(self, address: int, count: int = 1) -> List[int]:
        """
        Retrieve register values from the data block.

        Args:
            address (int): Starting address.
            count (int): Number of registers to read.

        Returns:
            List[int]: Register values.
        """
        with self.lock:
            value_list = self.context.getValues(3, address, count=count)
        self.log.debug(f"Retrieved values from address {address}: {value_list}")
        return value_list

    def is_alive(self) -> bool:
        """
        Check if the simulation is running.

        Returns:
            bool: True if the server thread is alive.
        """
        alive = self.thread_server and self.thread_server.is_alive()
        self.log.debug(f"Simulation alive: {alive}")
        return alive

# --- Display Functions ---
def generate_layout() -> Layout:
    """
    Create the UI layout using Rich.

    Returns:
        Layout: The configured layout.
    """
    layout = Layout(name="root")
    layout.split(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=3)
    )
    layout["main"].split_row(
        Layout(name="config", ratio=3),
        Layout(name="registers", ratio=5)
    )
    return layout

def make_config_table(sims: list) -> Table:
    """
    Create a table displaying the status of all running simulations.

    Args:
        sims (list): List of SimulationInstance objects.

    Returns:
        Table: Rich table with simulation details.
    """
    table = Table(title="Running Modbus Simulations", style="green", expand=True, highlight=True)
    table.add_column("Sim #", style="dim", width=1)
    table.add_column("IP Address", justify="center")
    table.add_column("Port", justify="center")
    table.add_column("Slave ID", justify="center",width=2)
    table.add_column("Status", justify="right")
    log.debug(f"Building config table with {len(sims)} simulations")
    if not sims:
        table.add_row("[red]No simulations running[/red]")
        return table
    for idx, sim in enumerate(sims):
        status = "[green]Running[/green]" if sim.is_alive() else "[red]Stopped[/red]"
        table.add_row(str(idx + 1), sim.ip, str(sim.port), str(sim.slave_id), status)
        log.debug(f"Added simulation {idx + 1}: {sim.ip}:{sim.port}, Slave ID {sim.slave_id}, Status {status}")
    return table

def make_register_table(sim_instance, sim_index: int) -> Table:
    """
    Create a table displaying the current register values for a simulation.

    Args:
        sim_instance: The SimulationInstance to display.
        sim_index (int): Index of the simulation (for display purposes).

    Returns:
        Table: Rich table with register values.
    """
    if not sim_instance:
        table = Table(title="Simulated Registers", style="green", expand=True)
        table.add_row("[dim]No simulation running[/dim]")
        log.debug("No simulation instance provided for register table")
        return table

    # Initialize the table with expand=True to use available space
    table = Table(title=f"Registers (Sim #{sim_index + 1} @ {sim_instance.ip}:{sim_instance.port})", style="green", expand=True, highlight=True)

    # Define columns without fixed widths initially
    table.add_column("Address", style="dim", justify="center")
    table.add_column("Value", justify="center")
    table.add_column("Scaled Value", justify="center")
    table.add_column("Description", justify="center")
    table.add_column("Writable", justify="center")

    log.debug(f"Building register table for Sim #{sim_index + 1}")
    sorted_addresses = sorted(register_map.keys())
    current_reg_values = {}
    with sim_instance.lock:
        try:
            value_list = sim_instance.context.getValues(3, 0, count=sim_instance.max_address)
            if value_list:
                for i, addr in enumerate(range(sim_instance.max_address)):
                    if addr in register_map:
                        reg_info = get_register_info(addr)
                        num_registers = 2 if reg_info["type"] in ["uint32", "int32", "float32"] else 1
                        if i + num_registers <= len(value_list):
                            current_reg_values[addr] = value_list[i:i + num_registers]
                        else:
                            sim_instance.log.warning(f"Could not retrieve values for address {addr}: insufficient data")
            else:
                sim_instance.log.warning(f"No values retrieved for registers")
        except Exception as e:
            sim_instance.log.error(f"Error retrieving register values: {e}")

    # Collect data and calculate maximum lengths for each column
    rows = []
    max_address_len = len("Address")
    max_value_len = len("Value")
    max_scaled_len = len("Scaled Value")
    max_description_len = len("Description")
    max_writable_len = len("Writable")

    for address in sorted_addresses:
        reg_info = get_register_info(address)
        raw_values = current_reg_values.get(address, [0])
        scaled_value = decode_value(raw_values, reg_info["type"], reg_info["scale"])
        scaled_str = f"{scaled_value:.3f}" if reg_info["scale"] >= 100 else f"{scaled_value:.2f}"
        writable = "Yes" if reg_info.get("writable", False) else "No"

        # Format the raw value based on register type
        if reg_info["type"] == "uint16":
            raw_value = str(raw_values[0]) if raw_values else "N/A"
        elif reg_info["type"] == "int16":
            value = raw_values[0] if raw_values else 0
            raw_value = str(value if value < 32768 else value - 65536)
        elif reg_info["type"] == "uint32":
            if len(raw_values) >= 2:
                raw_value = str((raw_values[0] << 16) + raw_values[1])
            else:
                raw_value = "N/A"
        elif reg_info["type"] == "int32":
            if len(raw_values) >= 2:
                value = (raw_values[0] << 16) + raw_values[1]
                raw_value = str(value if value < 0x80000000 else value - 0x100000000)
            else:
                raw_value = "N/A"
        elif reg_info["type"] == "float32":
            if len(raw_values) >= 2:
                from pymodbus.payload import BinaryPayloadDecoder
                decoder = BinaryPayloadDecoder.fromRegisters(raw_values, byteorder=Endian.BIG, wordorder=Endian.BIG)
                raw_value = f"{decoder.decode_32bit_float():.2f}"
            else:
                raw_value = "N/A"
        else:
            raw_value = str(raw_values) if raw_values else "N/A"

        address_str = str(40001 + address)
        rows.append((address_str, raw_value, scaled_str, reg_info["description"], writable))

        # Update maximum lengths
        max_address_len = max(max_address_len, len(address_str))
        max_value_len = max(max_value_len, len(raw_value))
        max_scaled_len = max(max_scaled_len, len(scaled_str))
        max_description_len = max(max_description_len, len(reg_info["description"]))
        max_writable_len = max(max_writable_len, len(writable))

    # Adjust column widths with some padding (add 2 for spacing)
    table.columns[0].width = max_address_len + 2
    table.columns[1].width = max_value_len + 2
    table.columns[2].width = max_scaled_len + 2
    table.columns[3].width = max_description_len + 2  # Description gets more space
    table.columns[4].width = max_writable_len + 2

    # Add rows to the table
    for address_str, raw_value, scaled_str, description, writable in rows:
        table.add_row(address_str, raw_value, scaled_str, description, writable)
        log.debug(f"Added register at address {address_str}: raw={raw_value}, scaled={scaled_str}, description={description}, writable={writable}")

    return table

def update_display(live: Live, sims: list, selected_index: int = 0):
    """
    Update the live UI display with the current simulation status and register values.

    Args:
        live (Live): Rich Live display object.
        sims (list): List of SimulationInstance objects.
        selected_index (int): Index of the currently selected simulation.
    """
    layout = generate_layout()
    layout["header"].update(Panel(f"ModSim Pro (v{VERSION})", style="bold blue"))
    log.debug("Updating config panel")
    
    if not sims:
        config_panel = Panel("[red]No simulations running. Check logs for errors.[/red]", title="[b]Configurations[/b]", border_style="blue")
    else:
        config_panel = Panel(make_config_table(sims), title="[b]Configurations[/b]", border_style="blue")
    layout["config"].update(Padding(config_panel, (1, 1)))

    sim_instance_to_display = None
    if 0 <= selected_index < len(sims):
        sim_instance_to_display = sims[selected_index]
    else:
        log.warning(f"Invalid selected index: {selected_index}, sims length: {len(sims)}")

    log.debug(f"Updating register panel for sim index {selected_index}")
    register_panel = Panel(make_register_table(sim_instance_to_display, selected_index), title=f"[b]Live Registers (Sim #{selected_index + 1 if sim_instance_to_display else 'N/A'})[/b]", border_style="blue")
    layout["registers"].update(Padding(register_panel, (1, 1)))

    instructions = f"[dim]Press 1-{len(sims)} to view a simulation, Left/Right arrows to cycle, Ctrl+C to stop, [bold green]Press 'a' to add a new simulation[/bold green].[/dim]"
    layout["footer"].update(Panel(instructions, style="dim"))

    live.update(layout)
    log.debug("Display updated")

# --- User Configuration Input ---
def get_user_config(simulation_count: int, defaults: Dict[str, Any]) -> tuple:
    """
    Prompt the user for simulation configuration (IP, port, slave ID).

    Args:
        simulation_count (int): Current number of simulations (for display).
        defaults (Dict[str, Any]): Default values from the config.

    Returns:
        tuple: (ip, port, slave_id)
    """
    log.info(f"Configuring Simulation #{simulation_count+1}")
    console.print(f"\n[bold green]--- Configuration for Simulation #{simulation_count+1} ---[/bold green]")

    default_ip = defaults["ip"]
    default_port = defaults["port"]
    default_slave_id = defaults["slave_id"] + simulation_count

    log.debug("Prompting for IP...")
    console.print(f"Enter IP Address to listen on [default: {default_ip}]: ", end="")
    ip = input().strip() or default_ip
    log.debug(f"IP received: '{ip}'")

    while True:
        log.debug("Prompting for Port...")
        console.print(f"Enter TCP Port [default: {default_port}]: ", end="")
        port_str = input().strip() or str(default_port)
        log.debug(f"Port string received: '{port_str}'")
        try:
            port = int(port_str)
            if 0 < port < 65536:
                log.debug(f"Port parsed as: {port}")
                break
            else:
                console.print("[yellow]Port must be between 1 and 65535.[/yellow]")
                log.warning(f"Invalid port entered: {port}")
        except ValueError:
            console.print("[yellow]Invalid port number.[/yellow]")
            log.warning(f"Non-integer port entered: '{port_str}'")

    while True:
        log.debug("Prompting for Slave ID...")
        console.print(f"Enter Slave ID (1-247) [default: {default_slave_id}]: ", end="")
        slave_id_str = input().strip() or str(default_slave_id)
        log.debug(f"Slave ID string received: '{slave_id_str}'")
        try:
            slave_id = int(slave_id_str)
            if 0 < slave_id < 248:
                log.debug(f"Slave ID parsed as: {slave_id}")
                break
            else:
                console.print("[yellow]Slave ID must be between 1 and 247.[/yellow]")
                log.warning(f"Invalid Slave ID entered: '{slave_id_str}'")
        except ValueError:
            console.print("[yellow]Invalid Slave ID.[/yellow]")
            log.warning(f"Non-integer Slave ID entered: '{slave_id_str}'")

    log.info(f"Configuration complete: IP={ip}, Port={port}, SlaveID={slave_id}")
    return ip, port, slave_id

# --- Main Execution ---
if __name__ == "__main__":
    # Display startup banner
    console.clear()
    banner = """
    ╔══════════════════════════════╗
    ║     ModSim Pro v1.5.0        ║
    ║  Simulate Modbus with ease!  ║
    ╚══════════════════════════════╝
    """
    console.print(banner, style="bold blue")
    console.print("[cyan]Loading configuration...[/cyan]")
    log.info("Simulator starting...")

    # Load configuration
    try:
        config = load_config("config.yaml")
    except Exception as e:
        log.error(f"Failed to load configuration: {e}")
        console.print(f"[bold red]Failed to load configuration: {e}[/bold red]")
        console.print(f"[bold red]Please check if config.yaml exists and is correctly formatted.[/bold red]")
        exit(1)

    simulations_configured = False

    while not simulations_configured:
        sim_count = len(simulations)
        try:
            ip, port, slave_id = get_user_config(sim_count, config["defaults"])
            sim_instance = SimulationInstance(ip, port, slave_id)
            sim_instance.start()
            log.info(f"Simulation instance {slave_id}@{ip}:{port} requested to start.")
            time.sleep(0.01)

            with lock:
                simulations.append(sim_instance)
                log.debug(f"Simulations list: {len(simulations)} instances")
        except Exception as e:
            log.error(f"Failed to create simulation: {e}")
            console.print(f"[bold red]Failed to create simulation: {e}[/bold red]")
            console.print("[yellow]Please check the port availability or try a different port.[/yellow]")
            continue

        if not simulations_configured:
            console.print("\nAdd another simulation? (y/N): ", end="")
            add_more = input().strip().lower()
            if add_more != 'y':
                simulations_configured = True

    try:
        with Live(generate_layout(), refresh_per_second=10, screen=True, transient=False) as live:
            live.console.print("\n[bold yellow]Simulations running. Press 1-N to view, Left/Right arrows to cycle, Ctrl+C to stop.[/bold yellow]")
            log.info("Configuration phase complete. Entering running state.")
            while True:
                for i in range(1, len(simulations) + 1):
                    if keyboard.is_pressed(str(i)):
                        selected_simulation_index = i - 1
                        log.debug(f"Selected simulation #{i}")
                        time.sleep(0.01)
                        break

                if keyboard.is_pressed('right'):
                    selected_simulation_index = (selected_simulation_index + 1) % len(simulations)
                    log.debug(f"Cycled to simulation #{selected_simulation_index + 1}")
                    time.sleep(0.01)
                elif keyboard.is_pressed('left'):
                    selected_simulation_index = (selected_simulation_index - 1) % len(simulations)
                    log.debug(f"Cycled to simulation #{selected_simulation_index + 1}")
                    time.sleep(0.01)
                elif keyboard.is_pressed('a'):
                    live.stop()
                    console.print("\n[bold green]Adding a new simulation...[/bold green]")
                    sim_count = len(simulations)
                    try:
                        ip, port, slave_id = get_user_config(sim_count, config["defaults"])
                        sim_instance = SimulationInstance(ip, port, slave_id)
                        sim_instance.start()
                        log.info(f"New simulation instance {slave_id}@{ip}:{port} requested to start.")
                        time.sleep(0.01)

                        with lock:
                            simulations.append(sim_instance)
                        console.print("[bold green]New simulation added and started.[/bold green]")
                    except Exception as e:
                        log.error(f"Failed to add new simulation: {e}")
                        console.print(f"[bold red]Failed to add new simulation: {e}[/bold red]")
                    time.sleep(0.05)
                    live.start()

                update_display(live, simulations, selected_index=selected_simulation_index)

                with lock:
                    any_stopped = False
                    for sim in simulations:
                        if not sim.is_alive():
                            log.warning(f"Simulation {sim.slave_id}@{sim.ip}:{sim.port} server thread appears stopped.")
                            any_stopped = True
                    if any_stopped:
                        live.console.print("[bold yellow]One or more simulations stopped unexpectedly. Check simulator.log[/bold yellow]")

                time.sleep(UPDATE_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        log.info("KeyboardInterrupt received. Stopping simulator...")
        print("\n[bold yellow]Stopping simulator...[/bold yellow]")
        with lock:
            for sim in simulations:
                sim.stop()
        time.sleep(0.01)

    except Exception as e:
        log.exception("FATAL: An unexpected error occurred in main loop:")
        print(f"\n[bold red]FATAL ERROR in main loop: {e}[/bold red]")
        print(f"[bold red]Check {LOG_FILENAME} for details.[/bold red]")

    log.info("Simulator finished.")
    console.print("[cyan]Simulator finished.[/cyan]")