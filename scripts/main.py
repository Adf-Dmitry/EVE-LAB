"""
Argentum - CLI Utility for managing network devices.
"""
import os
import sys
import subprocess
import platform
from concurrent.futures import ThreadPoolExecutor, as_completed

import yaml
import typer
from dotenv import load_dotenv
from netmiko import ConnectHandler, NetmikoTimeoutException

class NetworkManager:
    """Manages inventory and connections for network devices."""
    def __init__(self, inventory_file='devices.yaml'):
        self.active_devices = None
        load_dotenv()
        self.username = os.getenv("ROUTER_USER")
        self.password = os.getenv("ROUTER_PASS")
        self.inventory_file = inventory_file
        self.devices = self._load_inventory()
        self.active_devices = []
        self.current_os = platform.system().lower()

    def _get_ping_command (self, host):
        """Generates the appropriate ping command based on the OS."""
        match self.current_os:
            case 'windows':
                return ['ping', '-n', '1', '-w', '1000', host]
            case 'darwin' | 'linux':
                return ['ping', '-c', '1', '-W', '1', host]
            case _:
                print(f"Warning: Unknown OS '{self.current_os}'. Defaulting to Unix ping.")
                return ['ping', '-c', '1', '-W', '1', host]

    def check_online_devices(self):
        """Pings devices in the inventory to check if they are online."""
        print("Checking for active devices...")
        self.active_devices = []

        for name,config in  self.devices.items():
            host = config.get('host')
            if not host:
                continue
            command =  self._get_ping_command(host)
            result = subprocess.run(
            command,stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check = False
            )
            if result.returncode == 0:
                self.active_devices.append(name)

        self.show_devices()

    def _load_inventory(self):
        """Loads device configurations from the YAML inventory file."""
        try:
            with open(self.inventory_file, 'r') as file:
                return yaml.safe_load(file)
        except FileNotFoundError:
            print(f"Error: Inventory file '{self.inventory_file}' not found.")
            sys.exit(1)
        except yaml.YAMLError as e:
            print(f"Error: parsing YAML file '{self.inventory_file}': {e}")
            sys.exit(1)

    def execute_command(self, device_info, command):
        """Executes a single command on a specific device."""
        device_config = device_info.copy()
        device_config['username'] = self.username
        device_config['password'] = self.password

        with ConnectHandler(**device_config) as net_connect:
            return net_connect.send_command(command)

    def run_on_all_devices(self, command):
        """Executes a command concurrently on all active devices."""
        if not self.active_devices:
            print("No active devices to run commands on.")
            return {}

        results = {}
        max_workers = min(len(self.active_devices), 20)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_device = {
                executor.submit(self.execute_command, self.devices[name], command): name
                for name in self.active_devices
            }

            for future in as_completed(future_to_device):
                name = future_to_device[future]
                try:
                    output = future.result()
                    print(f"\n[{name}] Output:\n{output}")
                    results[name] = output

                except NetmikoTimeoutException:
                    print(f"\nFailed to connect to {name}.")

        return results

    def show_devices(self):
        """Displays all currently active devices."""
        if hasattr(self, 'active_devices') and self.active_devices:
            print("\nAvailable devices:")

            for dev in self.active_devices:
                print(f"- {dev}")
            return self.active_devices
        else:
            print("\nNo devices available")
            return []

    def configure_dedicated_device(self, device_name, command):
        """Runs a command on a specific named device."""
        if device_name not in self.devices:
            print(f"Device '{device_name}' not found in inventory.")
            return None
        try:
            output = self.execute_command(self.devices[device_name], command)
            print(output)
            return output

        except NetmikoTimeoutException:
            print(f"Failed to connect to {device_name}")
            return None

app = typer.Typer(help="CLI Utility for managing devices.")
lab_manager = NetworkManager("devices.yaml")

@app.command()
def active():
    """
    Show active devices.
    """
    lab_manager.check_online_devices()

@app.command()
def seldev(
    device: str = typer.Option(
        ...,
        "-d",
        "--device",
        help="Name of the device (e.g., core_switch_1)"),
    command: str = typer.Option(..., "-c", "--command", help="Command to execute")
):
    """
    Execute a command on a specific device using flags.
    """
    lab_manager.configure_dedicated_device(device, command)

@app.command()
def all_devices(
    command: str = typer.Option(
        ...,
        "-c",
        "--command",
        help="Command to execute on all active devices")
):
    """
    Execute a command on all available devices.
    """
    lab_manager.check_online_devices()
    lab_manager.run_on_all_devices(command)

if __name__ == "__main__":
    app()