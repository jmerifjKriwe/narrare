# Capability: Prompt Management

## Purpose
Provide API endpoints for listing, viewing, saving, and resetting prompt overrides using a cascade resolution strategy (project → user-global → bundled). Supports update detection and diff comparison between overrides and current bundled versions.

## Requirements

### Requirement: List prompts endpoint
The system SHALL provide an API endpoint that lists all available bundled prompts with metadata (id, name, category, language, source, has_override, can_edit, prompt_version).

#### Scenario: List all prompts
- **WHEN** `GET /api/v1/prompts` is called
- **THEN** a list of all bundled prompts across all categories and languages is returned with metadata

#### Scenario: Filter by category
- **WHEN** `GET /api/v1/prompts?category=generation` is called
- **THEN** only prompts in the "generation" category are returned

### Requirement: Get prompt content endpoint
The system SHALL provide an API endpoint that returns a prompt's resolved content via the cascade (project → user-global → bundled), along with the source, base content (bundled), and extracted variables.

#### Scenario: Get bundled prompt
- **WHEN** `GET /api/v1/prompts/{prompt_id}` is called for a prompt with no override
- **THEN** the bundled content is returned with `source: "bundled"` and `is_overridden: false`

#### Scenario: Get overridden prompt
- **WHEN** `GET /api/v1/prompts/{prompt_id}` is called for a prompt with a project-level override
- **THEN** the override content is returned with `source: "project"` and `is_overridden: true`

### Requirement: Save prompt override endpoint
The system SHALL provide an API endpoint that saves a prompt override to the project-level `.narrare/prompts/` directory, recording the bundled version as `override_of_version` in the override's frontmatter.

#### Scenario: Save new override
- **WHEN** `PUT /api/v1/prompts/{prompt_id}` is called with content
- **THEN** the override is saved to `.narrare/prompts/{prompt_path}/system.md` with `override_of_version` set to the current bundled version

### Requirement: Reset prompt override endpoint
The system SHALL provide an API endpoint that deletes a prompt override, restoring the bundled default.

#### Scenario: Reset existing override
- **WHEN** `DELETE /api/v1/prompts/{prompt_id}/override` is called for a prompt with an override
- **THEN** the override file is deleted and subsequent requests return the bundled content

#### Scenario: Reset non-existent override
- **WHEN** `DELETE /api/v1/prompts/{prompt_id}/override` is called for a prompt with no override
- **THEN** a 404 error is returned

### Requirement: Cascade info endpoint
The system SHALL provide an API endpoint that returns all cascade paths for a prompt with existence status for each level.

#### Scenario: Cascade info
- **WHEN** `GET /api/v1/prompts/{prompt_id}/cascade` is called
- **THEN** the response includes `cascade_paths` with entries for project, user-global, and bundled levels, each with `exists` boolean

### Requirement: Update detection
The system SHALL provide an API endpoint that returns a list of prompts where the user has overrides AND the bundled version has changed since the override was created.

#### Scenario: Detect available updates
- **WHEN** `GET /api/v1/prompts/updates` is called and a user override was created against bundled v1.0.0 but the current bundled version is v1.1.0
- **THEN** that prompt is included in the update list with both versions

#### Scenario: No updates available
- **WHEN** `GET /api/v1/prompts/updates` is called and all overrides match current bundled versions
- **THEN** an empty list is returned

### Requirement: Diff endpoint
The system SHALL provide an API endpoint that returns a comparison between a user's override and the current bundled default, suitable for rendering in the UI.

#### Scenario: Diff between override and new default
- **WHEN** `GET /api/v1/prompts/{prompt_id}/diff` is called for a prompt with an override and a new bundled version
- **THEN** the response includes `override_content`, `bundled_content`, and a structured diff representation

### Requirement: PromptManagementService contract
The system SHALL define a `PromptManagementProtocol` in the prompts module contracts that defines the list, get, save, reset, cascade_info, detect_updates, and diff operations. The service implementation SHALL be ported from `_scratch/packages/core/narrare_core/prompts/service.py`.

#### Scenario: Protocol-first development
- **WHEN** the prompts API module is implemented
- **THEN** `contracts.py` exists before `service.py` and defines the `PromptManagementProtocol`
