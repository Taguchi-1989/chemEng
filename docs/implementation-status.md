# ChemEng Implementation Status

This document reflects the current implementation in the repository and fills gaps not fully covered by the older summary documents.

## Registered calculation skills

- `property_estimation`
- `distillation`
- `mass_balance`
- `heat_balance`
- `extraction`
- `absorption`
- `txy_diagram`
- `lcoh`

## Additional API endpoints currently implemented

- `POST /api/v1/calculate/batch`
  Batch execution for up to 50 cases.
- `POST /api/v1/txy-diagram`
  Returns T-x-y diagram data for a binary system.
- `POST /api/v1/chat`
  AI chat endpoint for the help panel.
- `POST /api/v1/suggest`
  AI parameter suggestion endpoint.
- `GET /api/v1/substances`
  Curated substance list used by the web UI autocomplete.
- `GET /api/v1/substances/{substance}`
  Substance detail lookup using the selected engine.

## Web UI capabilities currently implemented

- Saved-case dashboard for comparing multiple runs
- Calculation history stored in `localStorage`
- JSON import for single-case and batch execution flows
- T-x-y modal chart in the distillation workflow
- AI help panel and AI parameter suggestions
- JSON / CSV export and HTML report generation

## CLI capabilities currently implemented

- Interactive mode when no subcommand is provided
- `property`
- `calculate`
- `skill list|show`
- `engine list|show`
- `info`
- `data sources|search|fetch|list|show|delete`

## Data path clarification

The codebase currently uses two related but distinct substance-data paths.

### Curated defaults

- Source: `skills/defaults/common_substances.yaml`
- Used by: `/api/v1/substances`, web autocomplete, curated UI listing

### Writable local property database

- Source: `data/custom_substances.yaml`
- Used by: `PropertyDatabase`, CLI `data fetch`, local fetched-property persistence

These are not the same storage path, so records fetched into the writable local database do not automatically become part of the curated `/api/v1/substances` list.
