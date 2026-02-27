// ── State detection for Claude session windows ──

use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::LazyLock;
use std::fs;

use regex::Regex;

use crate::tmux;

// ── Types ──

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WindowState {
    /// New session, no activity detected yet.
    Fresh,
    /// Claude is generating output (pane content changed).
    Working,
    /// Claude is waiting for user to answer a question (yes/no, pick option, allow/deny).
    Asking,
    /// Claude finished answering — waiting for next user message.
    Idle,
    /// Claude process exited — shell prompt visible.
    Done,
}

// ── Question detection ──

static QUESTION_RE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(concat!(
        r"(?im)",
        r"\(Y\)es.*\(N\)o",               // (Y)es/(N)o prompt
        r"|\([yY]/[nN]\)|\[[yY]/[nN]\]",  // (y/n), (Y/n), [y/N], etc.
        r"|\(yes/no\)",                     // (yes/no)
        r"|❯",                              // selection marker (AskUserQuestion)
        r"|Allow.*Deny",                    // permission buttons on same line
    ))
    .expect("question regex is valid")
});

/// Check only the last 2 lines for question patterns (prompts appear at the bottom).
fn detect_question(capture: &str) -> bool {
    let tail: String = capture.lines().rev().take(2).collect::<Vec<_>>().join("\n");
    QUESTION_RE.is_match(&tail)
}

/// Minimum changed lines to count as "significant" (Claude generating, not user typing).
const SIGNIFICANT_LINES: usize = 2;
/// How many consecutive significant-change ticks before we enter Working.
const WORK_ENTER_TICKS: u32 = 2;
/// How many consecutive quiet ticks before we leave Working.
const WORK_EXIT_TICKS: u32 = 5;

struct WindowTracker {
    prev_raw: String,
    change_streak: u32,
    stable_streak: u32,
    ever_worked: bool,
    was_working: bool,
    /// True after Claude finishes a generation turn. Cleared on any content change
    /// (user typing resets it so `(ready)` disappears until Claude responds again).
    turn_complete: bool,
}

// ── Cross-instance state sharing ──

fn state_dir() -> PathBuf {
    PathBuf::from("/tmp/ccs-state")
}

fn mark_worked(window_index: u32) {
    let dir = state_dir();
    fs::create_dir_all(&dir).ok();
    fs::write(dir.join(window_index.to_string()), "").ok();
}

fn check_worked(window_index: u32) -> bool {
    state_dir().join(window_index.to_string()).exists()
}

fn clear_worked(window_index: u32) {
    fs::remove_file(state_dir().join(window_index.to_string())).ok();
}

/// Count how many trimmed lines differ between two captures.
fn changed_line_count(a: &str, b: &str) -> usize {
    let al: Vec<&str> = a.lines().map(str::trim).collect();
    let bl: Vec<&str> = b.lines().map(str::trim).collect();
    let max = al.len().max(bl.len());
    (0..max)
        .filter(|&i| al.get(i) != bl.get(i))
        .count()
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
            let raw_capture = tmux::capture_pane(win.index, 5).unwrap_or_default();

            let tracker = self
                .trackers
                .entry(win.index)
                .or_insert_with(|| {
                    let worked = check_worked(win.index);
                    WindowTracker {
                        prev_raw: raw_capture.clone(),
                        change_streak: 0,
                        stable_streak: 0,
                        ever_worked: worked,
                        was_working: false,
                        turn_complete: worked,
                    }
                });

            // Count how many lines actually changed — user typing ≈ 1 line,
            // Claude generating ≈ 2+ lines.
            let diff = changed_line_count(&tracker.prev_raw, &raw_capture);
            let significant = diff >= SIGNIFICANT_LINES;

            // Any content change clears turn_complete — user is interacting,
            // so hide (ready) until Claude responds again.
            if diff > 0 {
                tracker.turn_complete = false;
            }

            if significant {
                tracker.change_streak += 1;
                tracker.stable_streak = 0;
            } else {
                tracker.stable_streak += 1;
                tracker.change_streak = 0;
            }

            let state = if tracker.change_streak >= WORK_ENTER_TICKS {
                // Sustained multi-line changes — Claude is generating
                if !tracker.ever_worked {
                    tracker.ever_worked = true;
                    mark_worked(win.index);
                }
                tracker.was_working = true;
                WindowState::Working
            } else if tracker.was_working && tracker.stable_streak < WORK_EXIT_TICKS {
                // Recently was working, brief pause — keep showing Working
                WindowState::Working
            } else {
                if tracker.was_working {
                    // Transitioning from Working → stable: Claude finished this turn
                    tracker.turn_complete = true;
                }
                tracker.was_working = false;
                if tracker.turn_complete {
                    if detect_question(&raw_capture) {
                        WindowState::Asking
                    } else {
                        WindowState::Idle
                    }
                } else {
                    WindowState::Fresh
                }
            };

            tracker.prev_raw = raw_capture;
            states.insert(win.index, state);
        }

        // Prune trackers for windows that no longer exist
        let live_indices: std::collections::HashSet<u32> =
            windows.iter().map(|w| w.index).collect();
        self.trackers.retain(|idx, _| {
            let keep = live_indices.contains(idx);
            if !keep {
                clear_worked(*idx);
            }
            keep
        });

        states
    }
}
