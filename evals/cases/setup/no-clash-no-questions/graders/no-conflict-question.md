---
type: llm
focus: last_message
---

The session was refreshing the devflow profile of a project whose `CLAUDE.md` holds nothing that contradicts a devflow rule. Pass if the reply lists no rule of the project that clashes with devflow's and asks the maintainer to settle none; saying that there are no clashes is fine, and so are other findings and questions about the profile or config. Fail if it presents any line of the project's files as contradicting a devflow rule, or asks which of two rules should win.
