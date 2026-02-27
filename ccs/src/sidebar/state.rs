// ── State detection for Claude session windows ──

use std::collections::HashMap;

use crate::tmux;

// ── Types ──

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WindowState {
    /// New session, no activity detected yet.
    Fresh,
    /// Claude is generating output (pane content changed).
    Working,
    /// Claude is idle — waiting for input (content stopped changing, but has worked before).
    Idle,
    /// Claude process exited — shell prompt visible.
    Done,
}

struct WindowTracker {
    prev_capture: String,
    ever_worked: bool,
}

pub struct StateDetector {
    trackers: HashMap<u32, WindowTracker>,
}

// ── Public API ──

impl StateDetector {
    pub fn new() -> Self {
        Self {
            trackers: HashMap::new(),
        }
    }

    /// Detect the state of each window. Returns a map from window_index to state.
    pub fn detect(&mut self, windows: &[tmux::WindowInfo]) -> HashMap<u32, WindowState> {
        let mut states = HashMap::new();

        // Get foreground commands for all panes in one tmux call
        let pane_cmds: HashMap<u32, String> = tmux::list_pane_commands()
            .unwrap_or_default()
            .into_iter()
            .map(|p| (p.window_index, p.command))
            .collect();

        for win in windows {
            let cmd = pane_cmds
                .get(&win.index)
                .map(String::as_str)
                .unwrap_or("zsh");

            // Shell prompt means Claude exited
            if cmd == "zsh" || cmd == "bash" || cmd == "fish" {
                states.insert(win.index, WindowState::Done);
                continue;
            }

            // Claude is running — detect activity via content change
            let capture = tmux::capture_pane(win.index, 3)
                .unwrap_or_default()
                .chars()
                .filter(|c| !c.is_whitespace())
                .collect::<String>();

            let tracker = self
                .trackers
                .entry(win.index)
                .or_insert_with(|| WindowTracker {
                    prev_capture: String::new(),
                    ever_worked: false,
                });

            let state = if capture != tracker.prev_capture {
                tracker.ever_worked = true;
                WindowState::Working
            } else if tracker.ever_worked {
                WindowState::Idle
            } else {
                WindowState::Fresh
            };

            tracker.prev_capture = capture;
            states.insert(win.index, state);
        }

        // Prune trackers for windows that no longer exist
        let live_indices: std::collections::HashSet<u32> =
            windows.iter().map(|w| w.index).collect();
        self.trackers.retain(|idx, _| live_indices.contains(idx));

        states
    }
}
