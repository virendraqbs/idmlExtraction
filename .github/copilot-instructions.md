# AI Coding Assistant Guidelines for CL-PDF-Extraction

This is a **PDF-to-JSON extraction system** for educational curriculum content. An admin uploads PDF files (e.g., Student Resource Books, Practice Books, Teacher Implementation Guides) and the system:
1. Validates the Gemini API key (health check)
2. Processes PDFs page-by-page using Google's Gemini API
3. Extracts structured data into JSON conforming to the CL-Json-Schema

## Critical Architecture

### Schema System (CL-Json-Schema)

The content model uses **two parallel hierarchies**:

**Logical Content (Pedagogy)**
```
Resource (SRB/SPB/TIG) → Module (resourceId link) → Topic → Lesson → Activity → Task → Stem
```

**Physical Layout (Presentation)**
```
Resource → Pages → ContentBlocks (references to any logical level)
```

**Key Design Pattern**: Modules contain `resourceId` linking to their parent Resource for state/standards context. This enables content hierarchy independence from physical page layout. See [ARCHITECTURE.md](CL-Json-Schema/ARCHITECTURE.md#content-hierarchy).

### Core Schema Types
- **Content**: `resource.json`, `module.json`, `topic.json`, `lesson.json`, `activity.json`, `task.json`, `stem.json`
- **Layout**: `page.json` (references content blocks for display)
- **Standards**: `standard.json`, `standards-block.json` (supports CCSS, CA_CCSS, TEKS, BEST)
- **Media**: `image.json` (reusable assets)
- **Support**: `response-area.json`, `scaffolding.json`, `instructional-segment.json`

### Schema Validation Rules
1. **Explicit Linking**: All relationships use UUIDs with typed references (id + type + sequenceNumber)
2. **Parent-Child Relationships**: Direct parent reference (e.g., lesson has `moduleId`, activity has `lessonId`) for validation & querying
3. **Standards Single-Link**: Each lesson currently links to ONE standards-block. Amendments needed for multi-state standards
4. **Enum Consistency**: Use `enums.json` for activity types, page types, standards bodies, etc. ([enums.json](CL-Json-Schema/enums.json))
5. **Resource Context**: Modules inherit state/standards body context from their Resource via `resourceId`

## Gemini API Integration Pattern

**Expected Flow**:
1. Admin provides PDF file + resource metadata (type, grade level, state, standards body)
2. Health check validates Gemini API key (availability & quota)
3. For each PDF page:
   - Extract raw content using Gemini vision API
   - Prompt Gemini to return structured JSON matching the schema
   - Validate output against schema (all required fields populated)
   - Fallback/retry if Gemini returns incomplete data

**Critical Constraint**: Gemini MUST return ALL values available in the schema. Incomplete or null values indicate:
- Prompt clarity issues (refine the extraction prompt)
- Page quality issues (OCR failure, unclear content)
- Schema mismatch (Gemini cannot infer a required field)

## Key Files & Conventions

| Path | Purpose |
|------|---------|
| `CL-Json-Schema/schemas/` | JSON schema definitions (source of truth) |
| `CL-Json-Schema/README.md` | Quick start & feature overview |
| `CL-Json-Schema/ARCHITECTURE.md` | Dual hierarchy diagrams, content organization rationale |
| `CL-Json-Schema/DATA_ARCHITECTURE.md` | File organization patterns for implementation |
| `CL-Json-Schema/IMPLEMENTATION_EXAMPLES.md` | Full worked examples of Resource, Module, Topic, Activity chains |
| `CL-Json-Schema/DESIGN_DOCUMENTATION.md` | Design principles (separation of concerns, explicit linking, extensibility) |
| `sourceFile/` | Sample PDFs (A1_T13_L1.pdf, A1_T1_L2.pdf, etc.) for testing |

## Important Patterns from Schema Design

1. **Replication Model**: Content is **replicated per resource** (not reused) during ingestion. This allows independent validation and adjustments without re-processing PDFs.
2. **Enumeration Strictness**: Activity types, page types, direction types must match `enums.json` exactly. Misclassification during extraction is a common error.
3. **Localization Context**: Resources carry `metadata.localizationInfo` (state, locale). Modules inherit via `resourceId` for standards alignment.
4. **Flexible Scaffolding**: `scaffolding.json` and `activity-goals.json` provide optional differentiation layers—use when content indicates multiple complexity levels.

## Debugging Checklist

- [ ] Is Gemini returning valid JSON matching schema structure?
- [ ] Do all UUIDs in relationships exist in the target entity?
- [ ] Are `sequenceNumber` fields consistent within arrays?
- [ ] Are enumeration values (activity type, page type, etc.) in `enums.json`?
- [ ] Is `resourceId` present in every Module, linking to a valid Resource?
- [ ] Do pages only reference content blocks that exist in the resource's module hierarchy?
- [ ] Are all required properties populated (no nulls for non-optional fields)?

## References

- **Schema Source**: [schemas/](CL-Json-Schema/schemas/) directory (browse by category: common, content, instructional-guide, media, resource, standards, extraction)
- **Example Workflow**: [IMPLEMENTATION_EXAMPLES.md](CL-Json-Schema/IMPLEMENTATION_EXAMPLES.md#complete-lesson-example) — Grade 4 Math with full resource, module, topic, lesson, activity, task, stem chain
- **Data Organization**: [DATA_ARCHITECTURE.md](CL-Json-Schema/DATA_ARCHITECTURE.md#directory-structure) — recommended folder structure for ingested content
