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

impl WindowTracker {
    /// Feed a new capture and return the current state.
    /// Keeps all I/O (filesystem, tmux) out — caller handles side effects.
    fn update(&mut self, raw_capture: &str) -> WindowState {
        let changed = any_change(&self.prev_raw, raw_capture);
        let significant = changed && is_significant_change(&self.prev_raw, raw_capture);

        // Any content change clears turn_complete — user is interacting,
        // so hide (ready) until Claude responds again.
        if changed {
            self.turn_complete = false;
        }

        if significant {
            self.change_streak += 1;
            self.stable_streak = 0;
        } else {
            self.stable_streak += 1;
            self.change_streak = 0;
        }

        let state = if self.change_streak >= WORK_ENTER_TICKS {
            // Sustained multi-line changes — Claude is generating
            self.ever_worked = true;
            self.was_working = true;
            WindowState::Working
        } else if self.was_working && self.stable_streak < WORK_EXIT_TICKS {
            // Recently was working, brief pause — keep showing Working
            WindowState::Working
        } else {
            if self.was_working {
                // Transitioning from Working → stable: Claude finished this turn
                self.turn_complete = true;
            }
            self.was_working = false;
            if self.turn_complete {
                if detect_question(raw_capture) {
                    WindowState::Asking
                } else {
                    WindowState::Idle
                }
            } else {
                WindowState::Fresh
            }
        };

        self.prev_raw = raw_capture.to_string();
        state
    }
}

// ── Cross-instance state sharing ──

fn state_dir() -> PathBuf {
    PathBuf::from("/tmp/ccs-state")
}

/// Remove all cross-instance state files. Call when creating a new session —
/// any existing files are stale from a dead session (the sidebar that would
/// have cleaned them up died with the old session).
pub fn clear_all_state() {
    let dir = state_dir();
    if let Ok(entries) = fs::read_dir(&dir) {
        for entry in entries.flatten() {
            fs::remove_file(entry.path()).ok();
        }
    }
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

/// Did any line change at all? (trimmed comparison)
fn any_change(old: &str, new: &str) -> bool {
    let al: Vec<&str> = old.lines().map(str::trim).collect();
    let bl: Vec<&str> = new.lines().map(str::trim).collect();
    al != bl
}

/// Is this a significant change (Claude generating) vs trivial (user typing)?
/// User typing only modifies the bottom line (input area).
/// Claude generating scrolls content — upper lines change.
fn is_significant_change(old: &str, new: &str) -> bool {
    let al: Vec<&str> = old.lines().map(str::trim).collect();
    let bl: Vec<&str> = new.lines().map(str::trim).collect();

    // Different line count → content structure changed
    if al.len() != bl.len() {
        return true;
    }

    // Only 1 line → can't distinguish, treat as non-significant
    if al.len() <= 1 {
        return false;
    }

    // If any non-bottom line changed, content is scrolling → Claude is generating
    al[..al.len() - 1] != bl[..bl.len() - 1]
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
            let raw_capture = tmux::capture_pane(win.index, 10).unwrap_or_default();

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

            let was_worked = tracker.ever_worked;
            let state = tracker.update(&raw_capture);
            if tracker.ever_worked && !was_worked {
                mark_worked(win.index);
            }
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

// ── Tests ──

#[cfg(test)]
mod tests {
    use super::*;

    fn fresh_tracker() -> WindowTracker {
        WindowTracker {
            prev_raw: String::new(),
            change_streak: 0,
            stable_streak: 0,
            ever_worked: false,
            was_working: false,
            turn_complete: false,
        }
    }

    /// Feed a sequence of captures to a fresh tracker and return all states.
    fn run_sequence(captures: &[&str]) -> Vec<WindowState> {
        let mut tracker = fresh_tracker();
        captures.iter().map(|c| tracker.update(c)).collect()
    }

    // ── Pure helper tests: any_change ──

    #[test]
    fn no_change_detected() {
        assert!(!any_change("line1\nline2\n", "line1\nline2\n"));
    }

    #[test]
    fn whitespace_only_no_change() {
        assert!(!any_change("line1  \nline2\n", "line1\nline2  \n"));
    }

    #[test]
    fn content_change_detected() {
        assert!(any_change("line1\nline2", "line1\nline2 changed"));
    }

    // ── Pure helper tests: is_significant_change ──

    #[test]
    fn user_typing_not_significant() {
        let old = "header\nmiddle\ninput line";
        let new = "header\nmiddle\ninput line changed";
        assert!(!is_significant_change(old, new));
    }

    #[test]
    fn claude_generating_significant() {
        let old = "line1\nline2\nline3";
        let new = "line2\nline3\nline4";
        assert!(is_significant_change(old, new));
    }

    #[test]
    fn line_count_change_significant() {
        let old = "line1\nline2";
        let new = "line1\nline2\nline3";
        assert!(is_significant_change(old, new));
    }

    #[test]
    fn single_line_not_significant() {
        assert!(!is_significant_change("hello", "world"));
    }

    // ── Pure helper tests: detect_question ──

    #[test]
    fn question_yes_no() {
        assert!(detect_question("some output\n(Y)es/(N)o"));
    }

    #[test]
    fn question_yn_shorthand() {
        assert!(detect_question("prompt text\n(y/N)"));
    }

    #[test]
    fn question_yn_brackets() {
        assert!(detect_question("prompt text\n[y/N]"));
    }

    #[test]
    fn question_yes_no_parens() {
        assert!(detect_question("prompt text\n(yes/no)"));
    }

    #[test]
    fn question_selection_marker() {
        assert!(detect_question("Choose an option:\n❯ Option 1"));
    }

    #[test]
    fn question_allow_deny() {
        assert!(detect_question("Run this command?\nAllow  Deny"));
    }

    #[test]
    fn normal_text_no_question() {
        assert!(!detect_question("Claude generated some output.\nHere is the result."));
    }

    #[test]
    fn allow_in_prose_no_match() {
        // "Allow" in the middle of prose, not on the last 2 lines as a prompt
        assert!(!detect_question(
            "You should allow this.\nBut deny that.\nHere is the final line."
        ));
    }

    #[test]
    fn question_not_in_last_two_lines() {
        // Question pattern exists but is NOT in the last 2 lines
        assert!(!detect_question("(Y)es/(N)o\nsome line\nanother line\nfinal line"));
    }

    // ── State machine tests ──

    #[test]
    fn fresh_session_stays_fresh() {
        let same = "static content\nline two";
        let states = run_sequence(&[same, same, same, same, same]);
        assert!(states.iter().all(|s| *s == WindowState::Fresh));
    }

    #[test]
    fn claude_generates_then_idle() {
        // Simulate Claude generating: upper lines shift each tick
        let captures: Vec<String> = (0..10)
            .map(|i| format!("header {i}\nmiddle {i}\nbottom"))
            .collect();

        // First 3 ticks with significant changes, then 7 stable ticks
        let mut sequence: Vec<&str> = captures[..3].iter().map(|s| s.as_str()).collect();
        let stable = captures[2].as_str();
        for _ in 0..7 {
            sequence.push(stable);
        }

        let states = run_sequence(&sequence);

        // Tick 0: first capture, prev_raw is empty → significant (line count change), streak=1 → Fresh
        assert_eq!(states[0], WindowState::Fresh);
        // Tick 1: second significant change, streak=2 → Working (WORK_ENTER_TICKS=2)
        assert_eq!(states[1], WindowState::Working);
        // Tick 2: third significant change → Working
        assert_eq!(states[2], WindowState::Working);
        // Ticks 3-7: stable, but hysteresis keeps Working (WORK_EXIT_TICKS=5)
        for state in &states[3..7] {
            assert_eq!(*state, WindowState::Working);
        }
        // Tick 8+: stable_streak >= WORK_EXIT_TICKS → Idle (turn_complete set)
        assert_eq!(*states.last().unwrap(), WindowState::Idle);
    }

    #[test]
    fn user_typing_stays_fresh() {
        // Only the last line changes — non-significant
        let captures = [
            "header\nmiddle\nuser typing a",
            "header\nmiddle\nuser typing ab",
            "header\nmiddle\nuser typing abc",
            "header\nmiddle\nuser typing abcd",
            "header\nmiddle\nuser typing abcde",
        ];
        let states = run_sequence(&captures);
        assert!(
            states.iter().all(|s| *s == WindowState::Fresh),
            "expected all Fresh, got: {states:?}"
        );
    }

    #[test]
    fn ready_clears_on_typing() {
        let mut tracker = fresh_tracker();

        // Claude generates (significant changes to enter Working)
        for i in 0..3 {
            tracker.update(&format!("line {i}\ncontent {i}\nbottom"));
        }
        assert_eq!(tracker.update(&format!("line 2\ncontent 2\nbottom")), WindowState::Working);

        // Stabilize to reach Idle (WORK_EXIT_TICKS=5 stable ticks)
        let stable = "line 2\ncontent 2\nbottom";
        for _ in 0..WORK_EXIT_TICKS {
            tracker.update(stable);
        }
        assert_eq!(tracker.update(stable), WindowState::Idle);

        // User starts typing — only last line changes → should go to Fresh
        let state = tracker.update("line 2\ncontent 2\nuser types");
        assert_eq!(state, WindowState::Fresh);
    }

    #[test]
    fn no_false_working_on_enter() {
        let mut tracker = fresh_tracker();
        // Simulate a session that has been Idle (Claude finished a turn)
        tracker.ever_worked = true;
        tracker.turn_complete = true;
        tracker.prev_raw = "header\nmiddle\nbottom".to_string();

        // Verify we start at Idle
        let state = tracker.update("header\nmiddle\nbottom");
        assert_eq!(state, WindowState::Idle);

        // User hits enter — single last-line change
        let state = tracker.update("header\nmiddle\n");
        assert_eq!(state, WindowState::Fresh, "enter should not trigger Working");

        // Stable after enter
        let state = tracker.update("header\nmiddle\n");
        assert_eq!(state, WindowState::Fresh);

        let state = tracker.update("header\nmiddle\n");
        assert_eq!(state, WindowState::Fresh);
    }

    #[test]
    fn hysteresis_keeps_working() {
        let mut tracker = fresh_tracker();

        // Enter Working state (2 significant changes)
        tracker.update("line 0\ncontent 0\nbottom");
        tracker.update("line 1\ncontent 1\nbottom");
        assert_eq!(
            tracker.update("line 2\ncontent 2\nbottom"),
            WindowState::Working
        );

        // 3 stable ticks (less than WORK_EXIT_TICKS=5) — should stay Working
        let stable = "line 2\ncontent 2\nbottom";
        for _ in 0..3 {
            assert_eq!(tracker.update(stable), WindowState::Working);
        }

        // Significant change again — still Working, no flicker
        assert_eq!(
            tracker.update("line 3\ncontent 3\nbottom"),
            WindowState::Working
        );
    }

    #[test]
    fn asking_on_question_prompt() {
        let mut tracker = fresh_tracker();

        // Claude generates
        for i in 0..3 {
            tracker.update(&format!("line {i}\ncontent {i}\nbottom"));
        }

        // Stabilize with a question prompt in the last 2 lines
        let question = "some output\nDo you want to proceed?\n(Y)es/(N)o";
        for _ in 0..(WORK_EXIT_TICKS + 1) {
            tracker.update(question);
        }

        assert_eq!(tracker.update(question), WindowState::Asking);
    }

    #[test]
    fn cross_instance_shows_idle() {
        // Simulate a tracker that was initialized from cross-instance state
        // (another sidebar already saw Claude work)
        let mut tracker = WindowTracker {
            prev_raw: "stable content\nline two".to_string(),
            change_streak: 0,
            stable_streak: 0,
            ever_worked: true,
            was_working: false,
            turn_complete: true,
        };

        let state = tracker.update("stable content\nline two");
        assert_eq!(state, WindowState::Idle);
    }

    #[test]
    fn ever_worked_set_on_working() {
        let mut tracker = fresh_tracker();
        assert!(!tracker.ever_worked);

        // Feed significant changes to reach Working
        tracker.update("line 0\ncontent 0\nbottom");
        tracker.update("line 1\ncontent 1\nbottom");

        assert!(tracker.ever_worked, "ever_worked should be set after entering Working");
    }

    #[test]
    fn stale_state_causes_false_ready_then_clears() {
        // Bug: stale /tmp/ccs-state/ file from a dead session makes a new session
        // show "(ready)" immediately. Then Claude loads, content changes, and
        // turn_complete is cleared → "(ready)" disappears.
        let mut tracker = WindowTracker {
            prev_raw: "loading claude...".to_string(),
            change_streak: 0,
            stable_streak: 0,
            ever_worked: true,  // ← stale cross-instance state
            was_working: false,
            turn_complete: true, // ← causes Idle ("ready") on first tick
        };

        // First tick: stable content → Idle (false "ready")
        let state = tracker.update("loading claude...");
        assert_eq!(state, WindowState::Idle, "stale state shows false ready");

        // Claude finishes loading — content changes (non-significant, last line only)
        let state = tracker.update("loading claude...\n>");
        // turn_complete cleared by any_change → Fresh
        assert_eq!(state, WindowState::Fresh, "ready should disappear after content change");
    }
}
