from __future__ import annotations


# Closing WPS only when no other document is open protects a user's interactive
# session in case the COM server hands out its already-running instance.
QUIT_IF_IDLE = (
    "$wpsIdle = $true; "
    "foreach ($wpsCollection in 'Documents', 'Workbooks', 'Presentations') { "
    "try { $wpsItems = $app.$wpsCollection; "
    "if ($null -ne $wpsItems -and [int]$wpsItems.Count -gt 0) { $wpsIdle = $false } } catch { } }; "
    "if ($wpsIdle) { $app.Quit() }"
)
