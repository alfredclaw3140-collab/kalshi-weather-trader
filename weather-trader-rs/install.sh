#!/bin/bash
# Install Weather Trading Bot as a service

echo "Installing Weather Trading Bot..."

# Build release binary
cargo build --release

# Copy binary to /usr/local/bin
sudo cp target/release/weather-trader /usr/local/bin/

# Create config directory
mkdir -p ~/.config/weather-trader

# Install systemd service (on Linux)
if command -v systemctl &> /dev/null; then
    sudo cp weather-trader.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable weather-trader
    echo "Service installed. Run: sudo systemctl start weather-trader"
fi

# Create launchd plist for macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    cat > ~/Library/LaunchAgents/com.weather-trader.bot.plist << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.weather-trader.bot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/alfred/.openclaw/workspace/weather-trader-rs/target/release/weather-trader</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/weather-trader.out</string>
    <key>StandardErrorPath</key>
    <string>/tmp/weather-trader.err</string>
</dict>
</plist>
PLIST
    launchctl load ~/Library/LaunchAgents/com.weather-trader.bot.plist
    echo "LaunchAgent installed for macOS"
fi

echo "Installation complete!"
echo "Dashboard: http://localhost:8080"
