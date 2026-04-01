# Step 17: In-browser terminal — Phase 1 and Phase 2 in one tab

By default, feedreader (reading the filtered feed) happens in the browser, and Phase 2 (running Claude Code) happens in a separate terminal window. This step embeds a fully interactive terminal directly into the feedreader HTML reader, so both phases run in the same browser tab — on Mac, iPad, or any other device on your local network.

## How it works

VS Code embeds a terminal in the browser using **xterm.js** (a terminal renderer) connected to **node-pty** (a pseudo-terminal backend) over a WebSocket. The same architecture is available as a standalone tool: **ttyd**.

ttyd runs a local HTTP server that serves an xterm.js terminal connected to a shell on your Mac mini. The feedreader HTML reader embeds this terminal as an iframe. Clicking the **⌨️ terminal** button in the header reveals the terminal panel alongside your article list.

The iframe URL is derived dynamically from `window.location.hostname`, so the terminal works whether you access the page from the Mac mini itself (`localhost`) or from an iPad on the local network (via the Mac's IP address).

## 17a. Install ttyd

```bash
brew install ttyd
```

## 17b. Load the launchd agent

A launchd agent starts ttyd automatically at login and keeps it running:

```bash
launchctl load ~/Library/LaunchAgents/nl.researchvault.ttyd.plist
```

This agent starts ttyd on port 7681 with the `--writable` flag enabled, which is required for interactive use. Without `--writable`, the terminal renders but ignores all keyboard input.

To verify it is running:

```bash
launchctl list | grep ttyd
```

A PID (number) in the first column confirms it is active. Log output is written to `/tmp/ttyd.log`.

## 17c. Use the terminal in the HTML reader

1. Open `http://localhost:8765/filtered.html` (Mac) or `http://[mac-ip]:8765/filtered.html` (iPad)
2. Click **⌨️ terminal** in the header bar
3. A terminal panel opens on the right (side-by-side on desktop, stacked below on narrow screens)
4. The terminal is a full interactive shell — navigate to the vault and start Claude Code:

```bash
cd ~/Documents/ResearchVault
claude
```

Type `/research` to start the research workflow skill. You can now read feedreader items on the left and run Phase 2 in the terminal on the right, without switching tabs or apps.

The terminal panel is lazy-loaded: ttyd is only contacted when you first open the panel. If you never click the button, nothing changes in performance or behaviour.

## 17d. Optional: persistent sessions with tmux

By default, each time you open the terminal panel a new shell session starts. If you want to reconnect to an existing Claude Code session after navigating away or closing the panel, install tmux:

```bash
brew install tmux
```

Then unload the current agent, update the plist to use tmux, and reload:

```bash
launchctl unload ~/Library/LaunchAgents/nl.researchvault.ttyd.plist
```

Edit `~/Library/LaunchAgents/nl.researchvault.ttyd.plist` and replace the `ProgramArguments` block with:

```xml
<key>ProgramArguments</key>
<array>
  <string>/bin/sh</string>
  <string>-c</string>
  <string>/opt/homebrew/bin/tmux new-session -d -s phase2 2>/dev/null; exec /opt/homebrew/bin/ttyd --port 7681 --writable /opt/homebrew/bin/tmux attach -t phase2</string>
</array>
```

Then reload:

```bash
launchctl load ~/Library/LaunchAgents/nl.researchvault.ttyd.plist
```

Now every connection to the terminal panel attaches to the same persistent `phase2` session. A Claude Code conversation that was running when you closed the panel will still be there when you reopen it.

## 17e. Security note

ttyd listens on all network interfaces (`0.0.0.0`) by default, which is what makes it reachable from an iPad. This also means any device on your local network can open a terminal on your Mac mini. This is acceptable for a trusted home network — if you use public or shared networks, stop the agent before connecting:

```bash
launchctl unload ~/Library/LaunchAgents/nl.researchvault.ttyd.plist
```
