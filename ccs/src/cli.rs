use clap::{Parser, Subcommand};

#[derive(Parser)]
#[command(name = "ccs", about = "Claude Code session manager")]
pub struct Cli {
    #[command(subcommand)]
    pub command: Command,
}

#[derive(Subcommand)]
pub enum Command {
    /// Start or add a session tab
    Start {
        /// Session name
        #[arg(default_value = "session-1")]
        name: String,
        /// Working directory
        dir: Option<String>,
    },
    /// List active sessions
    #[command(alias = "ls")]
    List,
    /// Kill a single session tab
    Kill {
        /// Session name to kill
        name: String,
    },
    /// Kill all sessions
    AllKill,
    /// Reattach to existing session
    Resume,
    /// Interactive session navigator (launched by start)
    Sidebar,
}
