// ── ratatui rendering for sidebar ──

use std::collections::HashMap;

use ratatui::buffer::Buffer;
use ratatui::layout::Rect;
use ratatui::style::{Modifier, Style};
use ratatui::text::{Line, Span};
use ratatui::widgets::Widget;

use crate::colors;
use crate::sidebar::state::WindowState;
use crate::tmux::WindowInfo;

// ── Types ──

/// Legend entry for keyboard shortcuts.
struct LegendEntry {
    key: &'static str,
    label: &'static str,
}

const LEGEND: &[LegendEntry] = &[
    LegendEntry {
        key: "\u{2318} + j",
        label: "claude",
    },
    LegendEntry {
        key: "\u{2318} + m",
        label: "terminal",
    },
    LegendEntry {
        key: "\u{2318} + p",
        label: "sessions",
    },
    LegendEntry {
        key: "\u{2318} + ;",
        label: "exit",
    },
];

pub struct SidebarWidget<'a> {
    pub windows: &'a [WindowInfo],
    pub states: &'a HashMap<u32, WindowState>,
    pub selected: usize,
    pub tick: u64,
}

// ── Public API ──

impl Widget for SidebarWidget<'_> {
    fn render(self, area: Rect, buf: &mut Buffer) {
        let window_count = self.windows.len();

        // ── Header ──
        let plural = if window_count == 1 { "" } else { "s" };
        let header = Line::from(vec![
            Span::raw(" "),
            Span::styled(
                format!("{window_count} session{plural}"),
                Style::default().fg(colors::OVERLAY),
            ),
            Span::styled(" \u{00b7} ", Style::default().fg(colors::OVERLAY)),
            Span::styled("\u{2191}\u{2193}", Style::default().fg(colors::BLUE)),
            Span::styled(" switch", Style::default().fg(colors::OVERLAY)),
        ]);
        if area.height > 0 {
            buf.set_line(area.x, area.y, &header, area.width);
        }

        // ── Separator ──
        if area.height > 1 {
            let sep_row = area.y + 1;
            for x in area.x..area.x + area.width {
                buf.cell_mut((x, sep_row))
                    .map(|cell| cell.set_char('\u{2500}').set_fg(colors::SURFACE));
            }
        }

        // ── Body: sessions (left) + legend (right) ──
        let body_start = area.y + 2;
        let max_rows = window_count.max(LEGEND.len());

        // Calculate right column start (for legend)
        let right_col = area.width.saturating_sub(18);

        #[allow(clippy::needless_range_loop)] // indexes two parallel arrays of different lengths
        for row in 0..max_rows {
            let y = body_start + row as u16;
            if y >= area.y + area.height {
                break;
            }

            // Left column: session list
            if row < window_count {
                let win = &self.windows[row];
                let state = self
                    .states
                    .get(&win.index)
                    .copied()
                    .unwrap_or(WindowState::Fresh);
                let is_selected = row == self.selected;

                let (bullet, name_style) = if is_selected {
                    (
                        Span::styled("\u{25cf}", Style::default().fg(colors::PEACH)),
                        Style::default()
                            .fg(colors::PEACH)
                            .add_modifier(Modifier::BOLD),
                    )
                } else {
                    (
                        Span::styled("\u{00b7}", Style::default().fg(colors::OVERLAY)),
                        Style::default().fg(colors::OVERLAY),
                    )
                };

                let indicator = state_indicator(state, self.tick);

                let line = Line::from(vec![
                    Span::raw(" "),
                    bullet,
                    Span::raw(" "),
                    Span::styled(&win.name, name_style),
                    indicator,
                ]);
                buf.set_line(area.x, y, &line, right_col);
            }

            // Right column: legend
            if row < LEGEND.len() {
                let entry = &LEGEND[row];
                let legend_line = Line::from(vec![
                    Span::styled(entry.key, Style::default().fg(colors::BLUE)),
                    Span::raw("  "),
                    Span::styled(entry.label, Style::default().fg(colors::OVERLAY)),
                ]);
                buf.set_line(area.x + right_col, y, &legend_line, area.width - right_col);
            }
        }
    }
}

// ── Helpers ──

fn state_indicator(state: WindowState, tick: u64) -> Span<'static> {
    match state {
        WindowState::Working => {
            // Blink: peach dot for 5 ticks, dim dot for 5 ticks (0.5s each at 100ms/tick)
            if tick % 10 < 5 {
                Span::styled(" \u{25cf}", Style::default().fg(colors::PEACH))
            } else {
                Span::styled(" \u{00b7}", Style::default().fg(colors::SURFACE))
            }
        }
        WindowState::Idle => Span::styled(" \u{2753}", Style::default()),
        WindowState::Done => Span::styled(" \u{25cf}", Style::default().fg(colors::GREEN)),
        WindowState::Fresh => Span::raw(""),
    }
}
