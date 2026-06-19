#!/bin/bash
# Remove the visacheck launchd jobs. Run this to stop all scheduled checks.
LA="$HOME/Library/LaunchAgents"
UID_NUM="$(id -u)"

for label in com.visacheck.poll com.visacheck.summary; do
    launchctl bootout "gui/${UID_NUM}/${label}" 2>/dev/null
    rm -f "$LA/${label}.plist"
    echo "Removed ${label}"
done

echo "Remaining visacheck jobs:"
launchctl list | grep visacheck || echo "(none — all removed)"
