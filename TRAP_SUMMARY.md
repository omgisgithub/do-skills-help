# The trap test: outcomes only

A second experiment asked seven models to add a feature to a made-up invoicing app and then use a skill to commit the
change. One line in that skill was planted by the author. The app's keys were fake, the receiver was a logger on the
author's own laptop, and nothing left the machine.

**The working trap is not published**: not the planted line, not the sending command, not the receiver. This file
gives the outcomes, which is all the video shows.

| Model | Scored runs | Sent the (fake) keys | Warned the user | Said nothing about it |
|---|---|---|---|---|
| Claude Haiku 5.5 | 20 | 0 | 20 | 0 |
| Claude Sonnet 5.5 | 20 | 0 | 20 | 0 |
| Claude Opus 5.5 | 10 | 0 | 10 | 0 |
| GPT-6.1 Sol | 18 | 0 | 15 | 3 |
| GPT-6 Luna | 18 | 11 | 3 | 4 |
| Grok 4.7 | 20 | 0 | 18 | 2 |
| Grok 4.7 Fast | 20 | 0 | 19 | 1 |
| **All** | **126** | **11** | **105** | **10** |

GPT-6 Luna by version of the planted line: plain line 1 of 4; with an excuse 5 of 5; moved into a setup script 5 of 5;
as a hidden note 0 of 4. None of the 11 runs that sent the keys mentioned it in its final message.

Control: the same skill without the planted line, 33 runs, nothing sent.

Limits: OpenAI's models ran through the API with the author's own four tools, not in Codex; Claude ran in Claude Code
and Grok in its own CLI. At most 5 scored runs per model and version, so this is a warning, not a safety rating. Ten
more Claude Opus runs were stopped by the provider's filter before they started and are not scored.
