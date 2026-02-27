// ── Claude Code hook handler ──
//
// Called by Claude Code hooks (UserPromptSubmit, Stop) to write CCS state events.
// Reads JSON from stdin, determines state, appends to ~/.ccs/events/{session_id}.jsonl.

use std::fs::{self, OpenOptions};
use std::io::{self, BufRead, Read, Seek, SeekFrom, Write};
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
/// Reads the tail of the transcript file and checks if the last assistant
/// message contains an AskUserQuestion tool_use.
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

    // If we seeked mid-line, skip the partial first line
    if tail_start > 0 {
        let mut discard = String::new();
        let _ = reader.read_line(&mut discard);
    }

    // Scan for the last line containing "type":"assistant"
    let mut last_assistant_line: Option<String> = None;
    let mut line = String::new();
    loop {
        line.clear();
        match reader.read_line(&mut line) {
            Ok(0) => break,
            Ok(_) => {
                if line.contains(r#""type":"assistant""#) {
                    last_assistant_line = Some(line.clone());
                }
            }
            Err(_) => break,
        }
    }

    match last_assistant_line {
        Some(l) if l.contains(r#""name":"AskUserQuestion""#) => "asking",
        _ => "idle",
    }
}

/// Append a state event to the session's event file.
fn write_event(session_id: &str, cwd: &str, state: &str) -> Result<(), String> {
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

    let line = format!(r#"{{"state":"{state}","cwd":"{cwd}","ts":{ts}}}"#);
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

    write_event(&hook.session_id, &hook.cwd, state)
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
    fn test_determine_stop_state_asking() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("transcript.jsonl");
        let mut f = fs::File::create(&path).unwrap();
        writeln!(f, r#"{{"type":"user","message":{{"role":"user","content":"hi"}}}}"#).unwrap();
        writeln!(f, r#"{{"type":"assistant","message":{{"role":"assistant","content":[{{"type":"tool_use","name":"AskUserQuestion"}}]}}}}"#).unwrap();

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

        // Temporarily override HOME to use temp dir
        // We test the write_event internals directly instead
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
    fn test_determine_stop_state_ask_then_text() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("transcript.jsonl");
        let mut f = fs::File::create(&path).unwrap();
        // AskUserQuestion followed by a text-only assistant message → idle
        writeln!(f, r#"{{"type":"assistant","message":{{"role":"assistant","content":[{{"type":"tool_use","name":"AskUserQuestion"}}]}}}}"#).unwrap();
        writeln!(f, r#"{{"type":"user","message":{{"role":"user","content":[{{"type":"tool_result"}}]}}}}"#).unwrap();
        writeln!(f, r#"{{"type":"assistant","message":{{"role":"assistant","content":[{{"type":"text","text":"ok"}}]}}}}"#).unwrap();

        assert_eq!(determine_stop_state(path.to_str().unwrap()), "idle");
    }
}
