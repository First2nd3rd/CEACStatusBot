#!/bin/bash
# Install the visacheck launchd jobs (poll + nightly summary) for the current user.
# Plists are generated from the *.plist.template files so no machine-specific
# absolute path is ever committed.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$DIR/.." && pwd)"
LA="$HOME/Library/LaunchAgents"
UID_NUM="$(id -u)"

mkdir -p "$LA" "$REPO/logs"

for label in com.visacheck.poll com.visacheck.summary; do
    sed "s#__REPO__#${REPO}#g" "$DIR/${label}.plist.template" > "$DIR/${label}.plist"
    cp "$DIR/${label}.plist" "$LA/${label}.plist"
    # Modern launchd verbs; do not abort the loop if one label fails.
    launchctl bootout "gui/${UID_NUM}/${label}" 2>/dev/null
    if launchctl bootstrap "gui/${UID_NUM}" "$LA/${label}.plist" 2>/dev/null; then
        launchctl enable "gui/${UID_NUM}/${label}" 2>/dev/null
        echo "Loaded ${label}"
    else
        echo "WARN: could not load ${label}. Try manually:"
        echo "  launchctl bootstrap gui/${UID_NUM} \"$LA/${label}.plist\""
    fi
done

echo "--- active visacheck jobs (launchctl list) ---"
launchctl list | grep visacheck || echo "(none found — check warnings above)"
