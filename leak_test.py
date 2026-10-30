import ipaddress
import subprocess
import time
import socket

import requests


def get_public_ip():
    try:
        response = requests.get("https://ipinfo.io/ip", timeout=2)
        response.raise_for_status()
        candidate = response.text.strip()
        # Only accept a real IP address back. Anything else (an error
        # page, markup, or text with quotes in it) is not an IP and
        # must never reach the notification command below.
        return str(ipaddress.ip_address(candidate))
    except requests.exceptions.RequestException as e:
        print(f"Error getting public IP from ipinfo.io: {e}")
        return None
    except ValueError:
        print("Error getting public IP from ipinfo.io: response was not an IP address")
        return None


def get_local_ip():
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        return local_ip
    except socket.gaierror:
        return None


def notify(title, body, sound):
    script = f'display notification "{body}" with title "{title}" sound name "{sound}"'
    subprocess.run(["osascript", "-e", script], check=False)


def main():
    local_network_ip = get_local_ip()
    vpn_active = False
    check_interval = 0.1

    print("Starting AGGRESSIVE CONTINUOUS IP Monitor (using ipinfo.io). Connect to VPN now.")

    try:
        while True:
            current_public_ip = get_public_ip()

            if current_public_ip:
                print(f"Current public IP: {current_public_ip}")
                if not vpn_active and current_public_ip == local_network_ip:
                    notify(
                        "Internet (No VPN) (CONTINUOUS)",
                        f"Public IP is your local network IP: {current_public_ip}",
                        "Sosumi",
                    )
                elif vpn_active and current_public_ip == local_network_ip:
                    notify(
                        "POTENTIAL VPN LEAK DETECTED! (CONTINUOUS)",
                        f"WARNING! Public IP has reverted to local: {current_public_ip}",
                        "Glass",
                    )
                    vpn_active = False  # Ensure vpn_active reflects the state
                elif not vpn_active and current_public_ip != local_network_ip:
                    # A public IP that differs from the local address is
                    # the only sign this script can see that traffic is
                    # leaving through something else (for example a VPN),
                    # so treat it as the active state. Without this the
                    # leak alert below could never fire at all.
                    vpn_active = True
            else:
                print("Could not retrieve public IP.")

            time.sleep(check_interval)

    except KeyboardInterrupt:
        print("\nStopping CONTINUOUS IP Monitor.")


if __name__ == "__main__":
    main()
