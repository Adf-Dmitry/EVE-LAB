EVE-LAB
Multilayer computer network

## Current Topology
<img width="1662" height="898" alt="image" src="https://github.com/user-attachments/assets/869d4ef9-04e0-4a36-aa25-766eb4123ae8" />

## DEPLOY
* Before using these configurations, replace labels "REDACTED" with your actual passwords.

# Argentum

Argentum is a fast, multi-threaded Command Line Interface (CLI) utility for managing and automating network devices. Built with [Typer](https://typer.tiangolo.com/) and [Netmiko](https://github.com/ktbyers/netmiko), it allows network engineers to seamlessly check device availability and execute commands across single or multiple devices concurrently.

## Features

- **Multi-threaded Execution:** Run commands simultaneously across multiple devices using `ThreadPoolExecutor` for drastically reduced execution times.
- **Smart Device Discovery:** Automatically detects your OS (Windows, Linux, macOS) and pings devices to ensure they are online before attempting SSH connections.
- **Environment Variable Security:** Safely loads sensitive credentials (usernames and passwords) from a `.env` file.
- **YAML Inventory:** Easily manage your network inventory using a clean, readable `devices.yaml` format.
- **Modern CLI:** Provides a user-friendly command-line interface with built-in `--help` menus.

## Prerequisites

- **Python 3.10+** (Required for the `match/case` syntax used in OS detection)
- Python packages: `netmiko`, `typer`, `pyyaml`, `python-dotenv`

## Installation

1. Clone the repository or download the source code.
2. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On Linux/macOS:
   source .venv/bin/activate
   ```
3. Install the required dependencies:
   ```bash
   pip install netmiko typer pyyaml python-dotenv
   ```

## Configuration

Before running Argentum, you need to set up your credentials and device inventory.

### 1. Credentials (`.env`)
Create a file named `.env` in the root directory of the project and add your SSH credentials:

```env
ROUTER_USER=admin
ROUTER_PASS=YourSecurePassword123
```

### 2. Device Inventory (`devices.yaml`)
Create a `devices.yaml` file to define your network devices. The structure follows standard Netmiko dictionary arguments. 

```yaml
core_switch_1:
  device_type: cisco_ios
  host: 192.168.10.1

access_switch_2:
  device_type: cisco_ios
  host: 192.168.10.2

edge_router_1:
  device_type: juniper_junos
  host: 10.0.0.1
```
*(Note: Do not include `username` and `password` here, as Argentum automatically injects them from your `.env` file).*

## Usage

Argentum provides a simple CLI with built-in documentation. You can view all available commands by running:

```bash
python main_2.py --help
```

### Check Active Devices
To ping all devices in your `devices.yaml` inventory and print a list of reachable hosts:

```bash
python main_2.py active
```

### Execute a Command on a Specific Device
Use the `seldev` command with flags to target a specific device from your inventory. 
* `-d` or `--device`: The name of the device (must match the key in `devices.yaml`).
* `-c` or `--command`: The CLI command to execute.

```bash
python main_2.py seldev -d core_switch_1 -c "show ip interface brief"
```

### Execute a Command on All Active Devices
Use the `all-dev` command to run a specific command across **all online devices** simultaneously. Argentum will first ping all devices and only attempt SSH connections to the active ones.

```bash
python main_2.py all-dev "write memory"
```
*(Note: Replace `main_2.py` with your actual script name if you rename the file).*

## Error Handling

- **Missing Files:** The tool will alert you and exit gracefully if `devices.yaml` is not found or is improperly formatted.
- **Connection Timeouts:** If a device drops offline between the ping check and the SSH attempt, Netmiko timeout exceptions are caught and reported without crashing the rest of the threads.
