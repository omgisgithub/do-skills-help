# Third-party material

This experiment installed skills written by other people. Their files are **not** redistributed here, with one
exception (the Ponytail pack, MIT, kept with its licence in `conditions/C2/`).

| Condition | What was installed | Source | In this repository |
|---|---|---|---|
| C2 | Ponytail pack (its `AGENTS.md` + 6 skills) @ 96608e0 | https://github.com/DietrichGebert/ponytail (MIT) | yes, with `LICENSE.ponytail` |
| C5 | 50 public skills | https://github.com/anthropics/skills, https://github.com/openai/skills, https://github.com/vercel-labs/agent-skills, https://github.com/obra/superpowers (MIT), https://github.com/mattpocock/skills (MIT) | the list only: `conditions/C5/SOURCES.tsv` |

When a model opened a skill during a run, the skill's text was printed into that run's event log. The logs here
therefore quote parts of these skills: `using-superpowers`, `test-driven-development`,
`verification-before-completion`, `brainstorming`, `systematic-debugging`, `requesting-code-review`, `writing-plans`
(obra/superpowers, MIT, © Jesse Vincent), `diagnosing-bugs` (mattpocock/skills, MIT, © Matt Pocock), and `ponytail`
(MIT, © its authors). Those quotes remain under their authors' licences.

Agent CLIs used: Claude Code, OpenAI Codex CLI, OpenCode, Grok CLI. Their names and marks belong to their owners.
