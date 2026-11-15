---
type: tool_order
before: { tool: Bash, input_match: '"command"\s*:\s*"(?:(?:[^"\\]|\\.)*?(?:&&|;|\||\\n))?\s*\(?\s*(?:\w+=(?:\$\([^)]*\)|\S+)\s+)*(?:timeout \d+\s+)?(?:uv run (?:--no-project )?)?python[\d.]*(?:\s+-\S+(?:\s+[^-\s]\S*)?)*\s+(?:\\")?(?:\S*/)?tests/release_check\.py' }
after: { tool: Bash, input_match: 'release create' }
---
