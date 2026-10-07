EVE-LAB
Multilayer computer network

## Current Topology
<img width="1662" height="898" alt="image" src="https://github.com/user-attachments/assets/869d4ef9-04e0-4a36-aa25-766eb4123ae8" />

## DEPLOY
* Before using these configurations, replace labels "REDACTED" with your actual passwords.

# Argentum

Argentum is a Python-based Command Line Interface (CLI) utility designed for managing and interacting with network devices. It allows network administrators to execute commands on a single device or concurrently across multiple active devices using SSH/Telnet, powered by `netmiko`. 

## Features

- **Concurrent Execution:** Run commands simultaneously across multiple active devices using multi-threading.
- **Cross-Platform Ping Check:** Automatically detects your OS (Windows, macOS, or Linux) and pings devices to ensure they are online before attempting to connect.
- **YAML Inventory:** Manage your network devices easily using a structured YAML inventory file.
- **Netmiko Integration:** Supports a vast array of network operating systems (Cisco, Juniper, Arista, HP, etc.).

## Prerequisites

- **Python 3.10+** (Required for structural pattern matching `match/case` support)
- Network access to the target devices

## Installation

1. Clone the repository (or download the source code):
   ```bash
   git clone https://github.com/Adf-Dmitry/EVE-LAB.git
   cd /EVE-LAB/scripts
   ```

2. Create and activate a virtual environment (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Before running Argentum, you need to set up your environment variables and your device inventory.

### 1. Environment Variables (`.env`)

Create a `.env` file in the root directory of the project to store your network credentials:

```env
ROUTER_USER=your_admin_username
ROUTER_PASS=your_super_secret_password
```

### 2. Device Inventory (`devices.yaml`)

Create a YAML file (e.g., `devices.yaml`) containing your device configurations. The key for each device is its name, and the nested properties should map directly to [Netmiko's connection arguments](https://ktbyers.github.io/netmiko/docs/netmiko/index.html).

```yaml
core_sw_1:
  host: 192.168.1.10
  device_type: cisco_ios
  
edge_router_1:
  host: 192.168.1.1
  device_type: cisco_ios

access_sw_1:
  host: 10.0.0.50
  device_type: aruba_os
```

## Usage

Argentum is built with `Typer`, providing a clean CLI experience. 

### Basic Command Structure
```bash
python main.py -i <inventory_file> [OPTIONS] [COMMAND]
```

### Options
- `-i, --inventory TEXT`: **(Required)** Path to your YAML inventory file.
- `-d, --device TEXT`: Name of a specific device to run the command on.
- `-a, --all`: Select all *active* (pingable) devices in the inventory.
- `-c, --command TEXT`: The CLI command to execute on the device(s).

### Examples

**1. Run a command on a specific device:**
```bash
python main.py -i devices.yaml -d core_sw_1 -c "show version"
```

**2. Run a command concurrently on ALL active devices:**
```bash
python main.py -i devices.yaml -a -c "show ip interface brief"
```
*(Note: Argentum will first ping all devices in the YAML file. It will only attempt to connect to the ones that reply to the ping).*

**3. Check which devices are currently online/active:**
```bash
python main.py -i devices.yaml active
```

## Error Handling
- If both `--device` and `--all` are provided, the script will default to running on **all** active devices.
- If a device is unreachable via SSH/Telnet, a `NetmikoTimeoutException` is caught, and the script will gently notify you without crashing.
