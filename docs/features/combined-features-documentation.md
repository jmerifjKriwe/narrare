# Narrare Features - Complete Documentation

> This document consolidates all feature documentation from the Narrare writing platform.

---

## Table of Contents

1. [Core Writing Features](#core-writing-features)
2. [AI Assistance & Analysis](#ai-assistance--analysis)
3. [Knowledge Base & Worldbuilding](#knowledge-base--worldbuilding)
4. [Project Management](#project-management)
5. [Integration & Tools](#integration--tools)

---

## Core Writing Features

### AI Writing Assistant

> AI-powered writing assistance with continuation, rewriting, and suggestion capabilities.

The AI Writing Assistant provides intelligent writing support through multiple interfaces:

**Key Features:**
- **Text Continuation**: Generate seamless continuations from your cursor position
- **Rewriting**: Rephrase selected text with different styles or approaches
- **Context-Aware**: Uses your Knowledge Base to maintain consistency
- **Multi-language Support**: English, German, and French

**Usage:**
- Editor: Inline suggestions and toolbar buttons
- CLI: `narrare writing continue`, `narrare writing rewrite`
- MCP: Access through Claude Desktop
- API: REST endpoints for programmatic access

---

### Co-Author Mode

> Collaborative AI writing with version control and iterative refinement.

Co-Author Mode transforms the AI from a tool into a writing partner that can:

**Capabilities:**
- Generate alternative versions of your text
- Maintain version history of changes
- Accept/reject individual modifications
- Combine elements from multiple versions

**Workflow:**
1. Select text you want to improve
2. Open Co-Author panel
3. AI generates alternative version
4. Review changes with diff view
5. Accept, reject, or modify specific elements

**Best Practices:**
- Use for dialogue refinement and scene enhancement
- Combine with Voice Checker for character consistency
- Leverage Rejection Learning to improve future suggestions

---

### Multi-Draft Generation

> Generate 2-5 alternative versions of any passage with different approaches.

Multi-Draft Generation creates multiple variations of your text, each with:

**Output Features:**
- **Labels**: Clear identification of each draft's focus
- **Strengths/Weaknesses**: Analysis of what each version does well
- **Comparative Overview**: Side-by-side comparison of all drafts

**Generation Modes:**
- New chapter creation
- Extending existing content
- Rewriting selected passages

**Usage:**
```bash
narrare writing multi-draft --chapter <id> --count 3
narrare writing multi-draft --selection <text> --variations "dramatic,quiet,humorous"
```

**Best Practices:**
- Use variations to guide contrast in tone
- Combine elements from multiple drafts
- Start with 3 drafts for manageable comparison

---

### Writer's Unblock

> AI analyzes your last paragraphs and suggests 3 continuations with different tones.

When you're stuck, Writer's Unblock provides:

**Process:**
1. Analyzes last 500-1000 tokens of your chapter
2. Generates three continuations in different tones
3. Provides confidence scores for each suggestion
4. Allows quick acceptance or regeneration

**Default Tones:**
- **Dramatic**: Raises stakes and intensifies emotions
- **Quiet**: Focuses on reflection and sensory details
- **Surprising**: Introduces unexpected twists

**Customization:**
```bash
narrare writing unblock --chapter <id> --tones "tense,humorous,mysterious"
```

**Best Practices:**
- Use early and often during drafting
- Combine suggestions from different tones
- Trust confidence scores but don't be afraid of low scores

---

### Voice Cloning

> AI learns your writing style from existing chapters and generates text in your voice.

Voice Cloning captures your unique writing voice through:

**Analysis Phase:**
- Sentence length distribution
- Vocabulary profile and diversity
- Dialogue-to-narration ratio
- Metaphor density and usage patterns
- Narrative rhythm and paragraph structure

**Generation Phase:**
- Loads your Style Profile from persistent storage
- Uses few-shot prompting with your actual examples
- Generates text matching your measured patterns
- Streams results in real-time

**Usage:**
```bash
narrare voice analyze --novel <id>
narrare voice generate --novel <id> --prompt "The door creaked open, revealing"
```

**Best Practices:**
- Analyze after 3+ chapters for accuracy
- Re-analyze after major style changes
- Use specific, grounded prompts for best results

---

## AI Assistance & Analysis

### Dialogue Coach

> AI analyzes dialogue for common problems and suggests improvements.

Dialogue Coach identifies and fixes:

**Problem Types:**
- **Subtext Violations**: When characters say exactly what they think
- **Info-Dumping**: Excessive exposition through dialogue
- **Redundancy**: Repeating information unnecessarily
- **Character Voice Inconsistency**: When characters don't sound like themselves

**Analysis Modes:**
- **Analyze**: Identifies problems without changing text
- **Improve**: Provides rewritten versions

**Usage:**
```bash
narrare dialogue analyze --chapter <id>
narrare dialogue improve --selection <text> --character <id>
```

**Best Practices:**
- Analyze before improving to understand issues
- Assign characters properly in chapter metadata
- Use improvements as starting points, not final versions

---

### POV Tracker

> Automatically detect and track Point-of-View characters with head-hopping detection.

POV Tracker ensures narrative consistency through:

**Detection Capabilities:**
- POV character identification per scene
- Head-hopping detection (mid-scene switches)
- Knowledge leakage identification
- Emotional leakage detection
- Physical impossibility detection

**Analysis Types:**
- **Single-character POV**: Third person limited
- **Omniscient POV**: Access to multiple thoughts
- **First-person POV**: "I" narration
- **Head-hopping**: Problematic mid-scene switches

**Statistics Provided:**
- POV distribution percentages
- Switch frequency analysis
- Character POV mapping
- Problematic scene identification

**Best Practices:**
- Know your POV type and stick to it
- Use scene breaks for intentional POV switches
- Check consistency during revision

---

### Readability Analysis

> AI analyzes text readability using industry-standard metrics with improvement suggestions.

Readability Analysis combines mathematical formulas with AI feedback:

**Metrics Calculated:**
- **Flesch Reading Ease** (0-100): Higher = easier
- **Flesch-Kincaid Grade Level** (0-18): Education level needed
- **Gunning Fog Index** (0-20): Years of education needed

**AI-Powered Features:**
- Identifies problematic sentences
- Explains why sentences are difficult
- Suggests 2-3 rewrite alternatives
- Preserves voice while improving clarity

**Genre Benchmarks:**
- Middle Grade: 80-90 (Flesch), Grade 4-6
- Young Adult: 70-85, Grade 6-8
- Commercial Fiction: 60-75, Grade 7-9
- Literary Fiction: 50-70, Grade 8-12

**Best Practices:**
- Use during revision, not first draft
- Balance variety and consistency
- Simplify without dumbing down

---

### Sensitivity Reader

> AI-powered sensitivity analysis flags stereotypes and problematic representations.

Sensitivity Reader helps write inclusive fiction by identifying:

**Issue Categories:**
- **Stereotypes**: Reductive characterizations
- **Harmful Tropes**: Marginalizing narrative patterns
- **Cultural Appropriation**: Misuse of cultural elements
- **Representation Issues**: Tokenism, exclusion
- **Language Concerns**: Slurs, insensitive phrasing
- **Historical Inaccuracies**: Misrepresentation of cultures/events

**Severity Levels:**
- **Critical**: Slurs, hate speech, dehumanizing language
- **High**: Harmful stereotypes, toxic tropes
- **Medium**: Problematic patterns, missed opportunities
- **Low**: Minor insensitivities, phrasing improvements

**Best Practices:**
- Use during drafting, not just before publication
- Context matters for historical accuracy
- Focus on high-impact changes first
- Combine with human sensitivity readers

---

### Sentiment Analysis

> Track emotional arcs and tone shifts across your story chapter by chapter.

Sentiment Analysis maps your story's emotional landscape through:

**VAD Dimensions:**
- **Valence**: Positive/negative emotional tone (0-1)
- **Arousal**: Calm/excited state (0-1)
- **Dominance**: Submissive/dominant stance (0-1)

**Emotion Scores:**
Eight basic emotions: joy, sadness, anger, fear, surprise, anticipation, trust, disgust

**Arc Detection:**
Recognized patterns: Rags to riches, Tragedy, Man in a hole, Icarus, Cinderella, Oedipus

**Best Practices:**
- Use during revision to check emotional intent
- Compare segments within chapters for jarring shifts
- Track arcs across the whole novel

---

### Literary Analysis Suite

> Comprehensive thematic, comparative, and readability analysis.

Combines four analysis types:

**1. Comprehensive Literary Analysis:**
- Style, tone, narrative voice
- Structural patterns
- Literary devices

**2. Readability Analysis:**
- Flesch Reading Ease
- Flesch-Kincaid Grade Level
- Gunning Fog Index
- AI rewrite suggestions

**3. Thematic Analysis:**
- Themes and motifs
- Symbols and imagery
- Thematic density and distribution

**4. Comparative Analysis:**
- Writing style across chapters
- Tone consistency
- Pacing comparison
- Voice consistency

**Best Practices:**
- Run thematic analysis after first draft
- Use comparative analysis during revision
- Combine analysis types for comprehensive review

---

### Plot Analysis Suite

> Comprehensive plot structure analysis including arc detection and pacing.

Provides four dimensions of plot analysis:

**1. Arc Detection:**
Compares against classical structures:
- Hero's Journey
- Three-Act Structure
- Five-Act Structure
- Freytag's Pyramid

**2. Pacing Analysis:**
- Tempo measurement
- Tension curve analysis
- Info-dumping detection

**3. Conflict Mapping:**
- Internal conflicts
- External conflicts
- Interpersonal conflicts
- Conflict connections

**4. Trope Recognition:**
- Identifies tropes and clichés
- Recognizes subversions
- Genre-specific analysis

**Best Practices:**
- Run arc detection early in writing process
- Use pacing analysis for revision
- Map conflicts before major plot changes

---

### Scene Suggestions

> AI identifies missing narrative scenes and generates concrete proposals.

Fills narrative gaps through two-stage process:

**Gap Analysis:**
Identifies:
- Missing transitions between locations
- Unresolved plot threads
- Absent entities from Knowledge Base
- Time jumps without scenes
- Emotional gaps between chapters

**Scene Proposal Generation:**
For each gap, provides:
- Location suggestion
- Character list
- Scene goal
- Conflict source
- Emotional arc
- Beat-by-beat outline
- Word count estimate

**Severity Levels:**
- **Critical**: Major narrative gaps that confuse readers
- **Moderate**: Significant gaps dedicated readers notice
- **Minor**: Small gaps most readers fill in themselves

**Best Practices:**
- Run after major drafts or restructuring
- Prioritize critical gaps
- Use proposals as starting points, not prescriptions

---

### Story Generation

> AI-powered generation of plot ideas, twists, and character-driven plots.

Generates five types of story elements:

**1. Genre-Based Plot Suggestions:**
- Tailored to your novel's genre
- Balances conventions with freshness
- Includes premise and consequences

**2. Plot Twists:**
- Surprising but inevitable reveals
- Setup requirements and ripple effects
- Context-aware based on existing story

**3. Alternative Endings:**
- Range from hopeful to tragic
- Resolves different character arcs
- Shows thematic implications

**4. Character-Driven Plots:**
- Emerges from character motivations
- Identifies driving character and obstacles
- Shows effects on other characters

**5. Name Generation:**
- Context-aware for cultures and settings
- Avoids duplicates from Knowledge Base
- Supports multiple linguistic patterns

**Best Practices:**
- Provide rich Knowledge Base context
- Generate broadly, then narrow with seeds
- Give feedback to improve future suggestions

---

### Storyboard

> Compare written chapters against planned outlines with ripple analysis.

Two-level planning and tracking system:

**Sync Checking:**
Compares finished chapters against plans:
- **Synchronized**: Chapter matches plan
- **Deviated**: Drifted from plan (identifies how)
- **Abandoned**: Abandoned major planned elements
- **Impacted**: Affected by earlier chapter changes

**Ripple Analysis:**
Evaluates downstream effects of changes:
- Uses only chapter metadata (fast)
- Returns affected chapters with brief reasons
- Helps make informed structural decisions

**Best Practices:**
- Plan before writing (even brief outlines)
- Run sync checks after each chapter
- Use ripple analysis before major rewrites

---

### Voice Checker

> AI checks if dialogue matches character's established voice.

Maintains consistent character voices through:

**Voice Profile Extraction:**
- Formality level assessment
- Vocabulary pattern analysis
- Sentence structure preferences
- Emotional register identification
- Speech quirks detection

**Dialogue Analysis:**
Compares text against character profile:
- Match score (0-1)
- Specific feedback on mismatches
- Concrete rewrite suggestions

**Usage:**
```bash
narrare voice-checker check --text "dialogue" --character <id>
```

**Best Practices:**
- Build detailed character voice profiles
- Run checks after major dialogue passes
- Use low scores as opportunities for intentional changes

---

## Knowledge Base & Worldbuilding

### Knowledge Base Overview

> The structured memory system that powers Narrare's AI capabilities.

Foundation for all AI features with six entity types:

**Entity Types:**
1. **Characters**: People in your story with traits, relationships, arcs
2. **Locations**: Places where scenes occur with descriptions and connections
3. **Factions**: Organized groups with goals, structures, resources
4. **Objects**: Significant items with properties and histories
5. **Systems**: Abstract structures (magic, technology, economics)
6. **Timelines**: Temporal structures and event sequences

**Creation Methods:**
- **AI Interview**: Guided question-based creation (most powerful)
- **Manual Creation**: Direct entry with structured fields
- **From Templates**: Quick creation from patterns

**AI-Powered Features:**
- Entity suggestions based on existing content
- Character name generation
- Content enhancement proposals
- Automatic fact extraction

**Best Practices:**
- Start with core entities (protagonist, key locations)
- Use AI interviews for rich development
- Keep entries updated as story evolves
- Link related entities for better context

---

### Characters

> Create and manage the people who populate your story.

Comprehensive character management system:

**Character Profiles:**
- **Identity**: Name, aliases, basic demographics
- **Appearance**: Physical description, distinctive features
- **Personality**: Traits, motivations, fears, goals
- **Background**: History, relationships, formative events
- **Voice**: Speech patterns, vocabulary, verbal tics
- **Arc**: Character development trajectory

**Creation Methods:**
- **AI Interview**: Guided character development
- **Manual Entry**: Direct profile creation
- **Templates**: Quick character archetypes

**Character Relationships:**
- Family bonds, friendships, rivalries
- Professional connections, mentorships
- Romantic relationships, alliances
- Track relationship changes over story

**Best Practices:**
- Create detailed voice profiles for dialogue consistency
- Update character arcs as story evolves
- Link characters to locations and factions
- Use character interviews for deep development

---

### Worldbuilding

> Create and manage the rich world your characters inhabit.

Seven worldbuilding entity types:

**1. Locations:**
- Built: Cities, buildings, infrastructure
- Natural: Terrain, water features, landmarks
- Special: Magical spaces, underground, mobile

**2. Factions:**
- Political: Governments, movements, treaties
- Military: Armies, militias, guards
- Social: Religions, economic groups, cultures

**3. Objects:**
- Weapons, artifacts, tools
- Vehicles, mounts, flying machines
- Technological devices

**4. Systems:**
- Magic systems with rules and costs
- Technologies and capabilities
- Economies, legal systems, social hierarchies

**5. Timelines:**
- World history before story
- Story chronology
- Character histories
- Event sequences

**6. Languages:**
- Natural and constructed languages
- Dialects and codes
- Phonology, grammar, vocabulary

**7. Relationships:**
- Connections between all entity types
- Spatial, political, personal bonds
- Dynamic relationship mapping

**AI Assistance:**
- Worldbuilding suggestions and gap identification
- Consistency checking across entities
- Guided interviews for development
- Conflict and plot opportunity identification

**Best Practices:**
- Start broad (geography, major factions), go deep as needed
- Document rules clearly for systems
- Show world through story, not info-dumps
- Focus on story-relevant areas first

---

### Fact Extraction

> Extract verifiable facts from Knowledge Base and chapters for consistency checking.

Three-stage fact extraction system:

**Stage 1: Rule-Based Extraction:**
- Pulls facts from structured KB fields
- Extracts explicit statements
- High confidence, low false positives

**Stage 2: AI-Assisted Extraction:**
- Analyzes unstructured prose
- Identifies implicit facts
- Medium confidence, requires review

**Stage 3: Deduplication and Scoring:**
- Removes duplicate facts
- Assigns confidence levels (green/yellow/red)
- Resolves contradictions

**Fact Categories:**
- Character traits and relationships
- Location properties and connections
- Timeline markers and events
- Faction memberships and politics
- Backstory details and history
- System rules and limitations
- Plot facts and story events

**Best Practices:**
- Extract before consistency checks
- Re-extract after major KB updates
- Focus on low-confidence facts for review
- Extract for all entity types, not just characters

---

### Consistency Check

> Comprehensive consistency analysis across characters, timeline, and world facts.

Multi-dimensional consistency checking:

**Check Types:**
- **Character**: Behavior, voice, knowledge, abilities
- **Timeline**: Event sequencing, durations, ages
- **World**: Location properties, system rules, faction relationships
- **Plot**: Cause and effect, motivation chains
- **Knowledge**: What characters know vs. reader knows

**Analysis Process:**
1. Extract facts from KB and chapters
2. Compare related facts for contradictions
3. Flag inconsistencies with severity levels
4. Provide specific resolution suggestions
5. Track consistency scores over time

**Severity Levels:**
- **Error**: Impossible contradictions
- **Warning**: Likely inconsistencies
- **Info**: Minor discrepancies worth noting

**Best Practices:**
- Run after major writing sessions
- Check both within and across chapters
- Use warnings to guide revision priorities
- Update KB when fixing inconsistencies

---

### Semantic Timeline

> Automatically extract and visualize temporal events with AI-powered consistency checking.

Temporal consistency management system:

**Temporal Extraction:**
- Date expressions ("March 15, 2025")
- Time expressions ("at midnight", "dawn")
- Durations ("for three days", "a week-long journey")
- Temporal prepositions ("before", "after", "during")
- Ordinal sequences ("the second battle")

**Knowledge Base Integration:**
- Character birthdays and age calculations
- Historical events as timeline anchors
- Location temporal information
- User-defined timeline entities

**Consistency Checking:**
- Explicit contradictions ("A before B" vs "B before A")
- Implicit contradictions (duration conflicts, age impossibilities)
- Gaps and overlaps in event sequences
- Temporal loops and paradoxes

**Visualization Views:**
- Chronological: Events in temporal order
- Chapter: Events grouped by chapter
- Character: Timeline filtered by character
- Consistency: Color-coded by status

**Best Practices:**
- Rebuild after major edits
- Use manual events for anchors
- Check consistency in layers (chapter, arc, novel)
- Document temporal assumptions for complex stories

---

### Proactive Context Loading

> Automatically suggests relevant KB entries when you open chapters.

Smart context suggestion system:

**Three-Stage Pipeline:**
1. **Content Analysis**: Entity extraction, theme detection, frontmatter parsing
2. **KB Search**: Embedding-based search, similarity ranking, graph traversal
3. **Learning and Prioritization**: Weighted scoring (50% relevance, 30% usage, 20% recency)

**Feedback Loop:**
- Implicit feedback from acceptance/usage
- Explicit feedback from dismissals
- Learning algorithm improves suggestions over time

**Usage:**
- Suggestions appear automatically in editor panel
- CLI access for pre-writing planning
- MCP integration for conversational review

**Best Practices:**
- Keep KB entries updated and detailed
- Provide regular feedback for learning
- Use suggestions for planning, not just writing
- Combine with manual context selection

---

### Context Assembly

> The intelligent context system that powers AI generation.

Context management for AI writing assistance:

**Context Tiers:**
1. **Immediate Context**: Current chapter content and frontmatter
2. **Recent History**: Last 3-5 chapters with relevance scoring
3. **Knowledge Base**: Character profiles, location details, world facts
4. **Proactive Suggestions**: AI-relevant entries based on patterns
5. **Pinned Items**: Manually selected important context

**Assembly Process:**
- Gathers context from all tiers
- Ranks by relevance and recency
- Applies token limits intelligently
- Formats for optimal AI understanding

**User Controls:**
- Pin important KB entries
- Dismiss irrelevant suggestions
- Adjust context scope per chapter
- Review context before generation

**Best Practices:**
- Pin critical characters and locations for key scenes
- Review proactive suggestions regularly
- Use narrower context for focused scenes
- Widen context for scenes connecting multiple plot threads

---

## Project Management

### Chapters

> Create, organize, and manage your novel's chapters.

Chapter management system with rich metadata:

**Chapter Structure:**
- **Content**: Full chapter text with version history
- **Frontmatter**: Structured metadata (title, status, POV, location)
- **Outline**: Planned scenes and beats
- **Notes**: Author reminders and research links

**Chapter Status:**
- **Outline**: Planned but not written
- **Draft**: Initial complete version
- **Revision**: Undergoing edits
- **Final**: Complete and polished

**Organization Features:**
- Drag-and-drop reordering
- Chapter grouping by arcs or volumes
- Bulk operations (status changes, exports)
- Chapter templates for consistency

**Analytics Integration:**
- Word count tracking
- Writing time measurement
- Progress visualization
- Streak monitoring

**Best Practices:**
- Use consistent naming conventions
- Update frontmatter as you write
- Group related chapters in arcs
- Use chapter templates for series consistency

---

### Volume Management

> Organize longer works into volumes with independent statistics and context switching.

Multi-volume novel organization:

**Volume Structure:**
- **Metadata**: Title, description, ordinal position
- **Chapters**: Volume-scoped chapter organization
- **Statistics**: Independent word counts and progress
- **Context Scope**: Prioritizes current volume's content

**Volume Switching:**
- Preserves state in each volume
- Adjusts context assembly scope
- Maintains separate writing histories
- Seamless switching between volumes

**Shared vs. Volume-Scoped:**
- **Shared**: Knowledge Base, Style Profile, character data
- **Volume-Scoped**: Chapters, word counts, context history

**Best Practices:**
- Plan volume structure early (arcs, time periods, POVs)
- Set word count targets per volume
- Use consistency checks across volumes
- Keep Knowledge Base unified across volumes

---

### Import

> Bring existing content into Narrare from various sources.

Content import system with AI-powered classification:

**Import Modes:**
1. **Directory Import**: Multiple Markdown files with optional YAML frontmatter
2. **File Upload**: Individual plain text or Markdown files

**Import Process:**
1. **Source Selection**: Choose files or directory
2. **Content Analysis**: AI analyzes and classifies content
3. **Review Detected Files**: Confidence scores and classification levels
4. **Configure Post-Import Actions**: KB building, embeddings, fact extraction
5. **Execute and Monitor**: Progress tracking and error handling

**Classification Levels:**
- **AUTO**: High confidence automatic classification
- **REVIEW**: Medium confidence, needs human review
- **MANUAL**: Low confidence, requires manual setup

**Post-Import Actions:**
- Build Knowledge Graph from imported content
- Generate embeddings for semantic search
- Extract facts for consistency checking
- Auto-summarize chapters

**Best Practices:**
- Organize files before importing
- Use consistent naming conventions
- Start with small batches to test classification
- Enable post-import actions for best integration

---

### Export

> Publish your novel in multiple formats for sharing, submission, or publication.

Flexible export system supporting multiple formats and scopes:

**Export Scopes:**
- **Full Novel**: All chapters with frontmatter
- **Chapter Selection**: Custom chapter ranges
- **Knowledge Base**: Character sheets, worldbuilding, full KB
- **Custom Selection**: User-defined content sets

**Supported Formats:**
- **Markdown**: Plain text with formatting syntax
- **Plain Text**: Clean text without formatting
- **PDF**: Formatted document for print/digital
- **EPUB**: E-book format for readers
- **DocX**: Microsoft Word document
- **JSON**: Structured data for processing

**Export Configuration:**
- **Metadata Options**: Include/exclude frontmatter and project data
- **Formatting Controls**: Font, margins, styling preferences
- **Front/Back Matter**: Title pages, copyright, author notes
- **Conditional Exports**: Include/exclude based on status or tags

**Destination Options:**
- Project directory export
- Custom location selection
- Cloud storage integration (coming)

**Best Practices:**
- Run consistency checks before exporting
- Review metadata for accuracy
- Use appropriate format for target audience
- Test exports before final submission

---

### Filesystem Sync

> Export project data as structured Markdown files for backup and version control.

Project synchronization with local filesystem:

**Export Scopes:**
- **Full Project**: Chapters, KB entries, metadata
- **Chapters Only**: Chapter content with frontmatter
- **Knowledge Base Only**: KB entries in Markdown format

**Exported Structure:**
```
project-export/
├── chapters/
│   ├── chapter-1-title.md
│   └── chapter-2-title.md
├── knowledge-base/
│   ├── characters/
│   ├── locations/
│   └── factions/
├── metadata/
│   ├── novel-info.md
│   └── export-manifest.json
```

**YAML Frontmatter:**
Each exported file includes structured metadata:
- Chapter: title, status, POV, location, word count
- Character: basic info, relationships, current status
- Location: type, description, connected places

**Use Cases:**
- Version control with Git
- Offline editing in external tools
- Backup and archival
- Migration between systems

**Best Practices:**
- Sync after major writing sessions
- Use Git for tracking changes
- Review exported files before committing
- Combine with regular backup strategies

---

### Settings

> Configure Narrare to match your writing workflow and preferences.

Comprehensive settings management:

**AI Provider Configuration:**
- Provider selection (OpenAI, Anthropic, others)
- API key management with validation
- Model assignment per task type
- Embedding model configuration
- Two-tier override system (user defaults → project overrides)

**AI Prompt Management:**
- View and customize system prompts
- Genre-specific prompt modifications
- Style preference instructions
- Prompt reset to defaults
- Cascade system (bundled → user customizations)

**Appearance:**
- Theme selection (Light, Dark, System)
- Real-time theme switching
- OS theme following

**Language:**
- Interface language (English, German, French)
- Complete UI translation coverage
- Language-specific behavior

**Editor Preferences:**
- Font size (12px-24px)
- Line height (1.2x-2.0x)
- Font family (Serif, Sans-serif, System)
- Real-time preview updates

**Export Defaults:**
- Default format selection
- Metadata inclusion options
- Frontmatter preservation settings

**Token Limits:**
- Per-feature token budgets
- User and project-level limits
- Cost control mechanisms

**Feature Flags:**
- Enable/disable AI features per project
- Cost control options
- Workflow customization

**Account Information:**
- Email and user ID display
- Account status information
- Read-only account details

**Storage:**
- Frontend settings (localStorage)
- Server-side settings (API sync)
- Project-level overrides

**Best Practices:**
- Configure AI provider before starting
- Use project-level overrides for genre differences
- Experiment with editor settings for comfort
- Review settings after updates

---

### Keyboard Shortcuts

> Work faster with comprehensive keyboard shortcuts for every action.

Complete shortcut system for power users:

**Editor Shortcuts:**
- **Text Editing**: Save, Undo/Redo, Cut/Copy/Paste, Select All
- **Text Formatting**: Bold, Italic, Underline, Strikethrough
- **Navigation**: Find, Go to Next/Previous, Indent/Outdent
- **AI Writing**: Command Palette, Accept/Dismiss suggestions, Continue/Rewrite
- **Context Panel**: Toggle, Accept/Reject all, Navigate items
- **Chapter Navigation**: Next/Previous chapter, Jump to chapter, Create new

**Dashboard Shortcuts:**
- **Global Navigation**: Go to Dashboard/Editor/KB/Settings
- **Dashboard Actions**: Focus lists, Create items, Open dialogs
- **Chapter List**: Navigate, Select multiple, Delete, Open

**Knowledge Base Shortcuts:**
- **KB Navigation**: Go to Characters/Locations/Factions/Objects/Timelines
- **Entry Actions**: Create, Edit, Delete, Search
- **Search and Filter**: Focus search, Navigate results, Reset filters

**Modal Shortcuts:**
- **General**: Close modal, Confirm action, Navigate fields
- **Specific**: Chapter interview, New character dialogs

**System Shortcuts:**
- **Window Management**: New window, Close, Quit, Settings
- **Tab Management**: New/Close/Next/Previous tab, Jump to tab

**Platform-Specific:**
- **macOS**: System integration, text input shortcuts
- **Windows/Linux**: Alternative shortcuts, function keys

**Custom Shortcuts:**
- Create custom key combinations
- Conflict detection and resolution
- Disable unused shortcuts

**Productivity Tips:**
- Rapid chapter creation workflows
- Quick edit cycles
- AI-assisted revision patterns
- Focus mode configurations

**Accessibility:**
- Keyboard-only navigation
- Screen reader support
- Visual accessibility options

**Command Palette:**
- Fuzzy search across all tools
- Tool categorization
- Quick access to 17 writing tools

**Best Practices:**
- Learn core shortcuts first
- Customize for your workflow
- Use Command Palette for discovery
- Enable shortcut hints while learning

---

### Writing Analytics

> Track your writing progress with detailed statistics, streaks, and session data.

Comprehensive writing progress tracking:

**Session Tracking:**
- **Session Types**: Writing, Editing, Review
- **Automatic Tracking**: Start/end times, word counts, duration
- **Session History**: Complete record of all writing sessions

**Statistics Calculated:**
- **Daily Stats**: Words written, sessions, duration
- **Weekly Stats**: Aggregated totals with daily averages
- **Streaks**: Current streak, longest streak, last write date
- **Progress**: Cumulative word count, target completion estimates

**Progress Tracking:**
- Daily word count additions
- Cumulative progress charts
- Remaining words to target
- Implied completion dates based on pace

**Usage:**
```bash
narrare analytics session start --novel <id>
narrare analytics session end <session-id> --word-count 42500
narrare analytics stats daily --novel <id> --days 30
narrare analytics streak --novel <id>
narrare analytics progress --novel <id>
```

**Best Practices:**
- Start/end sessions consistently for accurate data
- Focus on streaks over daily totals for habit building
- Review weekly stats to identify productivity patterns
- Set realistic word count targets for your genre

---

### Cost Tracking

> Monitor AI usage costs and set budgets to control expenses.

AI cost management and monitoring:

**Usage Tracking:**
- Token consumption per feature
- Cost calculation by provider/model
- Historical usage patterns
- Project vs. user-level tracking

**Budget Management:**
- Monthly spending limits
- Per-feature budget caps
- Warning thresholds
- Automatic usage suspension at limits

**Cost Analysis:**
- Cost per word written
- Most expensive features
- Usage efficiency metrics
- Provider cost comparisons

**Reporting:**
- Daily/weekly/monthly cost summaries
- Usage breakdown by feature
- Project cost allocation
- Export for accounting

**Best Practices:**
- Set conservative budgets initially
- Monitor costs during heavy usage periods
- Use cost-efficient models for routine tasks
- Review usage patterns for optimization opportunities

---

## Integration & Tools

### MCP Integration (Claude Desktop)

> Connect Narrare to Claude Desktop and other AI tools via Model Context Protocol.

MCP enables AI assistants to use Narrare capabilities through natural language:

**Setup Process:**
1. Run Narrare API services
2. Configure Claude Desktop with MCP server
3. Set up authentication token
4. Choose transport mode (STDIO/HTTP)

**Available MCP Tools:**

**Knowledge Base:**
- `get_character`, `create_character`, `update_character`
- `get_location`, `create_location`, `search_knowledge_base`
- `list_entities`, `get_entity_relationships`

**Writing Tools:**
- `write_chapter`, `continue_writing`, `rewrite_selection`
- `generate_outline`, `suggest_scene`, `unblock_writer`

**Context & Analysis:**
- `get_proactive_suggestions`, `check_consistency`
- `analyze_plot`, `check_pov`, `analyze_sentiment`

**Projects & Sessions:**
- `list_novels`, `get_chapter`, `create_chapter`
- `start_session`, `end_session`, `get_analytics`

**Example Conversations:**
- "Create a character named Elara who's a disgraced mage"
- "Continue Chapter 3 where Elara confronts the Council"
- "Check my novel for consistency issues"
- "Generate three plot twists involving the mentor character"

**Best Practices:**
- Use for conversational exploration of ideas
- Combine multiple tools in single conversations
- Provide context for better results
- Use for planning as well as writing

---

### A2A Integration

> Connect with external AI agents and services through Agent-to-Agent protocol.

A2A enables interoperability with other AI systems:

**Supported Agents:**
- Writing assistants and editors
- Research and fact-checking services
- Publishing and submission tools
- Collaboration and review platforms

**Integration Types:**
- **Read Access**: Export content to external agents
- **Write Access**: Import suggestions and edits
- **Bidirectional**: Full collaborative workflows

**Security:**
- Agent authentication and authorization
- Data access controls
- Audit logging of agent interactions
- Revocable access permissions

**Use Cases:**
- Professional editing services
- Beta reader platforms
- Publishing submission systems
- Research integration

**Best Practices:**
- Review agent permissions carefully
- Test integrations with sample content
- Monitor agent activity logs
- Revoke access for unused agents

---

### Research Tools

> Search the web, verify facts, and explore cultural context without leaving your writing environment.

Integrated research capabilities:

**Web Search:**
- General web searching for information
- Result summaries with source links
- Search history for reference
- CLI and web interface access

**Fact Verification:**
- Claim validation against multiple sources
- Confidence scoring for fact accuracy
- Contradiction identification
- Source citation and links

**Historical Research:**
- Period-specific information gathering
- Anachronism detection
- Historical accuracy checking
- Contextual historical details

**Cultural Research:**
- Cultural practices and traditions
- Sensitivity and representation guidance
- Authentic portrayal assistance
- Cross-cultural comparison tools

**Research Management:**
- Save sources to Knowledge Base
- Organize research by category
- Search within saved research
- Export research findings

**Best Practices:**
- Verify critical facts through multiple sources
- Save important research to Knowledge Base
- Use cultural research for authentic representation
- Combine with sensitivity reader for review

---

### Prompting Locally

> Customize AI behavior by overriding system prompts in your project.

Local prompt customization system:

**Prompt Cascade:**
1. **Project Level**: `.narrare/prompts/` (highest priority)
2. **Global Level**: User-wide configuration (coming soon)
3. **Bundled Level**: Default prompts (fallback)

**Customization Process:**
1. Create `.narrare/prompts` directory
2. Identify prompt to override
3. Create corresponding file path
4. Copy and modify default content
5. Changes apply immediately

**Use Cases:**
- Genre-specific instructions
- Personal style preferences
- Tone guidelines
- Language specifications

**MCP Integration:**
- Local prompts work with MCP tools
- Custom prompts enhance Claude Desktop integration
- Project-specific prompt variations

**Best Practices:**
- Copy default before modifying
- Test custom prompts incrementally
- Document prompt changes for collaborators
- Reset to defaults if issues arise

---

### Rejection Learning

> The AI learns from your feedback to improve future suggestions over time.

Adaptive AI system that learns from user preferences:

**Feedback Collection:**
- **Accept**: Suggestion was useful and used
- **Reject**: Suggestion was not useful
- **Modify**: Suggestion was useful but needed changes

**Pattern Analysis:**
- **Style Preferences**: Sentence structure, descriptive density, dialogue patterns
- **Content Preferences**: Thematic interests, genre leanings, character types
- **Structure Preferences**: Scene length, chapter organization, pacing patterns

**Learning Application:**
- **Positive Context**: Highlights preferred styles in generation
- **Negative Constraints**: Explicitly avoids rejected patterns
- **Continuous Improvement**: Adapts over time based on feedback

**Usage:**
```bash
narrare learning feedback submit --suggestion <id> --action accept
narrare learning feedback submit --suggestion <id> --action reject --reason "too predictable"
narrare learning feedback get --novel <uuid>
```

**Best Practices:**
- Be consistent with feedback for pattern recognition
- Explain rejections when possible for better learning
- Review preference profile periodically
- Reset preferences when changing creative direction

---

### Name Generator

> Generate context-aware names for characters, locations, and objects.

Intelligent name generation system:

**Generation Pipeline:**
1. **Template Selection**: Genre-appropriate patterns
2. **Cultural Filtering**: Consistent with worldbuilding
3. **KB Deduplication**: Avoids existing names

**Supported Types:**
- **Characters**: First names, surnames, full names
- **Locations**: Cities, regions, landmarks
- **Objects**: Artifacts, weapons, vehicles

**Cultural Context:**
- Fantasy: Elvish, Dwarvish, Orcish patterns
- Sci-Fi: Technological, alien, corporate naming
- Historical: Period-appropriate cultural names
- Modern: Contemporary naming conventions

**Usage:**
```bash
narrare generation names --type character --culture elvish
narrare generation names --type location --culture medieval-french
```

**Best Practices:**
- Define cultures before generating names
- Generate in batches for options
- Check against existing KB entries
- Use pronunciation guides for fantasy names

---

### Graph Visualization

> Interactive visualization of the Knowledge Graph showing entity relationships.

Visual knowledge exploration system:

**Graph Elements:**
- **Nodes**: Characters, locations, factions, objects, timelines
- **Edges**: Relationships, connections, dependencies
- **Layouts**: Force-directed, concentric, layered, breadth-first

**Interactive Features:**
- **Filtering**: By node type, relationship type, attributes
- **Path Highlighting**: Show connections between entities
- **Node Details**: Expandable information panels
- **Export Options**: PNG/SVG export (planned feature)

**Usage Scenarios:**
- Explore character relationship networks
- Visualize faction alliances and conflicts
- Track location connections and travel routes
- Identify isolated entities or missing connections

**Technical Details:**
- Powered by Cytoscape.js
- Optimized for up to 500 nodes
- Real-time interaction and updates
- Responsive design for various screen sizes

**Best Practices:**
- Use for understanding complex relationships
- Filter to focus on specific story elements
- Combine with timeline for temporal context
- Export for documentation and reference

---

### Chapter Summary

> AI-generated summaries of chapters with configurable detail levels.

Automated chapter summarization system:

**Summary Types:**
- **Brief**: One-paragraph overview
- **Standard**: Multi-paragraph summary with key events
- **Detailed**: Comprehensive summary including subplots and character development

**Content Analysis:**
- Plot progression and major events
- Character appearances and development
- Setting changes and introductions
- Thematic elements and motifs
- Dialogue highlights and key quotes

**Configuration Options:**
- Summary length and detail level
- Focus areas (plot, characters, themes)
- Inclusion/exclusion criteria
- Output format (Markdown, plain text)

**Usage:**
- Chapter overview for quick reference
- Series continuity checking
- Beta reader preparation
- Marketing and synopsis development

**Best Practices:**
- Use standard summaries for most purposes
- Generate detailed summaries for complex chapters
- Review and edit summaries for accuracy
- Update summaries after major revisions

---

### Background Tasks

> Automated processes that run in the background to enhance your writing experience.

Continuous improvement system:

**Task Types:**
- **Embedding Generation**: Create semantic search vectors for new content
- **Fact Extraction**: Automatically extract facts from new chapters
- **Consistency Monitoring**: Background checking for new inconsistencies
- **Knowledge Graph Updates**: Maintain entity relationships

**Task Management:**
- Queue system for task scheduling
- Priority levels for different task types
- Progress tracking and status updates
- Error handling and retry mechanisms

**Performance Optimization:**
- Efficient resource usage
- Configurable task schedules
- Batch processing for multiple operations
- Caching to avoid redundant work

**User Controls:**
- Enable/disable specific background tasks
- Configure task scheduling preferences
- Monitor task status and progress
- Adjust resource allocation

**Best Practices:**
- Keep background tasks enabled for best experience
- Monitor task status if experiencing performance issues
- Schedule heavy tasks during off-hours
- Review task results for accuracy

---

## Writing Workflows

> Transform your ideas into high-quality prose through iterative AI-human collaboration.

Structured writing process from concept to completion:

### From Idea to Outline

1. **The Spark**: Record rough story concept in Project Setup
2. **Drafting the Outline**: Use AI-assisted planning tools to expand concept
3. **Volume & Chapter Planning**: Break outline into manageable sections

### Drafting Chapters

1. **Proposal Generation**: AI suggests context based on existing text and KB
2. **Refining the Context**: Accept, reject, or modify AI suggestions
3. **Progressive Drafting**: Use "Continue" or "Draft from Outline" with streaming text

### The Feedback Loop

- **Co-Authoring**: Brainstorm specific dialogue or scenes with version control
- **Multi-Draft Generation**: Compare 2-5 variations with labeled strengths/weaknesses
- **Voice Checking**: Ensure character voice consistency
- **Rejection Learning**: AI learns from your modifications and adapts

### Best Practices

- **Control**: Maintain control over every sentence and detail
- **Knowledge Base**: Build comprehensive KB for AI context
- **Privacy**: Work remains private with local/self-hosted options
- **Style**: Use Voice Cloning to match your writing style

---

## Conclusion

Narrare provides a comprehensive suite of tools for every stage of the writing process, from initial concept through final revision. The system combines powerful AI assistance with maintaining author control, ensuring that technology serves creativity rather than replacing it.

Key strengths include:
- **Unified Knowledge Base** for story consistency
- **Multi-language Support** (English, German, French)
- **Flexible Integration** (Web UI, CLI, MCP, API)
- **Adaptive Learning** that improves with use
- **Comprehensive Analysis** tools for quality improvement
- **Privacy-Focused** architecture with local deployment options

Whether you're a plotter who needs detailed outlines or a pantser who discovers the story through writing, Narrare adapts to your workflow while providing the structure and consistency tools needed to complete a polished novel.

---

*This documentation combines all individual feature documentation into a comprehensive reference guide. For detailed usage instructions on specific features, refer to the individual feature documents in the docs/user/features/ directory.*
