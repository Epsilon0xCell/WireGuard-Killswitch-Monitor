![banner](assets/banner.png)

# WireGuard Kill Switch for macOS

A bash script that creates a kill switch for WireGuard VPN on macOS using PF (Packet Filter). While it runs, traffic is passed only when the WireGuard interface is present with the expected MTU; otherwise all traffic is blocked, so a dropped VPN does not leak traffic onto the local network. Make sure your VPN uses MTU 1280: the script treats any other MTU as "VPN not connected".

## Features

- Blocks all traffic when the VPN interface is missing or has the wrong MTU
- Allows traffic in and out on the WireGuard interface while it is up
- Detects the WireGuard interface automatically (MTU 1280, the WireGuard UDP listen port visible in netstat, and an assigned IP), with a `wg show interfaces` fallback and a utun4 final fallback
- Re-checks the connection every 2 seconds and switches the rules when the state changes
- Configurable through environment variables (see below)
- Automatic cleanup on Ctrl+C or SIGTERM: the cleanup function flushes the PF rules and disables PF (see Cleanup)
- Status messages on state changes only, not on every check

## Requirements

- macOS operating system
- WireGuard installed, configured with MTU 1280 and ListenPort 51820 (or set WIREGUARD_PORT to your port)
- Administrative privileges (sudo): the script calls pfctl through sudo

## Installation

1. Clone this repository or download the `killswitch.sh` script:

```bash
git clone https://github.com/Epsilon0xCell/WireGuard-Killswitch-Monitor.git

cd wireguard-killswitch
```

2. Make the script executable:

```bash
chmod +x killswitch.sh
```

## Usage

### Basic Usage

Simply run the script:

```bash
./killswitch.sh
```

Stop it with Ctrl+C. The cleanup function then flushes the PF rules (`sudo pfctl -F all`) and disables PF (`sudo pfctl -d`), restoring normal internet access.

### Configuration

You can configure the script using environment variables:

- `VPN_INTERFACE`: WireGuard interface name. When set, detection is skipped and this interface is monitored directly. When unset, the script auto-detects and falls back to utun4.
- `WIREGUARD_PORT`: WireGuard server listen port used during detection (default: 51820)

Example:

```bash
export VPN_INTERFACE=utun3
export WIREGUARD_PORT=51820
./killswitch.sh
```

The script does not read any PF anchor file: each state change writes the complete ruleset to a temp file and loads it with a single `pfctl -f` call, because a pfctl load replaces the whole main ruleset and loading rules one at a time would discard all but the last. pfctl failures are printed and the state is retried on the next check rather than reported as success. The check interval is a `CHECK_INTERVAL` constant (2 seconds) at the top of the script.

### Finding WireGuard Interface

To determine which interface your WireGuard VPN is using:

1. First, check all available interfaces:

```bash
ifconfig | grep utun
```

2. Note the current interfaces, then connect to your WireGuard VPN

3. Run the same command again:

```bash
ifconfig | grep utun
```

4. The new utun interface that appears is your WireGuard interface. Example output:

```
Before VPN connection:
utun0: flags=8031<UP,POINTOPOINT,RUNNING,MULTICAST> mtu 1490
utun1: flags=8031<UP,POINTOPOINT,RUNNING,MULTICAST> mtu 2000

After VPN connection:
utun0: flags=8031<UP,POINTOPOINT,RUNNING,MULTICAST> mtu 1490
utun1: flags=8031<UP,POINTOPOINT,RUNNING,MULTICAST> mtu 2000
utun3: flags=8031<UP,POINTOPOINT,RUNNING,MULTICAST> mtu 1280  <- This is your WireGuard interface
```

Set ListenPort=51820 in wireguard settings (or export WIREGUARD_PORT with your port).

5. Set the interface via environment variable if auto-detection picks the wrong one:

```bash
export VPN_INTERFACE="utun3"
```

## leak_test.py

A small companion monitor, also macOS only. It polls https://ipinfo.io/ip roughly every 0.1 seconds plus request time, prints the current public IP, and uses macOS notifications (`osascript`) to warn you. It treats the first public IP that differs from your local address as the "VPN active" state; if the public IP later equals your local address, it raises a "POTENTIAL VPN LEAK DETECTED" notification. That is a heuristic based only on comparing the two addresses, not proof of a leak. The service response is validated as an IP address before it is used anywhere.

```bash
pip install -r requirements.txt
python3 leak_test.py
```

Stop it with Ctrl+C.

## Automatic Startup Configuration

To make the kill switch start automatically after system reboot, follow these steps:

1. Copy the script to a permanent location:

```bash
sudo cp killswitch.sh /usr/local/bin/killswitch.sh

sudo chmod +x /usr/local/bin/killswitch.sh
```

2. Create a launch daemon configuration:

```bash
sudo mkdir -p /Library/LaunchDaemons
```

3. Create the launch daemon file `/Library/LaunchDaemons/com.wireguard.killswitch.plist` with this content:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.wireguard.killswitch</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/killswitch.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/killswitch.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/killswitch.error.log</string>
</dict>
</plist>
```

4. Set correct permissions:

```bash
sudo chown root:wheel /Library/LaunchDaemons/com.wireguard.killswitch.plist
sudo chmod 644 /Library/LaunchDaemons/com.wireguard.killswitch.plist
```

5. Load the launch daemon:

```bash
sudo launchctl load -w /Library/LaunchDaemons/com.wireguard.killswitch.plist
```

6. Verify the launch daemon is running:

```bash
sudo launchctl list | grep com.wireguard.killswitch
```

### Managing Autostart

- To stop the service and disable autostart:

```bash
launchctl unload /Library/LaunchDaemons/com.wireguard.killswitch.plist
```

Note: with KeepAlive set, a stopped script is relaunched by launchd while the daemon is loaded, and the cleanup trap still runs on SIGTERM.

## Troubleshooting

### Logs

Check the log files for any issues (only when running under launchd):

```bash
tail -f /var/log/killswitch.log
tail -f /var/log/killswitch.error.log
```

# Cleanup

The `cleanup` function in `killswitch.sh` runs on SIGINT and SIGTERM and uses `sudo pfctl -F all` and `sudo pfctl -d` to flush and disable the Packet Filter (PF) rules. If the script is killed with SIGKILL (`kill -9`), no cleanup can run and the last loaded rules stay in place; run those two pfctl commands by hand in that case.

### Common Issues

1. **Script doesn't start automatically**
   - Check permissions: `chmod +x /path/to/your/killswitch.sh`
   - Verify the path in the plist file
   - Check log files for errors

2. **Permission denied errors**
   - Ensure the script has proper ownership: `sudo chown root:wheel /path/to/your/killswitch.sh`
   - Make sure the script is executable: `chmod +x /path/to/your/killswitch.sh`

3. **Everything is blocked even though the VPN is connected**
   - Check the interface MTU: the script only treats MTU 1280 as connected. Set your WireGuard interface to MTU 1280, or the rules will stay in the blocked state.

## Security Considerations

- The script requires root privileges to modify firewall rules
- All traffic is blocked if the VPN connection drops or reports the wrong MTU
- The loaded rules are deliberately simple: `block all` plus `pass in` and `pass out` on the VPN interface while it is up, `block all` alone otherwise, each state loaded in a single `pfctl -f` call. PF rules loaded this way replace the main PF ruleset while the script runs, and cleanup disables PF rather than restoring a previous ruleset.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details
