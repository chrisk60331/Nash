#!/usr/bin/env bash
# Opens the Nash dashboard as a new window in the current tmux session
SESSION="$(tmux display-message -p '#S')"
WINDOW="nash"

PANE_TL=$(tmux new-window -a -n "$WINDOW" -P -F "#{pane_id}")
PANE_TR=$(tmux split-window  -h -t "$PANE_TL"           -P -F "#{pane_id}")
PANE_BL=$(tmux split-window  -v -t "$PANE_TL"           -P -F "#{pane_id}")
PANE_BR=$(tmux split-window  -v -t "$PANE_TR"           -P -F "#{pane_id}")
# Send commands
tmux send-keys -t "$PANE_TL" "./scripts/tail-aws-logs.sh" Enter
tmux send-keys -t "$PANE_BL" "watch -n 60 bash scripts/recent-user-stats.sh" Enter
tmux send-keys -t "$PANE_TR" "BASE_URL=https://nash.backboard.io ./scripts/nash-watchdog.sh" Enter
tmux send-keys -t "$PANE_BR" "watch -n 60 SIGNUP_DAYS=100 scripts/nash-health-summary.sh dev" Enter


tmux select-pane -t "$SESSION:$WINDOW.0"