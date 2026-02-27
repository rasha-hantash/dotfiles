// ── Hook installation for Claude Code ──
//
// Adds CCS hook entries to ~/.claude/settings.json so Claude Code
// calls `ccs hook user-prompt` and `ccs hook stop` on session events.

use std::fs;
use std::path::{Path, PathBuf};

use serde_json::Value;

// ── Helpers ──

fn settings_path() -> PathBuf {
    let home = std::env::var("HOME").unwrap_or_default();
    PathBuf::from(home).join(".claude").join("settings.json")
}

fn ccs_bin_path() -> String {
    if let Ok(exe) = std::env::current_exe() {
        if let Ok(canonical) = fs::canonicalize(exe) {
            return canonical.to_string_lossy().to_string();
        }
    }
    let home = std::env::var("HOME").unwrap_or_default();
    format!("{home}/.local/bin/ccs")
}

/// Check if CCS hooks are already installed in settings.json.
pub fn hooks_installed(path: &Path) -> bool {
    let content = match fs::read_to_string(path) {
        Ok(c) => c,
        Err(_) => return false,
    };
    content.contains("ccs hook")
}

/// Install CCS hooks into settings.json.
/// Appends to existing hook arrays — does not overwrite.
pub fn install_hooks(path: &Path) -> Result<(), String> {
    install_hooks_with_bin(path, &ccs_bin_path())
}

fn install_hooks_with_bin(path: &Path, bin: &str) -> Result<(), String> {

    let mut settings: Value = if path.exists() {
        let content = fs::read_to_string(path).map_err(|e| format!("read settings: {e}"))?;
        serde_json::from_str(&content).map_err(|e| format!("parse settings: {e}"))?
    } else {
        // Create minimal settings structure
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).map_err(|e| format!("create settings dir: {e}"))?;
        }
        serde_json::json!({})
    };

    let hooks = settings
        .as_object_mut()
        .ok_or("settings.json is not an object")?
        .entry("hooks")
        .or_insert_with(|| serde_json::json!({}));

    let hooks_obj = hooks
        .as_object_mut()
        .ok_or("hooks is not an object")?;

    // UserPromptSubmit hook
    let user_prompt_entry = serde_json::json!({
        "matcher": "*",
        "hooks": [{
            "type": "command",
            "command": format!("{bin} hook user-prompt"),
            "async": true,
            "timeout": 5
        }]
    });

    let user_prompt_arr = hooks_obj
        .entry("UserPromptSubmit")
        .or_insert_with(|| serde_json::json!([]));
    user_prompt_arr
        .as_array_mut()
        .ok_or("UserPromptSubmit is not an array")?
        .push(user_prompt_entry);

    // Stop hook
    let stop_entry = serde_json::json!({
        "matcher": "*",
        "hooks": [{
            "type": "command",
            "command": format!("{bin} hook stop"),
            "async": true,
            "timeout": 5
        }]
    });

    let stop_arr = hooks_obj
        .entry("Stop")
        .or_insert_with(|| serde_json::json!([]));
    stop_arr
        .as_array_mut()
        .ok_or("Stop is not an array")?
        .push(stop_entry);

    let output =
        serde_json::to_string_pretty(&settings).map_err(|e| format!("serialize settings: {e}"))?;
    fs::write(path, output).map_err(|e| format!("write settings: {e}"))?;

    Ok(())
}

// ── Public API ──

pub fn run() -> Result<(), String> {
    let path = settings_path();

    if hooks_installed(&path) {
        println!("CCS hooks are already installed in ~/.claude/settings.json");
        return Ok(());
    }

    install_hooks(&path)?;
    println!("Installed CCS hooks in ~/.claude/settings.json");
    println!("  UserPromptSubmit → ccs hook user-prompt");
    println!("  Stop             → ccs hook stop");

    Ok(())
}

// ── Tests ──

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_hooks_installed_no_file() {
        assert!(!hooks_installed(Path::new("/nonexistent/settings.json")));
    }

    #[test]
    fn test_hooks_installed_empty() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("settings.json");
        fs::write(&path, "{}").unwrap();

        assert!(!hooks_installed(&path));
    }

    #[test]
    fn test_hooks_installed_present() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("settings.json");
        fs::write(&path, r#"{"hooks":{"Stop":[{"hooks":[{"command":"ccs hook stop"}]}]}}"#)
            .unwrap();

        assert!(hooks_installed(&path));
    }

    #[test]
    fn test_install_hooks_fresh() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("settings.json");
        fs::write(&path, "{}").unwrap();

        install_hooks_with_bin(&path, "ccs").unwrap();

        let content = fs::read_to_string(&path).unwrap();
        assert!(content.contains("ccs hook user-prompt"));
        assert!(content.contains("ccs hook stop"));

        // Verify JSON is valid
        let parsed: Value = serde_json::from_str(&content).unwrap();
        let hooks = parsed["hooks"].as_object().unwrap();
        assert_eq!(hooks["UserPromptSubmit"].as_array().unwrap().len(), 1);
        assert_eq!(hooks["Stop"].as_array().unwrap().len(), 1);
    }

    #[test]
    fn test_install_hooks_preserves_existing() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("settings.json");
        fs::write(
            &path,
            r#"{"hooks":{"Stop":[{"matcher":"*","hooks":[{"type":"command","command":"afplay sound.aiff"}]}]}}"#,
        )
        .unwrap();

        install_hooks_with_bin(&path, "ccs").unwrap();

        let content = fs::read_to_string(&path).unwrap();
        let parsed: Value = serde_json::from_str(&content).unwrap();

        // Stop should have 2 entries: original + CCS
        let stop = parsed["hooks"]["Stop"].as_array().unwrap();
        assert_eq!(stop.len(), 2);
        assert!(stop[0]["hooks"][0]["command"]
            .as_str()
            .unwrap()
            .contains("afplay"));
        assert!(stop[1]["hooks"][0]["command"]
            .as_str()
            .unwrap()
            .contains("ccs hook stop"));
    }

    #[test]
    fn test_install_hooks_creates_file() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("subdir").join("settings.json");

        install_hooks_with_bin(&path, "ccs").unwrap();

        assert!(path.exists());
        let content = fs::read_to_string(&path).unwrap();
        assert!(content.contains("ccs hook"));
    }
}
