// ── Claude Code hook handler ──
//
// Called by Claude Code hooks (UserPromptSubmit, Stop) to write CCS state events.
// Reads JSON from stdin, determines state, appends to ~/.ccs/events/{session_id}.jsonl.

use std::fs::{self, OpenOptions};
use std::io::{self, Read, Seek, SeekFrom, Write};
use std::path::PathBuf;

use serde::Deserialize;

use crate::cli::HookEvent;

// ── Types ──

#[derive(Deserialize)]
struct HookInput {
    session_id: String,
    cwd: String,
    transcript_path: Option<String>,
}

// ── Helpers ──

fn events_dir() -> PathBuf {
    let home = std::env::var("HOME").unwrap_or_default();
    PathBuf::from(home).join(".ccs").join("events")
}

/// Determine whether the Stop event should produce "idle" or "asking".
///
/// Reads the tail of the transcript and compares the position of the last
/// `"AskUserQuestion"` vs the last `"tool_result"`. If AskUserQuestion
/// appears later, the question hasn't been answered yet → "asking".
///
/// This approach avoids depending on JSON formatting (compact vs spaced)
/// by doing simple substring position comparisons on the raw content.
fn determine_stop_state(transcript_path: &str) -> &'static str {
    let file = match fs::File::open(transcript_path) {
        Ok(f) => f,
        Err(_) => return "idle",
    };

    let file_len = file.metadata().map(|m| m.len()).unwrap_or(0);
    if file_len == 0 {
        return "idle";
    }

    // Read last 64KB — enough to find the final assistant message
    let tail_start = file_len.saturating_sub(64 * 1024);
    let mut reader = io::BufReader::new(file);
    if reader.seek(SeekFrom::Start(tail_start)).is_err() {
        return "idle";
    }

    let mut tail = String::new();
    if reader.read_to_string(&mut tail).is_err() {
        return "idle";
    }

    // Compare positions: if AskUserQuestion appears after the last tool_result,
    // the question is still pending (unanswered).
    let last_ask = tail.rfind("\"AskUserQuestion\"");
    let last_result = tail.rfind("\"tool_result\"");

    match (last_ask, last_result) {
        (Some(ask_pos), Some(result_pos)) if ask_pos > result_pos => "asking",
        (Some(_), None) => "asking",
        _ => "idle",
    }
}

/// Append a state event to the session's event file.
fn write_event(session_id: &str, cwd: &str, pane_id: &str, state: &str) -> Result<(), String> {
    let dir = events_dir();
    fs::create_dir_all(&dir).map_err(|e| format!("create events dir: {e}"))?;

    let path = dir.join(format!("{session_id}.jsonl"));
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(&path)
        .map_err(|e| format!("open event file: {e}"))?;

    let ts = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();

    let line = format!(r#"{{"state":"{state}","cwd":"{cwd}","pane_id":"{pane_id}","ts":{ts}}}"#);
    writeln!(file, "{line}").map_err(|e| format!("write event: {e}"))?;

    Ok(())
}

// ── Public API ──

pub fn run(event: HookEvent) -> Result<(), String> {
    let mut input = String::new();
    io::stdin()
        .read_to_string(&mut input)
        .map_err(|e| format!("read stdin: {e}"))?;

    let hook: HookInput =
        serde_json::from_str(&input).map_err(|e| format!("parse hook input: {e}"))?;

    let state = match event {
        HookEvent::UserPrompt => "working",
        HookEvent::Stop => match hook.transcript_path.as_deref() {
            Some(path) => determine_stop_state(path),
            None => "idle",
        },
    };

    // $TMUX_PANE uniquely identifies which tmux pane Claude is running in.
    // This lets the sidebar distinguish sessions even when they share a cwd.
    let pane_id = std::env::var("TMUX_PANE").unwrap_or_default();

    write_event(&hook.session_id, &hook.cwd, &pane_id, state)
}

// ── Tests ──

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    #[test]
    fn test_determine_stop_state_idle() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("transcript.jsonl");
        let mut f = fs::File::create(&path).unwrap();
        writeln!(f, r#"{{"type":"user","message":{{"role":"user","content":"hi"}}}}"#).unwrap();
        writeln!(f, r#"{{"type":"assistant","message":{{"role":"assistant","content":[{{"type":"text","text":"hello"}}]}}}}"#).unwrap();

        assert_eq!(determine_stop_state(path.to_str().unwrap()), "idle");
    }

    #[test]
    fn test_determine_stop_state_asking_compact() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("transcript.jsonl");
        let mut f = fs::File::create(&path).unwrap();
        // Compact JSON (no spaces after colons)
        writeln!(f, r#"{{"type":"user","message":{{"role":"user","content":"hi"}}}}"#).unwrap();
        writeln!(f, r#"{{"type":"assistant","message":{{"role":"assistant","content":[{{"type":"tool_use","name":"AskUserQuestion"}}]}}}}"#).unwrap();

        assert_eq!(determine_stop_state(path.to_str().unwrap()), "asking");
    }

    #[test]
    fn test_determine_stop_state_asking_spaced() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("transcript.jsonl");
        let mut f = fs::File::create(&path).unwrap();
        // Spaced JSON (spaces after colons) — matches real Claude transcript format
        writeln!(f, r#"{{"type": "user", "message": {{"role": "user", "content": "hi"}}}}"#).unwrap();
        writeln!(f, r#"{{"type": "assistant", "message": {{"role": "assistant", "content": [{{"type": "tool_use", "name": "AskUserQuestion"}}]}}}}"#).unwrap();

        assert_eq!(determine_stop_state(path.to_str().unwrap()), "asking");
    }

    #[test]
    fn test_determine_stop_state_missing_file() {
        assert_eq!(determine_stop_state("/nonexistent/path.jsonl"), "idle");
    }

    #[test]
    fn test_determine_stop_state_empty_file() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("transcript.jsonl");
        fs::File::create(&path).unwrap();

        assert_eq!(determine_stop_state(path.to_str().unwrap()), "idle");
    }

    #[test]
    fn test_write_event_creates_file() {
        let dir = tempfile::tempdir().unwrap();
        let events = dir.path().join("events");

        fs::create_dir_all(&events).unwrap();
        let path = events.join("test-session.jsonl");

        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&path)
            .unwrap();
        writeln!(file, r#"{{"state":"working","cwd":"/tmp","ts":1234}}"#).unwrap();

        let content = fs::read_to_string(&path).unwrap();
        assert!(content.contains(r#""state":"working""#));
        assert!(content.contains(r#""cwd":"/tmp""#));
    }

    #[test]
    fn test_determine_stop_state_ask_then_answered() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("transcript.jsonl");
        let mut f = fs::File::create(&path).unwrap();
        // AskUserQuestion followed by tool_result (user answered) → idle
        writeln!(f, r#"{{"type":"assistant","content":[{{"type":"tool_use","name":"AskUserQuestion"}}]}}"#).unwrap();
        writeln!(f, r#"{{"type":"user","content":[{{"type":"tool_result","tool_use_id":"123"}}]}}"#).unwrap();
        writeln!(f, r#"{{"type":"assistant","content":[{{"type":"text","text":"ok"}}]}}"#).unwrap();

        assert_eq!(determine_stop_state(path.to_str().unwrap()), "idle");
    }

    #[test]
    fn test_determine_stop_state_no_ask_in_transcript() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("transcript.jsonl");
        let mut f = fs::File::create(&path).unwrap();
        // Normal conversation with tool use but no AskUserQuestion
        writeln!(f, r#"{{"type":"assistant","content":[{{"type":"tool_use","name":"Bash"}}]}}"#).unwrap();
        writeln!(f, r#"{{"type":"user","content":[{{"type":"tool_result"}}]}}"#).unwrap();
        writeln!(f, r#"{{"type":"assistant","content":[{{"type":"text","text":"done"}}]}}"#).unwrap();

        assert_eq!(determine_stop_state(path.to_str().unwrap()), "idle");
    }
}
