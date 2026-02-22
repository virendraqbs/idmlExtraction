# Educational Content Schema System

## Overview

This is a comprehensive JSON schema system for managing educational content across three interconnected CL publication types: Student Resource Books (SRB), Student Practice Books (SPB), and Teacher Implementation Guides (TIG). The system provides a structured approach to organizing curriculum content while maintaining relationships between teacher and student materials.

## Key Features

- **Multi-resource architecture**: Supports three distinct book types with shared content references
- **Hierarchical content organization**: Module → Topic → Lesson → Activity → Task → Stem
- **Standards alignment**: Built-in support for CCSS, CA_CCSS, TEKS, and BEST standards
- **Teacher-student linking**: Explicit connections between instructional guides and student materials
- **Rich metadata**: Comprehensive support for localization, accessibility, copyright, and publishing workflows
- **Media management**: Integrated image and asset tracking with reusability support
- **Flexible page layouts**: Separate physical page structure from logical content organization

## System Architecture

### Three Book Types

1. **Student Resource Book (SRB)**
   - Primary instructional content for students
   - Contains activate, explore, and reflect activities
   - Organized by modules, topics, and lessons

2. **Student Practice Book (SPB)**
   - Practice exercises aligned with lessons
   - Family guides and conversation starters
   - Reinforcement activities

3. **Teacher Implementation Guide (TIG)**
   - Instructional guidance and teaching strategies
   - Links directly to student content
   - Includes differentiation strategies and assessment guidance

### Content Hierarchy

The system uses two parallel hierarchies:

**Physical Layout Hierarchy** (How content appears in books):
```
Resource (Book)
└── Pages
    └── Content Blocks (references to Modules, Topics, Lessons, Activities, etc.)
```

**Logical Content Hierarchy** (How content is organized):
```
Module (linked to Resource for state/standards context)
└── Topic
    └── Lesson
        └── Activity
            └── Task
                └── Stem
```

Modules belong to a Resource (maintaining resourceId for context like state, grade level, standards body), but the content structure starts at the Module level. Pages reference content blocks at any level of the hierarchy.

## Quick Start

### Basic Concepts

1. **Resource**: The top-level container representing a physical book (SRB, SPB, or TIG). Contains metadata about grade level, state, standards body, and references to pages.
2. **Page**: Physical page layout that references content blocks (modules, topics, lessons, activities) for display.
3. **Module**: Major curriculum unit that belongs to a Resource (via resourceId) but serves as the starting point for logical content hierarchy. Contains topic references.
4. **Topic**: Specific subject within a module (e.g., "Place Value")
5. **Lesson**: Individual instructional session
6. **Activity**: Learning experience within a lesson (Activate, Explore, Reflect)
7. **Task**: Specific question or problem
8. **Stem**: Individual question prompt with response area

**Key Relationship**: Modules link to Resources (for context like state, standards body), but content hierarchy flows from Module downward. Pages provide the physical layout by referencing content at any level.

### Getting Started

1. Review the [Schema Reference](./SCHEMA_REFERENCE.md) for detailed property definitions
2. Study the [Architecture Documentation](./ARCHITECTURE.md) for system design
3. Follow the [Implementation Guide](./IMPLEMENTATION_GUIDE.md) for step-by-step instructions
4. Check [Data Architecture](./DATA_ARCHITECTURE.md) for file organization
5. See [Implementation Examples](./IMPLEMENTATION_EXAMPLES.md) for practical code samples

## Core Schemas

### Content Structure
- `resource.json` - Top-level book/publication
- `module.json` - Major curriculum units
- `topic.json` - Specific subjects within modules
- `lesson.json` - Individual lessons
- `activity.json` - Learning activities
- `task.json` - Specific problems/questions
- `stem.json` - Individual question prompts

### Supporting Elements
- `page.json` - Physical page layout
- `standard.json` - Educational standards
- `standards-block.json` - Grouped standards for display
- `image.json` - Media assets
- `response-area.json` - Student answer spaces
- `scaffolding.json` - Learning supports

### Instructional Content
- `instructional-prompt.json` - Teacher guidance elements
- `instructional-segment.json` - Instructional sections
- `practice-section.json` - Practice activities
- `activity-goals.json` - Learning objectives

### Common Definitions
- `primitives.json` - Basic data types (UUID, Reference, Image)
- `enums.json` - Enumerated values for all types
- `metadata.json` - Reusable metadata structures

## Key Relationships

### Teacher-Student Content Linking
Teacher Implementation Guide content explicitly links to corresponding student content through the `TeacherStudentLink` structure:

```json
{
  "studentPublicationId": "uuid",
  "studentPageId": "uuid",
  "studentActivityId": "uuid",
  "linkType": "MIRRORS"
}
```

### Standards Integration
Standards can be referenced at multiple levels:
- Resource level (overall curriculum)
- Module level (unit standards)
- Lesson level (specific lesson standards via standards blocks)
- Activity level (through activity goals)

### Content Reusability
Images and other assets can be:
- Referenced across multiple pages and activities
- Tracked for usage locations
- Marked as reusable or context-specific

## Workflow Patterns

### Creating New Content

1. **Define the resource** (book metadata and structure)
2. **Build the hierarchy** (modules → topics → lessons)
3. **Add activities** with learning goals
4. **Create tasks** with stems and response areas
5. **Align standards** at appropriate levels
6. **Link teacher content** to student materials
7. **Add media assets** with proper metadata

### Content Localization

1. Set base language and locale in resource metadata
2. Create translated versions with proper `LocalizationInfo`
3. Document cultural adaptations
4. Track translation and review status

### Standards Alignment

1. Define standards in `standard.json`
2. Group related standards in `standards-block.json`
3. Reference standards blocks in lessons
4. Link activity goals to specific standards

## Validation and Best Practices

### Required Fields
All schemas specify required fields. Key requirements:
- Every entity must have a unique `id` (UUID)
- Parent-child relationships require parent ID references
- Sequence numbers required for ordered collections
- Alt text required for non-decorative images

### Naming Conventions
- Use descriptive titles for human readability
- Maintain consistent terminology across related content
- Follow grade-level conventions (K, 1, 2, 3, 4, 5)
- Use standard codes for standards (e.g., "4.NBT.4")

### Data Integrity
- Maintain referential integrity for all UUID references
- Ensure sequence numbers are continuous within collections
- Validate enum values against definitions
- Keep teacher-student links synchronized


### File Organization
See [Data Architecture](./DATA_ARCHITECTURE.md) for recommended file and folder structure.

## Support and Documentation

- **Full Schema Details**: [SCHEMA_REFERENCE.md](./SCHEMA_REFERENCE.md)
- **System Architecture**: [ARCHITECTURE.md](./ARCHITECTURE.md)
- **Implementation Guide**: [IMPLEMENTATION_GUIDE.md](./IMPLEMENTATION_GUIDE.md)
- **Code Examples**: [IMPLEMENTATION_EXAMPLES.md](./IMPLEMENTATION_EXAMPLES.md)
- **Data Structure**: [DATA_ARCHITECTURE.md](./DATA_ARCHITECTURE.md)
- **Complete Index**: [INDEX.md](./INDEX.md)