import ipaddress
import subprocess
import sys
import time
import socket

import requests


def get_public_ip():
    try:
        # The 2 second timeout matters more than it looks: the poll
        # loop in main sleeps only 0.1 seconds, so a hanging request
        # is the thing that would set the real polling pace, and an
        # unbounded one would stall the monitor for good.
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
    # I use the hostname lookup as "the local address", and both
    # comparisons in main lean on that. It is shakier than it looks:
    # on plenty of machines the hostname resolves to 127.0.0.1, and a
    # public address will never equal that, so the script would read
    # the machine as behind a VPN from the first poll.
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        return local_ip
    except socket.gaierror:
        return None


def notify(title, body, sound):
    # The body still goes into an AppleScript string, quotes and all.
    # That is only safe because every caller passes a fixed title and
    # a body built from the validated address out of get_public_ip.
    # A free text body with a double quote in it would break out of
    # this string, so I do not pass anything else through here.
    script = f'display notification "{body}" with title "{title}" sound name "{sound}"'
    # check=False on purpose: on a machine without osascript the
    # notification fails quietly and the monitor keeps polling. The
    # trade is that a real notification failure is never reported.
    subprocess.run(["osascript", "-e", script], check=False)


def main():
    # The local address is read once, before the loop. If the machine
    # joins a different network while this runs, every comparison
    # below still uses the address from startup until I restart it.
    local_network_ip = get_local_ip()
    vpn_active = False
    # 0.1 seconds is only the sleep between polls. Each poll is also a
    # full HTTPS request to ipinfo.io, so the service gets hit about
    # as fast as the round trip allows. That rate is the aggressive
    # part of this monitor, and it is why a rate limit from ipinfo
    # would show up here as a stream of "Could not retrieve" lines.
    check_interval = 0.1

    print("Starting AGGRESSIVE CONTINUOUS IP Monitor (using ipinfo.io). Connect to VPN now.")

    try:
        while True:
            current_public_ip = get_public_ip()

            if current_public_ip:
                print(f"Current public IP: {current_public_ip}")
                # Neither notify branch has any rate limit. While
                # the public address sits on the local address, a
                # notification fires on every poll, many times a
                # second. Loud is what I wanted from a leak alarm,
                # but the no VPN branch does the same thing at
                # startup before any VPN was ever seen.
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


USAGE = (
    "Usage: python3 leak_test.py [--help]\n"
    "Poll ipinfo.io for the public IP and raise a macOS notification\n"
    "when it matches the local address. Takes no arguments. Stop with Ctrl+C."
)


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] in ("--help", "-h"):
        print(USAGE)
    elif len(sys.argv) > 1:
        print(f"Error: unknown argument: {sys.argv[1]}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        sys.exit(2)
    else:
        main()
