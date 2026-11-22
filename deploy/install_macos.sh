#!/bin/bash
# Install (or reinstall) the always-on Smart Vitals service on macOS.
#
#   bash deploy/install_macos.sh [path/to/.env]
#
# What it does:
#   ~/smart-vitals-service/repo   its own clone of the GitHub repository (updates itself from GitHub)
#   ~/smart-vitals-service/venv   its own Python environment
#   ~/smart-vitals-service/logs   service.log, api.log, simulator.log
#   ~/Library/LaunchAgents/com.smartvitals.ipms.plist
#       tells macOS to start deploy/supervisor.py at login and restart it if it stops.
# It lives outside the Desktop on purpose: the Desktop is synced by iCloud, and macOS does not
# let background services read the Desktop.
#
# Stop for now:   launchctl bootout gui/$(id -u)/com.smartvitals.ipms
# Start again:    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.smartvitals.ipms.plist
# Uninstall:      the bootout line above, then delete the .plist and ~/smart-vitals-service
set -euo pipefail

REPO_URL="https://github.com/AlessioAka/smart-vitals-ipms.git"
LABEL="com.smartvitals.ipms"
SERVICE="$HOME/smart-vitals-service"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
PYTHON="${PYTHON:-$(command -v python3.14 || command -v python3.13 || command -v python3.12)}"
ENV_FILE="${1:-}"

echo "Service folder: $SERVICE   Python: $PYTHON"
mkdir -p "$SERVICE/logs" "$HOME/Library/LaunchAgents"

# 1. The code: a clone of GitHub (pull if it is already there).
if [ -d "$SERVICE/repo/.git" ]; then
    git -C "$SERVICE/repo" pull --ff-only --quiet
else
    git clone --quiet "$REPO_URL" "$SERVICE/repo"
fi

# 2. Settings: .env is never in git, so copy the one given (or start from the example).
if [ -n "$ENV_FILE" ]; then
    cp "$ENV_FILE" "$SERVICE/repo/.env"
elif [ ! -f "$SERVICE/repo/.env" ]; then
    cp "$SERVICE/repo/.env.example" "$SERVICE/repo/.env"
fi
chmod 600 "$SERVICE/repo/.env"

# 3. Python environment with the pinned requirements.
[ -x "$SERVICE/venv/bin/python" ] || "$PYTHON" -m venv "$SERVICE/venv"
"$SERVICE/venv/bin/python" -m pip install --quiet --upgrade pip
"$SERVICE/venv/bin/python" -m pip install --quiet -r "$SERVICE/repo/requirements.txt"

# 4. Tell macOS to run the supervisor at login and keep it alive.
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$SERVICE/venv/bin/python</string>
        <string>-u</string>
        <string>$SERVICE/repo/deploy/supervisor.py</string>
    </array>
    <key>WorkingDirectory</key><string>$SERVICE/repo</string>
    <key>RunAtLoad</key><true/>
    <key>KeepAlive</key><true/>
    <key>ThrottleInterval</key><integer>10</integer>
    <key>EnvironmentVariables</key>
    <dict><key>PATH</key><string>/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin</string></dict>
    <key>StandardOutPath</key><string>$SERVICE/logs/service.log</string>
    <key>StandardErrorPath</key><string>$SERVICE/logs/service.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed. Dashboard: http://127.0.0.1:8000/dashboard/login   Logs: $SERVICE/logs"
