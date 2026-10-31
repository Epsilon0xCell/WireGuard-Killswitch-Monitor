#!/bin/bash

# Default VPN interface (fallback if detection fails). Set the
# VPN_INTERFACE environment variable to skip detection and use a
# specific interface instead.
DEFAULT_VPN_INTERFACE="utun4"

# VPN characteristics. The listen port can be overridden with the
# WIREGUARD_PORT environment variable.
# My identification rule is strict: MTU 1280 or it is not WireGuard,
# as far as this script is concerned. A working tunnel on any other
# MTU reads as disconnected here and gets blocked. That false
# negative is built into how I detect, and the README says so.
VPN_MTU=1280
VPN_LISTEN_PORT="${WIREGUARD_PORT:-51820}"

# Seconds to wait between connection checks in the monitor loop
# I added this after measuring my earlier version at 211 ifconfig
# calls in 2 seconds with no sleep at all. Two seconds is the trade
# I picked: a dropped tunnel can leak for up to that long before the
# loop notices, and in exchange the loop stops eating a core.
CHECK_INTERVAL=2

# Arguments are handled before anything touches pf. --help prints
# this text and exits 0; anything else is a mistake and exits 2, so
# a mistyped flag can never start the monitor by accident.
usage() {
    echo "Usage: ./killswitch.sh [--help]"
    echo "Monitor the WireGuard interface and load pf rules that block all"
    echo "traffic while it is down. Takes no arguments. Set VPN_INTERFACE"
    echo "to name the interface and WIREGUARD_PORT to set the listen port"
    echo "(default 51820). Stop with Ctrl+C."
}
if [ "$#" -gt 0 ]; then
    if [ "$#" -eq 1 ] && { [ "$1" = "--help" ] || [ "$1" = "-h" ]; }; then
        usage
        exit 0
    fi
    echo "Error: unknown argument: $1" >&2
    usage >&2
    exit 2
fi

# The port reaches a netstat pattern during detection, so it gets the
# same shape check as the interface name: digits only, in range.
if ! [[ "$VPN_LISTEN_PORT" =~ ^[0-9]+$ ]] || [ "$VPN_LISTEN_PORT" -lt 1 ] || [ "$VPN_LISTEN_PORT" -gt 65535 ]; then
    echo "Error: invalid WIREGUARD_PORT: $VPN_LISTEN_PORT" >&2
    exit 2
fi

# Function to detect WireGuard interface based on MTU and listen port
detect_wg_interface() {
    # Get all utun interfaces
    local interfaces
    interfaces=$(ifconfig -a | grep -E '^utun[0-9]+' | awk '{print $1}' | sed 's/:$//')

    for iface in $interfaces; do
        # Check MTU
        local mtu
        mtu=$(ifconfig "$iface" | grep -E 'mtu' | awk '{print $NF}')
        if [ "$mtu" != "$VPN_MTU" ]; then
            continue
        fi

        # Weak point I know about: the netstat test below is not tied
        # to this interface. It only shows something on this machine
        # listens on the WireGuard port. The MTU and inet checks are
        # what narrow it to this iface, and none of them prove the
        # port belongs to it.
        # Check if the listen port is associated (using netstat to find WireGuard's UDP port)
        if netstat -an | grep -E "udp.*\.$VPN_LISTEN_PORT" &> /dev/null; then
            # Verify interface has an IP (indicating it's active)
            if ifconfig "$iface" | grep -E 'inet ' &> /dev/null; then
                echo "$iface"
                return
            fi
        fi
    done

    # Fallback: Check wg command if available
    local wg_iface
    wg_iface=$(wg show interfaces 2>/dev/null | head -n 1)
    if [ -n "$wg_iface" ]; then
        echo "$wg_iface"
        return
    fi

    echo ""
}

# Rules file: every load writes the complete ruleset to this temp
# file and loads it with a single pfctl -f call. That shape is not
# a style choice. Each pfctl -f load replaces the whole main
# ruleset, so my earlier version, which loaded "pass out" and then
# "pass in" as two loads, ended up holding only the second rule:
# the first load was discarded by the second. The MacOS killswitch
# repo I keep beside this one loads block and pass together for
# exactly this reason, and this script now does the same.
RULES_FILE="$(mktemp /tmp/wireguard-killswitch-pf.XXXXXX)" || exit 1

# Load the ruleset currently written in RULES_FILE. Returns
# non-zero and says so on stderr when pfctl rejects the load, so
# callers can leave their state flag alone and retry on the next
# pass instead of believing a state that is not on the machine.
load_rules() {
    if ! sudo pfctl -f "$RULES_FILE"; then
        echo "Error: pfctl failed to load the ruleset in $RULES_FILE." >&2
        return 1
    fi
}

# Function to allow VPN traffic: block everything, then pass both
# directions on the VPN interface, in one load. The block line is
# the baseline the old two-load version never actually held.
allow_vpn_traffic() {
    printf 'block all\npass in on %s all\npass out on %s all\n' "$1" "$1" > "$RULES_FILE"
    if ! load_rules; then
        echo "Error: allow rules not loaded. Traffic state is unchanged." >&2
        return 1
    fi
    echo "VPN is connected on $1. Allowing traffic."
}

# Function to block all traffic
block_all_traffic() {
    echo "block all" > "$RULES_FILE"
    if ! load_rules; then
        echo "Error: block rules not loaded. Traffic state is unchanged." >&2
        return 1
    fi
    echo "VPN is disconnected. Enforcing killswitch."
}

# Cleanup on termination: flush the PF rules and disable PF, so the
# machine is not left blocked (or passed) by the last loaded ruleset.
# A failed flush or disable is reported as failed. The old version
# sent pfctl stderr to /dev/null and printed the restored message
# either way, which is the same false success problem the allow
# path had.
cleanup() {
    echo "Disabling kill switch..."
    local failed=0
    if ! sudo pfctl -F all; then
        echo "Error: pfctl failed to flush the rules." >&2
        failed=1
    fi
    if ! sudo pfctl -d; then
        echo "Error: pfctl failed to disable PF." >&2
        failed=1
    fi
    rm -f "$RULES_FILE"
    if [ "$failed" -eq 0 ]; then
        echo "Kill switch disabled. Internet access restored."
    else
        echo "Kill switch cleanup incomplete. Check pf state with: sudo pfctl -sr" >&2
    fi
    exit 0
}
trap cleanup INT TERM
# INT and TERM are all a trap can cover. A SIGKILL, a power loss, or a
# crash leaves the last ruleset loaded with PF still enabled, and the
# only way back is a reboot or running pfctl by hand.

# An environment supplied name is known right away, so it gets
# validated before pf is touched at all. The check after interface
# selection below covers the detected and fallback names as well.
if [ -n "$VPN_INTERFACE" ] && ! [[ "$VPN_INTERFACE" =~ ^[A-Za-z0-9_.-]+$ ]]; then
    echo "Error: invalid VPN interface name: $VPN_INTERFACE" >&2
    rm -f "$RULES_FILE"
    exit 2
fi

# Enable the firewall. If pf will not enable, nothing after this
# point can be true, so the script stops here instead of printing
# state messages about rules pf never took.
if ! sudo pfctl -E; then
    echo "Error: failed to enable PF. Killswitch is NOT active." >&2
    rm -f "$RULES_FILE"
    exit 1
fi

# Detect WireGuard interface, unless one was set in the environment
# When the environment names an interface I skip detection entirely
# and trust the name. A wrong name does not fail here: it fails at
# the state check below, which treats a missing interface as a down
# VPN and blocks traffic. Safe direction, confusing message.
if [ -n "$VPN_INTERFACE" ]; then
    echo "Using VPN interface from environment: $VPN_INTERFACE"
else
    VPN_INTERFACE=$(detect_wg_interface)
    if [ -n "$VPN_INTERFACE" ]; then
        echo "Detected WireGuard interface: $VPN_INTERFACE"
    else
        VPN_INTERFACE="$DEFAULT_VPN_INTERFACE"
        echo "No WireGuard interface detected. Using fallback: $VPN_INTERFACE"
    fi
fi

# The interface name is interpolated into a ruleset that root
# loads, so its shape gets checked before it is used, whichever
# path chose it. A name carrying a newline could otherwise add pf
# lines of its own. Exit 2 is for bad input, so it reads
# differently from a pfctl failure (exit 1) to anything wrapping
# this script. The MacOS companion repo checks the same pattern.
if ! [[ "$VPN_INTERFACE" =~ ^[A-Za-z0-9_.-]+$ ]]; then
    echo "Error: invalid VPN interface name: $VPN_INTERFACE" >&2
    rm -f "$RULES_FILE"
    exit 2
fi

# Check initial VPN state and set firewall rules accordingly
# Every path through this block must set VPN_WAS_DISCONNECTED. The
# monitor loop below trusts that flag to mean "the rules on the
# machine already match this state", so a path that left it unset
# would make the first loop pass load rules and print messages for
# a change that never happened.
if ifconfig "$VPN_INTERFACE" &> /dev/null; then
    current_mtu=$(ifconfig "$VPN_INTERFACE" | grep -E 'mtu' | awk '{print $NF}')
    if [ "$current_mtu" = "$VPN_MTU" ]; then
        # The flag flips only when the load actually succeeded. A
        # failed allow leaves the flag at disconnected, so the
        # monitor loop retries the load on its next pass.
        if allow_vpn_traffic "$VPN_INTERFACE"; then
            VPN_WAS_DISCONNECTED=false
        else
            VPN_WAS_DISCONNECTED=true
        fi
    else
        if block_all_traffic; then
            VPN_WAS_DISCONNECTED=true
        else
            VPN_WAS_DISCONNECTED=false
        fi
        echo "Initial state: VPN interface $VPN_INTERFACE has incorrect MTU ($current_mtu)."
    fi
else
    if block_all_traffic; then
        VPN_WAS_DISCONNECTED=true
    else
        VPN_WAS_DISCONNECTED=false
    fi
    echo "Initial state: VPN interface $VPN_INTERFACE is down."
fi

# Monitor the VPN connection status
# The guards on VPN_WAS_DISCONNECTED inside this loop are the point
# of the flag: rules load and messages print only when the state
# flips. My earlier version printed on every pass and produced 90
# lines in 1 second while the MTU was wrong.
while true; do
    if ifconfig "$VPN_INTERFACE" &> /dev/null; then
        # VPN interface exists, verify MTU
        current_mtu=$(ifconfig "$VPN_INTERFACE" | grep -E 'mtu' | awk '{print $NF}')
        if [ "$current_mtu" = "$VPN_MTU" ]; then
            if [ "$VPN_WAS_DISCONNECTED" = true ]; then
                # VPN reconnected, allow traffic. The flag flips
                # only on a successful load, so a pfctl failure is
                # retried on the next pass instead of believed.
                if allow_vpn_traffic "$VPN_INTERFACE"; then
                    VPN_WAS_DISCONNECTED=false
                fi
            fi
            # Removed echo to reduce output spam
        else
            if [ "$VPN_WAS_DISCONNECTED" = false ]; then
                if block_all_traffic; then
                    VPN_WAS_DISCONNECTED=true
                fi
                echo "VPN interface $VPN_INTERFACE has incorrect MTU ($current_mtu)."
            fi
        fi
    else
        # VPN interface doesn't exist
        if [ "$VPN_WAS_DISCONNECTED" = false ]; then
            if block_all_traffic; then
                VPN_WAS_DISCONNECTED=true
            fi
            echo "VPN interface $VPN_INTERFACE is down."
        fi
    fi
    # This sleep is at the end, after the checks, so the first pass
    # after a state change acts right away and the wait only spaces
    # out the steady state polling.
    sleep "$CHECK_INTERVAL"
done
