import os
import yaml
from dotenv import load_dotenv
from netmiko import ConnectHandler
class NetworkManager:
    def __init__(self, inventory_file = 'devices.yaml'):
        load_dotenv()
        self.username = os.getenv("ROUTER_USER")
        self.password = os.getenv("ROUTER_PASS")
        self.inventory_file = inventory_file
        self.devices = self._load_inventory()

    def _load_inventory(self):
        with open(self.inventory_file, 'r') as file:
            return yaml.safe_load(file)

    def execute_command(self, device_info, command):
        device_config = device_info.copy()
        device_config['username'] = self.username
        device_config['password'] = self.password

        with ConnectHandler(**device_info) as net_connect:
            return net_connect.send_command(command)

    def run_on_all_devices(self, command):
        results = {}
        for name,config in self.devices.items():
            try:
                output = self.execute_command(config, command)
                print (output)
                results[name] = output
            except Exception as e:
                print (f"Failed to connect to {name}:{e}")
        return results
if __name__ == "__main__":
    lab_manager = NetworkManager("devices.yaml")
    lab_manager.run_on_all_devices("show version")
