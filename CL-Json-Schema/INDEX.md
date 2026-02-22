# Documentation Index

## Welcome

This is the complete documentation for the comprehensive JSON schema-based framework for managing CL educational content across multiple publication types.

---

## Quick Start

### New Users
1. Start with [README.md](./README.md) - System overview and dual hierarchy concepts
2. Review [ARCHITECTURE.md](./ARCHITECTURE.md) - Visual diagrams showing both hierarchies

### Understanding the Dual Hierarchy

The system uses **two parallel hierarchies**:

**Physical Layout**: Resource → Pages → Content Block References
- How content appears in books
- Pages reference content at any level

**Logical Content**: Module (linked to Resource) → Topic → Lesson → Activity → Task → Stem
- How content is pedagogically organized  
- Modules link to resources for context (state, standards body)

See: [Content Hierarchy](./README.md#content-hierarchy) | [Architecture Diagrams](./ARCHITECTURE.md#content-hierarchy)

### Developers
1. [SCHEMA_REFERENCE.md](./SCHEMA_REFERENCE.md) - Complete schema documentation
2. [IMPLEMENTATION_EXAMPLES.md](./IMPLEMENTATION_EXAMPLES.md) - Practical code examples
3. [DATA_ARCHITECTURE.md](./DATA_ARCHITECTURE.md) - File organization and database design

### Content Creators
1. [README.md](./README.md#workflow-patterns) - Content creation workflows
2. [IMPLEMENTATION_EXAMPLES.md](./IMPLEMENTATION_EXAMPLES.md) - Complete lesson examples

---

## Documentation Files

### 📘 README.md
**Purpose**: Main entry point and system overview

**Contents**:
- System overview and key features
- Three book types (SRB, SPB, TIG)
- Content hierarchy explanation
- Quick start guide
- Core schema list
- Key relationships
- Workflow patterns

**Best For**: First-time users, project overview, management

[View README.md](./README.md)

---

### 🏗️ ARCHITECTURE.md
**Purpose**: System design, visual diagrams, and architectural decisions

**Contents**:
- Visual hierarchy diagrams (Mermaid)
- Content flow diagrams
- Resource type relationships
- Teacher-student linking patterns
- Schema dependency graphs
- Design principles
- Performance considerations
- Security guidelines

**Best For**: Understanding system design, planning implementations, architecture review

**Key Diagrams**:
- [Content Hierarchy](./ARCHITECTURE.md#content-hierarchy)
- [Three Book Architecture](./ARCHITECTURE.md#resource-types)
- [Data Flow](./ARCHITECTURE.md#data-flow)
- [Entity Relationships](./ARCHITECTURE.md#relationship-diagrams)
- [Schema Dependencies](./ARCHITECTURE.md#schema-dependencies)

[View ARCHITECTURE.md](./ARCHITECTURE.md)

---

### 📖 SCHEMA_REFERENCE.md
**Purpose**: Detailed documentation of every schema, property, and field

**Contents**:
- Common schemas (primitives, enums, metadata)
- Content schemas (resource through stem)
- Layout schemas (pages)
- Standards schemas
- Media schemas
- Response schemas
- Instructional schemas
- Field requirements and constraints
- Conditional requirements
- Property examples

**Best For**: Detailed schema lookup, validation requirements, implementation reference

**Schema Categories**:
- [Common Schemas](./SCHEMA_REFERENCE.md#common-schemas)
- [Content Schemas](./SCHEMA_REFERENCE.md#content-schemas)
- [Standards Schemas](./SCHEMA_REFERENCE.md#standards-schemas)
- [Media Schemas](./SCHEMA_REFERENCE.md#media-schemas)
- [Response Schemas](./SCHEMA_REFERENCE.md#response-schemas)
- [Instructional Schemas](./SCHEMA_REFERENCE.md#instructional-schemas)

[View SCHEMA_REFERENCE.md](./SCHEMA_REFERENCE.md)

---

### 💾 DATA_ARCHITECTURE.md
**Purpose**: File organization, database schema, and storage recommendations

**Contents**:
- Recommended directory structures
- File organization patterns
- Naming conventions
- Storage recommendations (file vs. database)
- Complete database schemas (PostgreSQL & MongoDB)
- Import/export scripts
- Validation pipeline
- Build pipeline
- Version control strategy
- Backup and recovery

**Best For**: Setting up projects, organizing content files, database design, DevOps

**Key Sections**:
- [Directory Structure](./DATA_ARCHITECTURE.md#directory-structure)
- [File Organization Patterns](./DATA_ARCHITECTURE.md#file-organization-patterns)
- [Database Schema](./DATA_ARCHITECTURE.md#database-schema)
- [File Management](./DATA_ARCHITECTURE.md#file-management)
- [Version Control](./DATA_ARCHITECTURE.md#version-control-strategy)

[View DATA_ARCHITECTURE.md](./DATA_ARCHITECTURE.md)

---

### 💡 IMPLEMENTATION_EXAMPLES.md
**Purpose**: Complete, real-world examples of schema usage

**Contents**:
- Complete Grade 4 lesson example
- Student Resource Book module
- Teacher Implementation Guide
- Practice Book section
- Standards integration examples
- Multi-media content examples
- All response area types
- Localization example (Spanish)

**Best For**: Learning by example, copy-paste templates, understanding relationships

**Examples Included**:
- [Complete Lesson](./IMPLEMENTATION_EXAMPLES.md#complete-lesson-example) - Full Module 1, Topic 1, Lesson 1
- [Student Resource Book](./IMPLEMENTATION_EXAMPLES.md#student-resource-book-module)
- [Teacher Guide](./IMPLEMENTATION_EXAMPLES.md#teacher-implementation-guide)
- [Practice Book](./IMPLEMENTATION_EXAMPLES.md#practice-book-section)
- [Standards](./IMPLEMENTATION_EXAMPLES.md#standards-integration)
- [Media](./IMPLEMENTATION_EXAMPLES.md#multi-media-content)
- [Response Areas](./IMPLEMENTATION_EXAMPLES.md#response-areas)
- [Localization](./IMPLEMENTATION_EXAMPLES.md#localization-example)

[View IMPLEMENTATION_EXAMPLES.md](./IMPLEMENTATION_EXAMPLES.md)

---

## Navigation by Topic

### Content Creation

#### Creating a New Resource (Book)
1. [Resource Schema Reference](./SCHEMA_REFERENCE.md#resourcejson)
2. [Resource Example](./IMPLEMENTATION_EXAMPLES.md#student-resource-book-module)

#### Creating Modules, Topics, and Lessons
1. [Content Hierarchy](./ARCHITECTURE.md#content-hierarchy)
2. [Module Schema](./SCHEMA_REFERENCE.md#modulejson)
3. [Topic Schema](./SCHEMA_REFERENCE.md#topicjson)
4. [Lesson Schema](./SCHEMA_REFERENCE.md#lessonjson)

#### Creating Activities and Tasks
1. [Activity Schema](./SCHEMA_REFERENCE.md#activityjson)
2. [Task Schema](./SCHEMA_REFERENCE.md#taskjson)
3. [Stem Schema](./SCHEMA_REFERENCE.md#stemjson)
4. [Complete Lesson Example](./IMPLEMENTATION_EXAMPLES.md#complete-lesson-example)

### Standards Alignment

#### Understanding Standards
1. [Standards Overview](./README.md#standards-integration)
2. [Standard Schema](./SCHEMA_REFERENCE.md#standardjson)
3. [Standards Block Schema](./SCHEMA_REFERENCE.md#standards-blockjson)
4. [Standards Alignment Flow](./ARCHITECTURE.md#standards-alignment-flow)

#### Implementing Standards
1. [Standards Examples](./IMPLEMENTATION_EXAMPLES.md#standards-integration)
2. [Activity Goals](./SCHEMA_REFERENCE.md#activity-goalsjson)

### Teacher-Student Linking

#### Understanding Links
1. [Teacher-Student Relationships](./ARCHITECTURE.md#teacher-student-content-linking)
2. [TeacherStudentLink Metadata](./SCHEMA_REFERENCE.md#teacherstudentlink)

#### Implementing Links
1. [TIG Examples](./IMPLEMENTATION_EXAMPLES.md#teacher-implementation-guide)

### Media Management

#### Images
1. [Image Schema](./SCHEMA_REFERENCE.md#imagejson)
2. [Image Types](./SCHEMA_REFERENCE.md#imagetype)
3. [Image Organization](./DATA_ARCHITECTURE.md#directory-structure)
4. [Multi-Media Examples](./IMPLEMENTATION_EXAMPLES.md#multi-media-content)

#### Technical Art
1. [Technical Art Types](./SCHEMA_REFERENCE.md#technicalarttype)
2. [Creating Technical Art](./IMPLEMENTATION_EXAMPLES.md#task-with-image-and-technical-art)

### Response Areas

#### Types of Response Areas
1. [Response Area Schema](./SCHEMA_REFERENCE.md#response-areajson)
2. [Response Area Types](./SCHEMA_REFERENCE.md#responseareatype)
3. [Response Area Examples](./IMPLEMENTATION_EXAMPLES.md#response-areas)

#### Creating Response Areas
1. [Grid Response](./IMPLEMENTATION_EXAMPLES.md#task-with-grid-response-area)
2. [Algorithm Workspace](./IMPLEMENTATION_EXAMPLES.md#algorithm-workspace)
3. [Number Line](./IMPLEMENTATION_EXAMPLES.md#number-line)

### Localization

#### Internationalization
1. [Localization Overview](./README.md#content-localization)
2. [LocalizationInfo Metadata](./SCHEMA_REFERENCE.md#localizationinfo)
3. [Localization Example](./IMPLEMENTATION_EXAMPLES.md#localization-example)


---

## Schema Quick Reference

### Core Content Schemas
- [resource.json](./SCHEMA_REFERENCE.md#resourcejson) - Books/Publications
- [module.json](./SCHEMA_REFERENCE.md#modulejson) - Major units
- [topic.json](./SCHEMA_REFERENCE.md#topicjson) - Subject areas
- [lesson.json](./SCHEMA_REFERENCE.md#lessonjson) - Instructional sessions
- [activity.json](./SCHEMA_REFERENCE.md#activityjson) - Learning experiences
- [task.json](./SCHEMA_REFERENCE.md#taskjson) - Questions/problems
- [stem.json](./SCHEMA_REFERENCE.md#stemjson) - Individual prompts

### Supporting Schemas
- [page.json](./SCHEMA_REFERENCE.md#pagejson) - Physical pages
- [standard.json](./SCHEMA_REFERENCE.md#standardjson) - Educational standards
- [standards-block.json](./SCHEMA_REFERENCE.md#standards-blockjson) - Grouped standards
- [image.json](./SCHEMA_REFERENCE.md#imagejson) - Media assets
- [response-area.json](./SCHEMA_REFERENCE.md#response-areajson) - Answer spaces
- [scaffolding.json](./SCHEMA_REFERENCE.md#scaffoldingjson) - Learning supports
- [activity-goals.json](./SCHEMA_REFERENCE.md#activity-goalsjson) - Learning objectives
- [practice-section.json](./SCHEMA_REFERENCE.md#practice-sectionjson) - Practice activities

### Instructional Schemas
- [instructional-prompt.json](./SCHEMA_REFERENCE.md#instructional-promptjson) - Teacher prompts
- [instructional-segment.json](./SCHEMA_REFERENCE.md#instructional-segmentjson) - Instructional sections

### Common Schemas
- [primitives.json](./SCHEMA_REFERENCE.md#primitivesjson) - Basic types
- [enums.json](./SCHEMA_REFERENCE.md#enumsjson) - Enumerated values
- [metadata.json](./SCHEMA_REFERENCE.md#metadatajson) - Metadata structures

---

## Diagrams Reference

All diagrams are in [ARCHITECTURE.md](./ARCHITECTURE.md):

1. [Content Hierarchy](./ARCHITECTURE.md#content-hierarchy) - Resource → Module → Topic → Lesson → Activity → Task → Stem
2. [Example Hierarchy Instance](./ARCHITECTURE.md#example-hierarchy-instance) - Grade 4 Math example
3. [Three Book Architecture](./ARCHITECTURE.md#three-book-architecture) - SRB, SPB, TIG relationships
4. [Content Creation Flow](./ARCHITECTURE.md#content-creation-flow) - Workflow sequence
5. [Standards Alignment Flow](./ARCHITECTURE.md#standards-alignment-flow) - How standards integrate
6. [Entity Relationships](./ARCHITECTURE.md#core-entity-relationships) - ER diagram
7. [Teacher-Student Linking](./ARCHITECTURE.md#teacher-student-content-linking) - TIG to SRB links
8. [Image and Media Flow](./ARCHITECTURE.md#image-and-media-flow) - Media management
9. [Schema Dependencies](./ARCHITECTURE.md#schema-dependency-graph) - Import order

---
