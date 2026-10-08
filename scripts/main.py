"""
Argentum - CLI Utility for managing network devices.

Requires Python 3.10+ (uses the `match` statement).
"""
import os
import platform
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import jinja2
import typer
import yaml
from dotenv import load_dotenv
from netmiko import (
    ConnectHandler,
    NetmikoAuthenticationException,
    NetmikoTimeoutException,
)

MAX_WORKERS = 20
PING_TIMEOUT_SEC = 5

def read_yaml(path, label):
    """
    Reads a YAML file and returns a dict.
    """
    try:
        with open(path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
    except FileNotFoundError:
        typer.echo(f"Error: {label} file '{path}' not found.", err=True)
        raise typer.Exit(code=1)
    except yaml.YAMLError as e:
        typer.echo(f"Error: failed to parse {label} file '{path}': {e}", err=True)
        raise typer.Exit(code=1)

    if data is None:
        return {}
    if not isinstance(data, dict):
        typer.echo(
            f"Error: {label} file '{path}' must contain a YAML mapping at the top level.",
            err=True,
        )
        raise typer.Exit(code=1)
    return data


def format_error(exc):
    """
    Turns an exception into a short human-readable message.
    """
    if isinstance(exc, NetmikoTimeoutException):
        return "Connection timed out"
    if isinstance(exc, NetmikoAuthenticationException):
        return "Authentication failed"
    return f"{type(exc).__name__}: {exc}"


def find_device_vars(vars_data, target):
    """
    Looks up the variables of a device in the parsed vars file.
    """
    wanted = target.lower()
    for group_val in vars_data.values():
        if not isinstance(group_val, dict):
            continue
        if isinstance(group_val.get(target), dict):
            return group_val[target]
        for key, val in group_val.items():
            if not isinstance(val, dict):
                continue
            if str(key).lower() == wanted or str(val.get('hostname', '')).lower() == wanted:
                return val
    return None


class NetworkManager:
    """Manages inventory and connections for network devices."""

    def __init__(self, inventory):
        load_dotenv()
        self.username = os.getenv("ROUTER_USER")
        self.password = os.getenv("ROUTER_PASS")

        self.inventory_file = inventory
        self.current_os = platform.system().lower()
        if self.current_os not in ('windows', 'darwin', 'linux'):
            typer.echo(
                f"Warning: Unknown OS '{self.current_os}'. Defaulting to Unix ping.",
                err=True,
            )

        self.inventory_groups = {}
        self.active_devices = []
        self.devices = self._load_inventory()

    # Inventory

    def _load_inventory(self):
        """Loads device configurations from the YAML inventory file."""
        raw_data = read_yaml(self.inventory_file, "Inventory")

        flattened_devices = {}
        for key, val in raw_data.items():
            if not isinstance(val, dict):
                typer.echo(f"Warning: inventory entry '{key}' is not a mapping. Skipping.", err=True)
                continue

            if 'host' in val:
                flattened_devices[key] = val
                continue

            group = {}
            for dev_name, dev_config in val.items():
                if isinstance(dev_config, dict):
                    group[dev_name] = dev_config
                else:
                    typer.echo(
                        f"Warning: device '{dev_name}' in group '{key}' is not a mapping. Skipping.",
                        err=True,
                    )
            self.inventory_groups[key] = group
            flattened_devices.update(group)
        return flattened_devices

    def require_credentials(self):
        """Stops early with a clear message if credentials are not configured."""
        if not self.username or not self.password:
            typer.echo(
                "Error: ROUTER_USER and ROUTER_PASS must be set "
                "(environment variables or .env file).",
                err=True,
            )
            raise typer.Exit(code=1)

    def _connection_params(self, device_info):
        """Builds Netmiko connection parameters for a device."""
        params = device_info.copy()
        params['username'] = self.username
        params['password'] = self.password
        return params

    # ------------------------------------------------------------------ #
    # Availability check
    # ------------------------------------------------------------------ #
    def _get_ping_command(self, host):
        """Generates the appropriate ping command based on the OS."""
        match self.current_os:
            case 'windows':
                return ['ping', '-n', '1', '-w', '1000', host]
            case 'darwin':
                return ['ping', '-c', '1', '-W', '1000', host]
            case _:
                return ['ping', '-c', '1', '-W', '1', host]

    def _is_online(self, host):
        """Returns True if the host answers a single ping."""
        try:
            result = subprocess.run(
                self._get_ping_command(host),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=PING_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            return False
        except FileNotFoundError:
            typer.echo("Error: 'ping' command not found on this system.", err=True)
            raise typer.Exit(code=1)
        return result.returncode == 0

    def check_online_devices(self):
        """Pings devices in the inventory (concurrently) to check if they are online."""
        typer.echo("Checking for active devices...")

        hosts = {
            name: str(config['host'])
            for name, config in self.devices.items()
            if config.get('host')
        }

        self.active_devices = []
        if hosts:
            with ThreadPoolExecutor(max_workers=min(len(hosts), MAX_WORKERS)) as executor:
                online_flags = executor.map(self._is_online, hosts.values())
                self.active_devices = [
                    name for name, online in zip(hosts, online_flags) if online
                ]
        self.show_devices()

    def show_devices(self):
        """Displays all currently active devices."""
        if self.active_devices:
            typer.echo("\nAvailable devices:")
            for dev in self.active_devices:
                typer.echo(f"- {dev}")
            return self.active_devices

        typer.echo("\nNo devices available")
        return []

    # ------------------------------------------------------------------ #
    # Working with devices
    # ------------------------------------------------------------------ #
    def execute_command(self, device_info, command):
        """Executes a single command on a specific device."""
        with ConnectHandler(**self._connection_params(device_info)) as net_connect:
            return net_connect.send_command(command)

    def push_configuration(self, device_info, config_text):
        """
        Pushes a rendered multiline configuration to a specific device and saves it.
        """

        config_lines = [line.rstrip() for line in config_text.splitlines() if line.strip()]
        if not config_lines:
            raise ValueError("rendered configuration is empty")

        with ConnectHandler(**self._connection_params(device_info)) as net_connect:
            output = net_connect.send_config_set(config_lines)
            try:
                output += "\n" + net_connect.save_config()
            except NotImplementedError:
                output += (
                    "\n[!] save_config() is not supported for this device type: "
                    "the configuration was applied but NOT saved."
                )
        return output

    def run_on_all_devices(self, command):
        """Executes a command concurrently on all active devices."""
        if not self.active_devices:
            typer.echo("No active devices to run commands on.")
            return {}

        self.require_credentials()

        results = {}
        max_workers = min(len(self.active_devices), MAX_WORKERS)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_device = {
                executor.submit(self.execute_command, self.devices[name], command): name
                for name in self.active_devices
            }

            for future in as_completed(future_to_device):
                name = future_to_device[future]
                try:
                    output = future.result()
                except Exception as e:  # one broken device must not stop the others
                    typer.echo(f"\n[{name}] Failed: {format_error(e)}", err=True)
                else:
                    typer.echo(f"\n[{name}] Output:\n{output}")
                    results[name] = output
        return results

    def configure_dedicated_device(self, device_name, command):
        """Runs a command on a specific named device. Returns None on failure."""
        if device_name not in self.devices:
            typer.echo(f"Device '{device_name}' not found in inventory.", err=True)
            return None

        self.require_credentials()
        try:
            output = self.execute_command(self.devices[device_name], command)
        except Exception as e:
            typer.echo(f"[{device_name}] Failed: {format_error(e)}", err=True)
            return None

        typer.echo(output)
        return output


app = typer.Typer(help="CLI Utility for managing devices.")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    inventory: str = typer.Option(
        ..., "-i", "--inventory",
        help="Inventory file to use, must contain your network devices list in YAML format"
    ),
    device: Optional[str] = typer.Option(
        None, "-d", "--device",
        help="Name of the device (e.g., core_switch_1)"
    ),
    all_devices: bool = typer.Option(
        False, "-a", "--all",
        help="Select all active devices."
    ),
    command: Optional[str] = typer.Option(
        None, "-c", "--command",
        help="Command to execute"
    )
):
    """
    Global initialization of inventory file and default execution.
    """
    manager = NetworkManager(inventory)
    ctx.obj = manager  # shared with subcommands instead of a global variable

    if ctx.invoked_subcommand is not None:
        return

    if not command:
        typer.echo("Error: You must provide a --command (-c) to execute.", err=True)
        raise typer.Exit(code=1)

    if all_devices:
        if device:
            typer.echo(
                "Warning: Both --device and --all provided. "
                "Ignoring --device and running on all active devices.",
                err=True,
            )
        manager.check_online_devices()
        results = manager.run_on_all_devices(command)
        if len(results) != len(manager.active_devices):
            raise typer.Exit(code=1)  # at least one device failed
    elif device:
        if manager.configure_dedicated_device(device, command) is None:
            raise typer.Exit(code=1)
    else:
        typer.echo("Error: You must specify a target using either --device (-d) or --all (-a).", err=True)
        raise typer.Exit(code=1)


@app.command()
def active(ctx: typer.Context):
    """
    Show active devices.
    """
    ctx.obj.check_online_devices()


@app.command()
def deploy(
    ctx: typer.Context,
    vars_file: str = typer.Option(..., "-v", "--vars", help="Variables YAML file"),
    templates_dir: str = typer.Option(".", "-t", "--templates", help="Jinja2 templates directory"),
    device: Optional[str] = typer.Option(None, "-d", "--device", help="Specific device to deploy to"),
    all_devices: bool = typer.Option(False, "-a", "--all", help="Deploy to all online devices")
):
    """
    Render templates and automatically deploy configuration to devices.
    """
    manager: NetworkManager = ctx.obj

    if not device and not all_devices:
        typer.echo("Error: Specify target using --device (-d) or --all (-a).", err=True)
        raise typer.Exit(code=1)

    if device and all_devices:
        typer.echo("Warning: Both --device and --all provided. Ignoring --device.", err=True)

    if not os.path.isdir(templates_dir):
        typer.echo(f"Error: templates directory '{templates_dir}' not found.", err=True)
        raise typer.Exit(code=1)

    vars_data = read_yaml(vars_file, "Variables")

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(templates_dir),
        undefined=jinja2.StrictUndefined,
    )

    if all_devices:
        manager.check_online_devices()
        targets = manager.active_devices
    else:
        if device not in manager.devices:
            typer.echo(f"Error: Device '{device}' not found in inventory.", err=True)
            raise typer.Exit(code=1)
        targets = [device]

    if not targets:
        raise typer.Exit(code=1)

    manager.require_credentials()
    failed = []

    for target in targets:
        target_group = next(
            (group for group, devs in manager.inventory_groups.items() if target in devs),
            None,
        )
        if not target_group:
            typer.echo(f"Warning: {target} is not in any group in inventory. Skipping.", err=True)
            failed.append(target)
            continue

        template_name = f"{target_group}_template.j2"

        dev_vars = find_device_vars(vars_data, target)
        if not dev_vars:
            typer.echo(
                f"Warning: No configuration variables found for '{target}' in '{vars_file}'. Skipping.",
                err=True,
            )
            failed.append(target)
            continue

        try:
            template = env.get_template(template_name)
            rendered_config = template.render(dev_vars)

        except jinja2.TemplateNotFound:
            typer.echo(f"Error: Template '{template_name}' not found in '{templates_dir}'.", err=True)
            failed.append(target)
            continue

        except Exception as e:
            typer.echo(f"Error rendering '{template_name}' for {target}: {e}", err=True)
            failed.append(target)
            continue

        typer.echo(f"\n[{target}] Generating and pushing configuration via {template_name}...")
        try:
            output = manager.push_configuration(manager.devices[target], rendered_config)
        except Exception as e:
            typer.echo(f"[{target}] Deployment FAILED: {format_error(e)}", err=True)
            failed.append(target)
            continue
        typer.echo(f"[{target}] Deployment Result:\n{output}")

    if failed:
        typer.echo(f"\nDeployment finished with problems on: {', '.join(failed)}", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()