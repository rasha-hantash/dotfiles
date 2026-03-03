# Claude Code Memory

## Permission Behavior

- **Batch permissions upfront**: Before any non-trivial task, list each permission needed as a short yes/no item. No paragraphs of explanation.
- **Don't re-ask for already-granted permissions**: `~/workspace/**` is readable, `~/workspace/personal/**` is editable/writable, `cargo *` is auto-approved. Stop prompting for these.
- **Format**: Simple checklist, one line per permission:
  ```
  Before I start, I'll need:
  - Read/edit files in `crates/` — approve?
  - Run `gt create` and `gt submit` — approve?
  ```
