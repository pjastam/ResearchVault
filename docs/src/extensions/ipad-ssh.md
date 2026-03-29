# Step 16: iPad access via SSH terminal

Phase 0 and Phase 1 of the workflow run naturally on an iPad — the HTML reader at `http://localhost:8765/filtered.html` is accessible from any browser on your local network, and adding items to Zotero works via the iOS app. Phase 2 and Phase 3 require Claude Code, which runs on the Mac mini. The most practical way to run these phases from an iPad is via SSH: you connect to the Mac mini over the network and run Claude Code in a terminal session, with full access to all local tools (Zotero MCP, Ollama, whisper.cpp, yt-dlp).

## 16a. Enable SSH on the Mac mini

1. Open **System Settings → General → Sharing**
2. Enable **Remote Login**
3. Enable "Allow full disk access for remote users" **on** — macOS protects folders like Documents and Desktop via TCC (privacy framework), which blocks SSH access even for your own account unless this option is enabled

## 16b. Install a terminal app on your iPad

**Recommended:** [Termius](https://apps.apple.com/app/termius-ssh-sftp-client/id549039908) (free tier is sufficient for a single SSH connection)

**Alternative:** Blink Shell (one-time purchase, slightly more powerful but not necessary)

No account is required in Termius for basic use. The built-in sync and AI features are not needed for this workflow — skip account creation when prompted.

## 16c. Set up the connection in Termius (home network)

1. Open Termius → tap **+** → **New Host**
2. Fill in the following fields:

   | Field | Value |
   | --- | --- |
   | Label | `Mac Mini` (or any name you like) |
   | Hostname | the local IP address of your Mac mini (see below) |
   | Port | `22` |
   | Username | your macOS account name |
   | Password | your Mac login password |

3. Tap **Save**, then tap the host to connect
4. Termius stores the host key silently on first connection — no manual confirmation needed

**Finding your Mac mini's local IP address:**

Run the following in Terminal on the Mac mini:

```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

The address shown (e.g. `192.168.178.x`) is your local IP. For a stable address, assign a fixed IP to the Mac mini's MAC address in your router's DHCP settings — this prevents the address from changing after a restart.

**Verifying the host key fingerprint:**

To verify that Termius stored the correct key, run the following on the Mac mini:

```bash
for f in /etc/ssh/ssh_host_*_key.pub; do ssh-keygen -lf "$f"; done
```

This lists the fingerprints for all three host key types (ECDSA, ED25519, RSA). In Termius, check **Edit host → Known Host** and confirm that the stored fingerprint matches one of these — the ED25519 fingerprint is the most commonly used in modern connections.

## 16d. Set up SSH key authentication (recommended)

Entering a password every session is inconvenient. An SSH key pair allows passwordless login.

**In Termius:**

1. Go to **Settings → Keychain → +** → **Generate key**
2. Choose Ed25519, give it a name, tap **Generate**
3. Tap the key → **Export public key** → copy the text to your clipboard

**On the Mac mini**, paste the public key into your `authorized_keys` file:

```bash
echo "PASTE_YOUR_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

**Back in Termius**, edit the host and set the **Key** field to the key you just created. From now on, the connection opens without a password prompt.

## 16e. Ensure required services are running on the Mac mini

Before starting Claude Code, two background services must be running on the Mac mini:

**Zotero** — Claude Code communicates with Zotero via its local API on port 23119. If Zotero is not open, all MCP calls will fail.

To start Zotero automatically at login, open System Settings on the Mac mini, go to **General → Login Items**, click the **+** button, and select Zotero from your Applications folder. After this one-time setup, Zotero will always be running when the Mac mini is on.

If Zotero is not running for any reason, you can start it from the SSH session itself (this works as long as the Mac mini has an active logged-in user session):

```bash
open -a Zotero
```

**Ollama** — required for local model generation. Ollama starts automatically as a background service after installation, so no action is normally needed. If it is not running:

```bash
open -a Ollama
```

**Obsidian** does not need to be running. Claude Code writes Markdown files directly to the vault on the filesystem — Obsidian picks up the changes the next time you open it.

## 16f. Run Claude Code via SSH

Once connected, navigate to the vault and start Claude Code:

```bash
cd ~/Documents/ResearchVault
claude
```

You are now in exactly the same environment as when using Claude Code on the Mac mini directly — including Zotero MCP, Ollama, whisper.cpp, and all workflow skills. Type `/research` to start the research workflow.

**First-time login:** The Claude Code CLI stores its credentials separately from the desktop or VS Code login. The first time you run `claude` via SSH it will tell you that you are not logged in and ask you to run `/login`. Do the following:

1. Type `/login` inside Claude Code
2. Claude Code displays a URL
3. Open that URL in Safari on your iPad
4. Sign in with your Claude account
5. After confirmation the token is saved to `~/.claude/` on the Mac mini — you will not be asked again

**One-step shortcut:** Add the following alias to `~/.zshrc` on the Mac mini so you can launch Claude Code in the vault with a single command:

```bash
alias rv='cd ~/Documents/ResearchVault && claude "start research workflow"'
```

Activate it once with `source ~/.zshrc`, then from any SSH session just type `rv`.

A keyboard (Smart Keyboard, Magic Keyboard, or similar) makes this experience comfortable on an iPad.

## 16g. Outside your home network — Tailscale

The setup above works on your local network. To also run Phase 2 and Phase 3 from outside your home (e.g. on the road with an iPad and cellular), you need a way to reach the Mac mini securely over the internet. **Tailscale** is the simplest option: it creates an encrypted peer-to-peer network between your devices without requiring port forwarding or a VPN server.

**Installation takes about 10 minutes:**

1. Download [Tailscale](https://tailscale.com/download) on the Mac mini and install it
2. Download the Tailscale app on your iPad from the App Store
3. Sign in to the same account (Google, GitHub, or email) on both devices
4. Both devices now appear in your Tailscale network with stable `100.x.x.x` addresses
5. In Termius, create a second host entry using the Tailscale IP of your Mac mini (visible in the Tailscale app on either device) as the hostname

From that point on, the SSH connection works identically whether you are at home or anywhere else — no port forwarding needed, no firewall rules required. Tailscale's free tier supports up to 100 devices, which is more than sufficient for personal use.
