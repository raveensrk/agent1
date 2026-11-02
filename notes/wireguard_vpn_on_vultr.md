# How to set up wireguard vpn in vultr instance.

This guide sets up a personal WireGuard VPN on a Vultr instance, then connects
both iOS and macOS clients.

It intentionally uses placeholders for sensitive values. Do not paste private
keys, full configs, or personal server IPs into public chats or documents.

## What This Setup Does

- Uses a Vultr server as a personal VPN exit node.
- Runs WireGuard on UDP port `51820`.
- Routes client internet traffic through the Vultr public IP.
- Creates separate WireGuard clients for iOS and macOS.
- Keeps SSH available for server management.

## Placeholders Used

Replace these placeholders with your own values:

```text
<SERVER_PUBLIC_IPV4>     Your real Vultr public IPv4
<PUBLIC_INTERFACE>       Your server's outbound network interface
<YOUR_HOME_PUBLIC_IP>    Your current home/office public IP for SSH lockdown
```

Do not use private keys as placeholders in notes. They should stay only on the
server and inside the WireGuard client app.

## 1. Confirm You Have a Real Public IPv4

If SSH times out like this:

```bash
ssh root@<server-ip>
ssh: connect to host <server-ip> port 22: Operation timed out
```

first confirm that the IP is actually public.

Vultr may show an address in the `100.64.0.0/10` range. Addresses in that range
are shared/CGNAT-style addresses and are not normally reachable directly from
the public internet.

Use the instance's real public IPv4 from the Vultr instance overview or IPv4
settings page:

```bash
ssh root@<SERVER_PUBLIC_IPV4>
```

If the server only has a non-routable-looking IPv4, upgrade or attach a real
public IPv4 / reserved IPv4 in Vultr.

IPv6 can also work, if both your local internet connection and Vultr firewall
allow it:

```bash
ssh -6 root@<SERVER_IPV6>
```

For a simpler personal VPN setup, a real public IPv4 is usually easiest.

## 2. Configure Vultr Firewall Group

In Vultr, `Firewall Groups` are the cloud firewall.

If your instance says `No Firewall` under instance settings, then no Vultr cloud
firewall is attached yet.

Create or open a firewall group:

```text
Products -> Network -> Firewall Groups
```

Add these inbound IPv4 rules:

```text
Protocol / Preset    Port      Source
SSH                  22        0.0.0.0/0 initially, or your IP for stricter SSH
UDP                  51820     0.0.0.0/0
```

Notes:

- Vultr's `SSH` preset is TCP port `22`.
- You do not need a separate TCP `22` rule if `SSH` already exists.
- If Vultr says `This rule is already defined`, the rule already exists.
- Keep UDP `51820` open to `0.0.0.0/0` because phones and laptops roam between
  networks.
- Rule changes may take up to about 120 seconds to propagate.

Attach the firewall group to the instance:

```text
Instance -> Settings -> Firewall -> select firewall group
```

or:

```text
Firewall Group -> Linked Instances -> add instance
```

## 3. Install WireGuard on the Server

SSH into the Vultr server:

```bash
ssh root@<SERVER_PUBLIC_IPV4>
```

Install WireGuard, QR tooling, and `tcpdump` for troubleshooting:

```bash
apt update
apt install -y wireguard qrencode tcpdump
```

## 4. Enable IP Forwarding

WireGuard clients need the server to forward traffic.

```bash
cat > /etc/sysctl.d/99-wireguard.conf <<'EOF'
net.ipv4.ip_forward=1
net.ipv6.conf.all.forwarding=1
EOF

sysctl --system
```

Verify IPv4 forwarding:

```bash
sysctl net.ipv4.ip_forward
```

Expected:

```text
net.ipv4.ip_forward = 1
```

## 5. Generate Server Keys

```bash
mkdir -p /etc/wireguard
cd /etc/wireguard
umask 077

wg genkey | tee server_private.key | wg pubkey > server_public.key
```

The private key must remain private.

## 6. Find the Server's Public Network Interface

Run:

```bash
ip route get 8.8.8.8 | awk '{print $5; exit}'
```

It prints the outbound public interface, such as:

```text
eth0
ens3
enp1s0
```

Use that value wherever this guide says `<PUBLIC_INTERFACE>`.

## 7. Create the WireGuard Server Config

Create `/etc/wireguard/wg0.conf`:

```bash
cd /etc/wireguard
SERVER_PRIVATE_KEY="$(cat /etc/wireguard/server_private.key)"

cat > /etc/wireguard/wg0.conf <<EOF
[Interface]
Address = 10.8.0.1/24
ListenPort = 51820
PrivateKey = $SERVER_PRIVATE_KEY
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -A FORWARD -o wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o <PUBLIC_INTERFACE> -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -D FORWARD -o wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o <PUBLIC_INTERFACE> -j MASQUERADE
EOF

chmod 600 /etc/wireguard/wg0.conf
```

Important: replace `<PUBLIC_INTERFACE>` with the interface discovered earlier.

Example shape only:

```ini
PostUp = iptables ... -o enp1s0 -j MASQUERADE
PostDown = iptables ... -o enp1s0 -j MASQUERADE
```

## 8. Start WireGuard

```bash
systemctl enable --now wg-quick@wg0
wg show
```

You should see:

```text
interface: wg0
listening port: 51820
```

Confirm the server is listening:

```bash
ss -lunp | grep 51820
```

Expected shape:

```text
0.0.0.0:51820
[::]:51820
```

## 9. Create an iOS Client

Create a separate client keypair for the phone:

```bash
cd /etc/wireguard
umask 077

wg genkey | tee ios_private.key | wg pubkey > ios_public.key
```

Add the phone as a peer on the server:

```bash
cat >> /etc/wireguard/wg0.conf <<EOF

[Peer]
PublicKey = $(cat ios_public.key)
AllowedIPs = 10.8.0.2/32
EOF

systemctl restart wg-quick@wg0
```

Create the iOS client config:

```bash
cat > /etc/wireguard/ios.conf <<EOF
[Interface]
PrivateKey = $(cat ios_private.key)
Address = 10.8.0.2/32
DNS = 1.1.1.1

[Peer]
PublicKey = $(cat server_public.key)
Endpoint = <SERVER_PUBLIC_IPV4>:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF

chmod 600 /etc/wireguard/ios.conf
```

Generate a QR code:

```bash
qrencode -t ansiutf8 < /etc/wireguard/ios.conf
```

On iOS:

1. Install the WireGuard app.
2. Tap `+`.
3. Choose `Create from QR code`.
4. Scan the QR code.
5. Turn on the tunnel.

Test by visiting:

```text
https://ifconfig.me
```

It should show the Vultr server public IPv4.

## 10. Create a macOS Client

Create a separate client for macOS. Do not reuse the iOS config, because both
devices would compete for the same WireGuard client IP.

On the server:

```bash
cd /etc/wireguard
umask 077

wg genkey | tee macos_private.key | wg pubkey > macos_public.key
```

Add the Mac as a peer:

```bash
cat >> /etc/wireguard/wg0.conf <<EOF

[Peer]
PublicKey = $(cat macos_public.key)
AllowedIPs = 10.8.0.3/32
EOF

systemctl restart wg-quick@wg0
```

Create the macOS client config:

```bash
cat > /etc/wireguard/macos.conf <<EOF
[Interface]
PrivateKey = $(cat macos_private.key)
Address = 10.8.0.3/32
DNS = 1.1.1.1

[Peer]
PublicKey = $(cat server_public.key)
Endpoint = <SERVER_PUBLIC_IPV4>:51820
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
EOF

chmod 600 /etc/wireguard/macos.conf
```

Download WireGuard for macOS from the official install page:

```text
https://www.wireguard.com/install/
```

Copy the config to the Mac:

```bash
scp root@<SERVER_PUBLIC_IPV4>:/etc/wireguard/macos.conf ~/Downloads/macos.conf
```

In the macOS WireGuard app:

1. Choose `Import tunnel(s) from file`.
2. Select `~/Downloads/macos.conf`.
3. Activate the tunnel.

Test from macOS:

```bash
curl https://ifconfig.me
```

It should show the Vultr server public IPv4.

## 11. Troubleshooting: No Handshake

On the server, run:

```bash
wg show
```

If the client is connected successfully, the peer shows something like:

```text
latest handshake: ...
transfer: ... received, ... sent
```

If there is no `latest handshake`, check these:

1. The client `Endpoint` must be:

```ini
Endpoint = <SERVER_PUBLIC_IPV4>:51820
```

2. The client `[Peer] PublicKey` must match the server public key:

```bash
cat /etc/wireguard/server_public.key
```

3. The server `[Peer] PublicKey` must match the client public key:

```bash
cat /etc/wireguard/ios_public.key
cat /etc/wireguard/macos_public.key
```

4. Vultr firewall must allow:

```text
UDP 51820 from 0.0.0.0/0
```

5. The server OS firewall must allow WireGuard:

```bash
ufw allow 51820/udp
ufw reload
```

6. Confirm the server is listening:

```bash
ss -lunp | grep 51820
```

7. Use tcpdump to see whether packets arrive:

```bash
tcpdump -ni <PUBLIC_INTERFACE> udp port 51820
```

Then toggle WireGuard off/on on the client.

Interpretation:

- If `tcpdump` shows no packets, the client is not reaching the server. Check
  endpoint IP, Vultr firewall, local network, or mobile network.
- If `tcpdump` shows packets but `wg show` still has no handshake, the keys or
  peer config probably do not match, the client may still be using an old
  tunnel, or the server firewall/reloaded service state may be stale.

When packets arrive but there is still no handshake, check the loaded peer and
restart WireGuard after any peer or firewall changes:

```bash
wg show
grep -A2 -B1 '10.8.0.2/32' /etc/wireguard/wg0.conf
systemctl restart wg-quick@wg0
```

Then delete the old tunnel from the iOS/macOS WireGuard app, scan or import the
current config again, and toggle the tunnel off/on.

For iOS, the tunnel's `Interface` public key in the app must match:

```bash
cat /etc/wireguard/ios_public.key
```

The iOS `[Peer] PublicKey` must match:

```bash
cat /etc/wireguard/server_public.key
```

Also check the host firewall if packets arrive but no handshake appears:

```bash
ufw status verbose
iptables -S INPUT
```

If UFW is active, explicitly allow WireGuard and restart:

```bash
ufw allow 51820/udp
ufw reload
systemctl restart wg-quick@wg0
```

## 12. Troubleshooting: Handshake Works but Websites Do Not Load

If `wg show` has a recent handshake but websites fail, check forwarding, NAT,
DNS, and UFW route permissions.

Server checks:

```bash
sysctl net.ipv4.ip_forward
iptables -t nat -S
ufw status verbose
```

If UFW is enabled, allow routed traffic:

```bash
ufw route allow in on wg0 out on <PUBLIC_INTERFACE>
ufw reload
systemctl restart wg-quick@wg0
```

Reconnect the WireGuard client.

If IP addresses work but domain names do not, it may be DNS. The client config
uses:

```ini
DNS = 1.1.1.1
```

You can also test:

```text
https://1.1.1.1
https://ifconfig.me
```

## 13. Lock Down SSH After VPN Works

Once WireGuard works, tighten SSH access in the Vultr firewall.

On the Mac, find your current public IP:

```bash
curl https://ifconfig.me
```

In Vultr Firewall Group:

1. Keep:

```text
UDP 51820 from 0.0.0.0/0
```

2. Add a stricter SSH rule:

```text
SSH / TCP 22 from <YOUR_HOME_PUBLIC_IP>/32
```

3. Open a new terminal and verify SSH still works:

```bash
ssh root@<SERVER_PUBLIC_IPV4>
```

4. Only after confirming SSH works, delete the broad SSH rule:

```text
SSH / TCP 22 from 0.0.0.0/0
```

## 14. Optional: Use UFW on the Server

If UFW is inactive and you want host-level firewall protection:

```bash
ufw allow OpenSSH
ufw allow 51820/udp
ufw route allow in on wg0 out on <PUBLIC_INTERFACE>
ufw enable
```

Check:

```bash
ufw status verbose
```

Do this carefully so you do not lock yourself out of SSH.

## 15. Back Up Configs Safely

WireGuard configs contain private keys, so treat them like passwords.

Example backup location on macOS:

```bash
mkdir -p ~/Documents/wireguard-backup
scp root@<SERVER_PUBLIC_IPV4>:/etc/wireguard/wg0.conf ~/Documents/wireguard-backup/
scp root@<SERVER_PUBLIC_IPV4>:/etc/wireguard/ios.conf ~/Documents/wireguard-backup/
scp root@<SERVER_PUBLIC_IPV4>:/etc/wireguard/macos.conf ~/Documents/wireguard-backup/
```

Keep that folder private.

## 16. Add Another Device Later

For every new device:

1. Generate a new keypair.
2. Add a new `[Peer]` block to `/etc/wireguard/wg0.conf`.
3. Give the device a unique VPN IP.
4. Create a separate client config.

Example device IPs:

```text
Server: 10.8.0.1/24
iOS:    10.8.0.2/24
macOS:  10.8.0.3/24
Next:   10.8.0.4/24
```

Server peer entries should use `/32`:

```ini
AllowedIPs = 10.8.0.4/32
```

Client interface entries can use `/24`:

```ini
Address = 10.8.0.4/24
```

## 17. Quick Verification Checklist

Server:

```bash
systemctl status wg-quick@wg0
wg show
ss -lunp | grep 51820
sysctl net.ipv4.ip_forward
iptables -t nat -S
```

Vultr firewall:

```text
SSH / TCP 22 allowed from your IP
UDP 51820 allowed from 0.0.0.0/0
Firewall group linked to the instance
```

Client:

```text
Endpoint uses the real Vultr public IPv4
Server public key is correct
Each device has a unique client key and unique 10.8.0.x address
Tunnel shows latest handshake
https://ifconfig.me shows the Vultr public IPv4
```
