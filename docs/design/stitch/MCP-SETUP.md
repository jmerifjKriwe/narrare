# Stitch MCP setup (interactive path)

For interactive design work (generate/edit/variants, design systems) the MCP is
the right tool; for bulk file downloads use the REST path in
[`README.md`](README.md) (context-sparing).

## Server

- Remote MCP: `https://stitch.googleapis.com/mcp`
- Auth header: `X-Goog-Api-Key`
- Project ID for narrare: `15314899202287259920`

## Configuration

Configured **user-wide** in `~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "servers": {
      "google-stitch": {
        "type": "remote",
        "url": "https://stitch.googleapis.com/mcp",
        "headers": { "X-Goog-Api-Key": "<key>" },
        "disabled": false
      }
    }
  }
}
```

The MCP stays in the user-level (openchamber) config and is **not** mirrored into
the repo's `opencode.json`. API key is created in Stitch → profile → Stitch
settings → API key.

## Tools (selected)

`list_projects`, `get_project`, `list_screens`, `get_screen`, `create_project`,
`update_project`, `delete_project`, `generate_screen_from_text`, `edit_screens`,
`generate_variants`, `create_design_system`, `create_design_system_from_design_md`,
`apply_design_system`, `list_design_systems`, `update_design_system`,
`update_screen`, `upload_design_md`, `download_file`.

`download_file` returns raw content into the agent context — prefer the REST
download endpoint for bulk operations.