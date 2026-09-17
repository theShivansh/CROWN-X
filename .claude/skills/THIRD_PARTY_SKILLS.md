# Third-party skills

Installed by `scripts/install_ui_skills.py` at pinned commits (ADR-007). Don't edit these
directories by hand; change the pin in the script and reinstall with `--force`.

| Skill | Repository | Commit | Licence | Note |
|---|---|---|---|---|
| `design-taste-frontend` | github.com/Leonxlnx/taste-skill | `ccbc15639c97057cbfcf32ecebc38ef716e4bb37` | MIT | Anti-slop frontend rules. Upstream scope: landing pages, portfolios, redesigns. |
| `ui-ux-pro-max` | github.com/nextlevelbuilder/ui-ux-pro-max-skill | `8bd29e775453ebcae52b6e6514fbf134df0c5770` | MIT | Local UX/design search. Patched: script paths use ${CLAUDE_SKILL_DIR}, because ${CLAUDE_PLUGIN_ROOT} only exists when installed as a plugin. |
