# Design Documentation

## Overview

The JSON schema is designed to model complex educational materials across three interconnected resource types while maintaining flexibility, clarity, and standards alignment. This document explains the key design principles, decisions, and rationales behind the schema architecture.

---

## Design Principles

### 1. Hierarchical Organization
**Principle**: Content is organized in a clear, predictable hierarchy from high-level containers to atomic content elements.

**Rationale**:
- Mirrors how educators conceptualize curriculum organization
- Enables efficient navigation and querying
- Supports progressive disclosure of complexity
- Facilitates content reuse and modularization

**Implementation**:
```
Resource → Module → Topic → Lesson → Activity → Task → Stem
```

Each level has a specific purpose and scope, preventing ambiguity about where content belongs.

---

### 2. Separation of Concerns
**Principle**: Different aspects of content (structure, presentation, pedagogy, standards) are modeled separately but linked.

**Rationale**:
- Allows independent evolution of each concern
- Enables different teams to work on different aspects
- Supports multiple presentation formats from same content
- Facilitates content reuse across contexts

**Implementation**:
- **Structural**: module.json, topic.json, lesson.json (content hierarchy)
- **Presentation**: page.json (physical layout)
- **Pedagogical**: activity.json, instructional-segment.json (teaching approach)
- **Standards**: standard.json, standards-block.json (alignment)
- **Media**: image.json (visual assets)

---

### 3. Explicit Linking
**Principle**: All relationships between entities are explicitly defined using UUIDs and typed references.

**Rationale**:
- Prevents ambiguity in relationships
- Enables bidirectional queries
- Supports data integrity validation
- Facilitates content updates without breaking references

**Implementation**:
```json
{
  "activities": [
    {
      "id": "activity-uuid",
      "type": "ACTIVITY",
      "sequenceNumber": 1
    }
  ]
}
```

Every reference includes:
- **id**: UUID of referenced entity
- **type**: Entity type (from ReferenceType enum)
- **sequenceNumber** (when order matters): Explicit ordering

---

### 4. Teacher-Student Synchronization
**Principle**: Teacher and student content are separate but explicitly linked, allowing different perspectives on the same content.

**Rationale**:
- Teachers need additional information students shouldn't see
- Maintains clear separation between teacher and student views
- Enables independent updates to teacher guidance
- Supports differentiation and scaffolding

**Implementation**:
- Student content stands alone
- Teacher content includes `teacherGuidance` properties
- Links use `TeacherStudentLink` metadata structure
- Relationship types (MIRRORS, EXTENDS, SUPPORTS, etc.) clarify connection

---

### 5. Flexible Standards Alignment
**Principle**: Standards can be linked at multiple levels of granularity and support multiple standards bodies.

**Rationale**:
- Different states and countries use different standards
- Standards may apply at lesson, activity, or task level
- Some content addresses multiple standards simultaneously
- Standards frameworks evolve over time

**Implementation**:
- `StandardsBody` enum: CCSS, CA_CCSS, TEKS, BEST
- Standards can be linked at resource, module, lesson, or activity level
- `StandardsBlock` provides contextualized groupings
- Individual `Standard` objects are reusable across content

---

### 6. Rich Metadata
**Principle**: Content includes comprehensive metadata to support publishing, accessibility, localization, and analytics.

**Rationale**:
- Educational content has complex lifecycle (authoring, review, publication)
- Accessibility is legally required and pedagogically important
- Content must be localizable for different markets
- Analytics and tracking require rich metadata

**Implementation**:
- `PublishingMetadata`: Version control, review status
- `AccessibilityInfo`: Screen reader support, alt text, color contrast
- `LocalizationInfo`: Language, locale, translation status
- `PacingEstimate`: Time estimates for planning

---

### 7. Enumerated Types
**Principle**: Use enumerated types for categorization to ensure consistency and enable validation.

**Rationale**:
- Prevents typos and inconsistencies
- Enables dropdown UIs for content creation
- Facilitates querying and filtering
- Documents valid options explicitly

**Implementation**:
- Comprehensive `enums.json` file
- Enums for: resource types, page types, activity types, task types, image types, standards bodies, etc.
- Clear naming conventions (e.g., `SRB_` prefix for Student Resource Book pages)

---

### 8. Extensibility
**Principle**: Schema is designed to accommodate future additions without breaking existing content.

**Rationale**:
- Educational requirements evolve
- New content types emerge
- Additional standards bodies may be needed
- New pedagogical approaches develop

**Implementation**:
- Optional properties for advanced features
- Enum extensibility (new values can be added)
- Flexible `metadata` objects
- Generic `Reference` type for future entity types

---

## Key Design Decisions

### Decision 1: Three-Book Model
**Decision**: Model three distinct resource types rather than a single generic resource.

**Options Considered**:
1. Single generic resource with content type property
2. Three separate, unrelated schemas
3. Three resources with shared structure and explicit linking ✓

**Rationale**:
- Student Resource Books, Practice Books, and Teacher Guides have different purposes
- They share structure but have unique properties
- Explicit linking enables teacher-student synchronization
- Separate types enable type-specific validation

**Trade-offs**:
- ✅ Clear separation of concerns
- ✅ Type-safe linking
- ❌ Some redundancy in schema definitions
- ❌ More complex to maintain consistency

---

### Decision 2: Page vs. Content Separation
**Decision**: Separate `page.json` (presentation) from content schemas (structure).

**Options Considered**:
1. Embed all content directly in pages
2. Pages reference content blocks ✓
3. No page concept, only content hierarchy

**Rationale**:
- Content structure (lessons, activities) is conceptual, not physical
- Same content may appear on different pages in different editions
- Digital presentations may not have "pages"
- Separating allows content reuse across presentations

**Trade-offs**:
- ✅ Content reuse across presentations
- ✅ Supports digital and print
- ✅ Easier to update content without changing layout
- ❌ More complex queries to find content on specific pages

---

### Decision 3: Standards Block vs. Direct References
**Decision**: Create `StandardsBlock` as an intermediate grouping rather than direct lesson-to-standard links.

**Options Considered**:
1. Direct lesson → standards references
2. Standards Block grouping with context ✓
3. Standards embedded in lesson objects

**Rationale**:
- Standards often come with explanatory text (conceptual overlays)
- Same standards may be presented differently for different contexts
- Standards Block can be reused across lessons
- Allows for state-specific customization

**Trade-offs**:
- ✅ Richer contextualization
- ✅ Reusability
- ✅ State-specific customization
- ❌ Extra level of indirection
- ❌ More entities to manage

---

### Decision 4: Task-Stem Decomposition
**Decision**: Split tasks into tasks and stems rather than making stem a property.

**Options Considered**:
1. Single "question" entity
2. Task with embedded stems
3. Separate task and stem entities ✓

**Rationale**:
- Many tasks have multiple parts (a, b, c)
- Each stem may have its own image, response area
- Enables fine-grained reuse
- Supports complex multi-part problems

**Trade-offs**:
- ✅ Maximum flexibility
- ✅ Fine-grained asset management
- ✅ Supports complex problems
- ❌ More entities to manage
- ❌ Deeper hierarchy

---

### Decision 5: Instructional Prompt vs. Embedded Guidance
**Decision**: Create separate `InstructionalPrompt` entities rather than embedding all guidance in content.

**Options Considered**:
1. All teacher guidance embedded in activity/lesson objects
2. Separate instructional prompt entities ✓
3. External documentation with no schema

**Rationale**:
- Prompts can apply to multiple content elements
- Prompts have their own lifecycle (created/updated independently)
- Enables querying all prompts of a certain type
- Supports different presentation styles (sidebar, box, inline)

**Trade-offs**:
- ✅ Reusability
- ✅ Independent lifecycle
- ✅ Flexible presentation
- ❌ More references to manage
- ❌ Potential for orphaned prompts

---

### Decision 6: UUID vs. Compound Keys
**Decision**: Use UUIDs for all entity identifiers rather than compound keys.

**Options Considered**:
1. Compound keys (e.g., moduleNumber + topicNumber + lessonNumber)
2. UUIDs ✓
3. Auto-incrementing integers

**Rationale**:
- UUIDs enable distributed content creation
- No need to coordinate ID assignment
- Content can be created offline
- Prevents ID conflicts during merges

**Trade-offs**:
- ✅ Distributed authoring
- ✅ No coordination needed
- ✅ Prevents conflicts
- ❌ Less human-readable
- ❌ Larger storage requirement

---

### Decision 7: Sequence Numbers on References
**Decision**: Include explicit `sequenceNumber` in reference objects rather than relying on array order.

**Options Considered**:
1. Array order implies sequence
2. Explicit sequenceNumber in references ✓
3. Separate ordering entity

**Rationale**:
- Array order can be fragile during edits
- Explicit numbering enables reordering without changing arrays
- Allows gaps for future insertions
- Makes sequencing explicit and queryable

**Trade-offs**:
- ✅ Explicit and queryable
- ✅ Enables easy reordering
- ✅ Supports gaps
- ❌ Redundant information
- ❌ Risk of inconsistency with array order

---

### Decision 8: Image as Separate Entity
**Decision**: Make images separate entities with rich metadata rather than simple URL properties.

**Options Considered**:
1. Simple URL string properties
2. Embedded image objects
3. Separate image entities with references ✓

**Rationale**:
- Images need rich metadata (alt text, copyright, dimensions)
- Same image may be used in multiple places
- Images have their own lifecycle
- Supports asset management and reuse

**Trade-offs**:
- ✅ Rich metadata
- ✅ Reusability
- ✅ Asset management
- ✅ Accessibility support
- ❌ More entities to manage
- ❌ Extra level of indirection

---

## Architectural Patterns

### 1. Reference Pattern
Used throughout the system for linking entities:

```json
{
  "id": "uuid-of-referenced-entity",
  "type": "ACTIVITY",
  "sequenceNumber": 1
}
```

**Benefits**:
- Type-safe linking
- Enables validation
- Supports ordering
- Queryable

---

### 2. Teacher Guidance Pattern
Used for linking teacher to student content:

```json
{
  "teacherGuidance": {
    "linkedStudentActivity": {
      "studentActivityId": "uuid",
      "linkType": "MIRRORS"
    },
    "instructionType": "DIRECT_INSTRUCTION",
    "instructionalText": "Guide students to...",
    "differentiationStrategies": {
      "advanced": "...",
      "ell": "..."
    }
  }
}
```

**Benefits**:
- Clear teacher-student separation
- Explicit relationship types
- Supports differentiation
- Optional and self-contained

---

### 3. Metadata Pattern
Used for optional rich metadata:

```json
{
  "metadata": {
    "pacingEstimate": { "value": 45 },
    "publishingMetadata": { "version": "1.0.0", "status": "PUBLISHED" },
    "localizationInfo": { "language": "en", "locale": "en-US" }
  }
}
```

**Benefits**:
- Keeps core properties clean
- Optional without breaking schema
- Grouped by concern
- Extensible

---

### 4. Typed Enumeration Pattern
All categorical values use enums:

```json
{
  "activityType": "EXPLORE",
  "taskType": "WORD_PROBLEM",
  "imageType": "TECHNICAL_ART"
}
```

**Benefits**:
- Prevents invalid values
- Self-documenting
- Enables validation
- UI-friendly (dropdowns)

---

## Scalability Considerations

### Content Volume
**Design supports**:
- Large curriculum (multiple grade levels)
- Hundreds of modules, thousands of lessons
- Tens of thousands of tasks and images
- Multiple editions and versions

**Mechanisms**:
- UUID-based linking (no sequential bottlenecks)
- Normalized structure (minimize duplication)
- Reference-based relationships (efficient storage)

---

### Query Performance
**Design supports**:
- Finding all lessons for a module
- Finding all activities of a specific type
- Finding all content aligned to a standard
- Finding teacher content for student content

**Mechanisms**:
- Explicit parent IDs (e.g., `lessonId` in activities)
- Reference arrays (e.g., `activities[]` in lessons)
- Type fields enable filtering
- Indexes can be built on key fields

---

### Content Reuse
**Design supports**:
- Reusing images across content
- Reusing standards across lessons
- Reusing scaffolding across tasks
- Reusing goals across activities

**Mechanisms**:
- Entity references (not embedding)
- Shared image library
- Shared standards database
- Modular content structure

---

## Validation Strategy

### Schema-Level Validation
**JSON Schema provides**:
- Type validation
- Required field enforcement
- Enum value checking
- Pattern matching (UUIDs, ISBNs)

### Application-Level Validation
**Additional validation needed**:
- Referenced entities exist
- No circular references
- Sequence numbers are unique and contiguous
- Teacher-student links are valid
- Parent-child relationships are consistent

### Recommended Validation Rules
1. **Reference Integrity**: All referenced UUIDs must exist
2. **Parent Consistency**: Child's parent ID must match parent's ID
3. **Sequence Uniqueness**: Sequence numbers unique within array
4. **Teacher-Student Validity**: Linked student content exists
5. **Standards Body Consistency**: Standards match declared body
6. **Image Type Consistency**: Technical art has technicalArtType
7. **Accessibility Compliance**: Non-decorative images have altText

---

## Extension Points

### Adding New Content Types
**To add a new content level** (e.g., "Unit" between Module and Topic):
1. Create new schema (unit.json)
2. Add Unit to ReferenceType enum
3. Add unit references to module.json
4. Add moduleId to unit.json
5. Update topic.json to reference unitId

### Adding New Activity Types
**To add a new activity type** (e.g., "ASSESSMENT"):
1. Add ASSESSMENT to ActivityType enum
2. Define specific properties if needed
3. Update documentation
4. Create validation rules if needed

### Adding New Standards Bodies
**To support a new standards framework** (e.g., American Curriculum):
1. Add new value to StandardsBody enum
2. Create standard documents with new body
3. Update documentation with body-specific format
4. Add to standards-block.json examples

### Adding New Image Types
**To add a new image category**:
1. Add to ImageType enum
2. If it's technical art, add to TechnicalArtType enum
3. Update image.json documentation
4. Add examples to implementation guide

---

## Data Integrity Principles

### 1. Referential Integrity
- Every reference must point to an existing entity
- Deleting an entity should handle or prevent orphaned references
- UUIDs are permanent and never reused

### 2. Hierarchy Consistency
- Child entities must have valid parent references
- Parent arrays must include all children
- Sequence numbers must be unique within siblings

### 3. Type Safety
- References must match expected types
- Enums must use valid values
- Conditional requirements must be enforced (e.g., technicalArtType when imageType is TECHNICAL_ART)

### 4. Semantic Consistency
- Teacher-student links must be bidirectional (if teacher references student, student should be referenceable)
- Standards referenced must match the declared standards body
- Page types must match the resource type (SRB_ pages only in student resource books)

---

## Performance Optimization Strategies

### 1. Indexing Strategy
**Recommended indexes**:
- UUIDs (primary keys)
- Parent IDs (moduleId, topicId, lessonId, etc.)
- Type fields (activityType, taskType, imageType, etc.)
- Sequence numbers
- Standard codes
- Status fields

### 2. Query Patterns
**Common queries to optimize**:
- Get all children of a parent (e.g., all activities in a lesson)
- Get entity by UUID
- Get entities by type
- Get content by standards alignment
- Get teacher content for student content

### 3. Denormalization Considerations
**May want to denormalize**:
- Content paths (module → topic → lesson) for breadcrumbs
- Aggregate counts (number of activities in lesson)
- Computed fields (total pacing estimate)

**But maintain**:
- Single source of truth
- Explicit update triggers

---

## Security & Access Control

### Considerations
1. **Student vs. Teacher Content**: Students should never see teacher guidance
2. **Draft vs. Published**: Unpublished content should be restricted
3. **Standards**: May have licensing restrictions
4. **Images**: May have copyright restrictions

### Recommended Access Patterns
- **Students**: Read access to published student content only
- **Teachers**: Read access to published student and teacher content
- **Authors**: Read/write access to draft and published content
- **Reviewers**: Read access to draft content, approval permissions
- **Admins**: Full access

---

## Testing Strategy

### Unit Testing
- Schema validation for each entity type
- Required field enforcement
- Enum value validation
- Pattern matching (UUIDs, ISBNs)

### Integration Testing
- Reference integrity
- Parent-child consistency
- Teacher-student linking
- Standards alignment

### End-to-End Testing
- Complete lesson creation workflow
- Teacher guide linking workflow
- Standards alignment workflow
- Content publishing workflow

---

## Future Considerations

### Potential Enhancements
1. **Versioning**: Track content versions and changes
2. **Localization**: Full multilingual support
3. **Adaptive Content**: Student-level customization
4. **Analytics**: Usage tracking and performance data
5. **Collaboration**: Multi-author workflows
6. **AI Integration**: Auto-tagging, standards alignment
7. **Assessment Integration**: Link to assessment systems
8. **Accessibility**: Enhanced accessibility features

### Migration Path
When schema evolves:
1. Version new schemas (1.1.0, 2.0.0)
2. Provide migration utilities
3. Support backward compatibility when possible
4. Deprecate old patterns before removing
5. Update documentation with migration guides

---

See also:
- [Schema Architecture](../architecture/SCHEMA_ARCHITECTURE.md) for technical implementation
- [Implementation Guide](../guides/IMPLEMENTATION_GUIDE.md) for practical usage
- [Best Practices](../guides/BEST_PRACTICES.md) for recommended patterns
