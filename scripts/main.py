import os
import sys
import yaml
from dotenv import load_dotenv
from netmiko import ConnectHandler
import subprocess

class NetworkManager:
    def __init__(self, inventory_file='devices.yaml'):
        self.active_devices = None
        load_dotenv()
        self.username = os.getenv("ROUTER_USER")
        self.password = os.getenv("ROUTER_PASS")
        self.inventory_file = inventory_file
        self.devices = self._load_inventory()
        self.active_devices = []

    def check_online_devices(self):
        print("Checking for active devices...")
        self.active_devices = []

        for name,config in  self.devices.items():
            host = config.get('host')
            if not host:
                continue
            command = ['ping','-c','1','-W','1',host]
            result = subprocess.run(command,stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if result.returncode == 0:
                self.active_devices.append(name)

        self.show_devices()

    def _load_inventory(self):
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
        device_config = device_info.copy()
        device_config['username'] = self.username
        device_config['password'] = self.password

        with ConnectHandler(**device_config) as net_connect:
            return net_connect.send_command(command)

    def run_on_all_devices(self, command):
        results = {}

        for name in self.active_devices:
            config = self.devices[name]
            try:
                output = self.execute_command(config, command)
                print(output)
                results[name] = output

            except Exception as e:
                print(f"Failed to connect to {name}: {e}")
        return results

    def show_devices(self):
        if hasattr(self, 'active_devices') and self.active_devices:
            print("\nAvailable devices:")

            for dev in self.active_devices:
                print(f"- {dev}")
            return self.active_devices
        else:
            print("\nNo devices available")
            return []

    def configure_dedicated_device(self, device_name, command):
        if device_name not in self.devices:
            print(f"Device '{device_name}' not found in inventory.")
            return None
        try:
            output = self.execute_command(self.devices[device_name], command)
            print(output)
            return output
        except Exception as e:
            print(f"Failed to connect to {device_name}: {e}")
            return None

if __name__ == "__main__":
    lab_manager = NetworkManager("devices.yaml")
    lab_manager.check_online_devices()
    close = False

    while not close:
        user_input = input("\n> ").strip().lower()
        match user_input:
            case "active":
                lab_manager.check_online_devices()

            case "seldev":
                selected_device = input("Enter Device Name").strip().lower()
                cmd_to_run = input(f"Enter Command for {selected_device}").strip()
                if cmd_to_run:
                    lab_manager.configure_dedicated_device(selected_device, cmd_to_run)
                else:
                    print("Invalid Command")

            case "help":
                print("\nAvailable commands:")
                print("active  - show active devices")
                print("seldev  - select one device to configure")
                print("all     - run command on all available devices")
                print("help    - show this message")
                print("exit|quit - exit the program")

            case "all":
                cmd_to_run = input("Enter Command").strip()
                if cmd_to_run:
                    lab_manager.run_on_all_devices(cmd_to_run)
                else:
                    print("Invalid Command")

            case "exit" | "quit":
                print("Exiting...")
                close = True

            case _:
                print("Invalid Command. To show a list of available commands enter help")