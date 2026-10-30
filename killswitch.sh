#!/bin/bash

# Default VPN interface (fallback if detection fails). Set the
# VPN_INTERFACE environment variable to skip detection and use a
# specific interface instead.
DEFAULT_VPN_INTERFACE="utun4"

# VPN characteristics. The listen port can be overridden with the
# WIREGUARD_PORT environment variable.
VPN_MTU=1280
VPN_LISTEN_PORT="${WIREGUARD_PORT:-51820}"

# Seconds to wait between connection checks in the monitor loop
CHECK_INTERVAL=2

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

# Function to allow VPN traffic
allow_vpn_traffic() {
    echo "pass out on $1 all" | sudo pfctl -f - 2>/dev/null
    echo "pass in on $1 all" | sudo pfctl -f - 2>/dev/null
    echo "VPN is connected on $1. Allowing traffic."
}

# Function to block all traffic
block_all_traffic() {
    echo "block all" | sudo pfctl -f - 2>/dev/null
    echo "VPN is disconnected. Enforcing killswitch."
}

# Cleanup on termination: flush the PF rules and disable PF, so the
# machine is not left blocked (or passed) by the last loaded ruleset
cleanup() {
    echo "Disabling kill switch..."
    sudo pfctl -F all 2>/dev/null
    sudo pfctl -d 2>/dev/null
    echo "Kill switch disabled. Internet access restored."
    exit 0
}
trap cleanup INT TERM

# Enable the firewall
sudo pfctl -E

# Detect WireGuard interface, unless one was set in the environment
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

# Check initial VPN state and set firewall rules accordingly
if ifconfig "$VPN_INTERFACE" &> /dev/null; then
    current_mtu=$(ifconfig "$VPN_INTERFACE" | grep -E 'mtu' | awk '{print $NF}')
    if [ "$current_mtu" = "$VPN_MTU" ]; then
        allow_vpn_traffic "$VPN_INTERFACE"
        VPN_WAS_DISCONNECTED=false
    else
        block_all_traffic
        VPN_WAS_DISCONNECTED=true
        echo "Initial state: VPN interface $VPN_INTERFACE has incorrect MTU ($current_mtu)."
    fi
else
    block_all_traffic
    VPN_WAS_DISCONNECTED=true
    echo "Initial state: VPN interface $VPN_INTERFACE is down."
fi

# Monitor the VPN connection status
while true; do
    if ifconfig "$VPN_INTERFACE" &> /dev/null; then
        # VPN interface exists, verify MTU
        current_mtu=$(ifconfig "$VPN_INTERFACE" | grep -E 'mtu' | awk '{print $NF}')
        if [ "$current_mtu" = "$VPN_MTU" ]; then
            if [ "$VPN_WAS_DISCONNECTED" = true ]; then
                # VPN reconnected, allow traffic
                allow_vpn_traffic "$VPN_INTERFACE"
                VPN_WAS_DISCONNECTED=false
            fi
            # Removed echo to reduce output spam
        else
            if [ "$VPN_WAS_DISCONNECTED" = false ]; then
                block_all_traffic
                VPN_WAS_DISCONNECTED=true
                echo "VPN interface $VPN_INTERFACE has incorrect MTU ($current_mtu)."
            fi
        fi
    else
        # VPN interface doesn't exist
        if [ "$VPN_WAS_DISCONNECTED" = false ]; then
            block_all_traffic
            VPN_WAS_DISCONNECTED=true
            echo "VPN interface $VPN_INTERFACE is down."
        fi
    fi
    sleep "$CHECK_INTERVAL"
done
