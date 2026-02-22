# System Architecture

## Table of Contents

1. [Overview](#overview)
2. [Content Hierarchy](#content-hierarchy)
3. [Resource Types](#resource-types)
4. [Data Flow](#data-flow)
5. [Relationship Diagrams](#relationship-diagrams)
6. [Schema Dependencies](#schema-dependencies)
7. [Design Principles](#design-principles)

## Overview

The JSON schema is designed as a hierarchical, relational data model that supports three distinct publication types while maintaining content coherence and reusability. The architecture balances flexibility with structure, enabling both rigid curriculum organization and dynamic content relationships.

### Core Architectural Principles

1. **Separation of Concerns**: Physical layout (pages) is separate from logical content organization (modules/lessons)
2. **Hierarchical Organization**: Clear parent-child relationships from Resource down to Stem
3. **Content Reusability**: Images and other assets can be shared across content
4. **Standards Alignment**: Multiple levels of standards integration
5. **Explicit Linking**: Teacher content explicitly links to student content
6. **Localization Support**: Built-in internationalization and state-specific variations

## Content Hierarchy

> **Note**: You can view and interact with the Mermaid diagrams in this document by pasting them into [Mermaid Chart Playground](https://www.mermaidchart.com/play).

The system employs two parallel hierarchies that work together:

### Physical Layout Hierarchy

Pages provide the physical structure of how content appears in books:

```mermaid
graph TD
    A[Resource<br/>Book/Publication] --> B[Pages]
    B --> C[Page 1]
    B --> D[Page 42]
    B --> E[Page 43]
    
    C --> C1[Content Blocks]
    C1 --> C2[References to:<br/>Modules, Topics,<br/>Lessons, Activities]
    
    style A fill:#e1f5ff
    style B fill:#fff4e1
    style C fill:#ffe1f5
    style D fill:#ffe1f5
    style E fill:#ffe1f5
```

### Logical Content Hierarchy

Content is organized hierarchically starting from Modules, which link to Resources for context:

```mermaid
graph TD
    R[Resource<br/>Provides Context:<br/>State, Standards Body,<br/>Grade Level]
    
    M[Module<br/>Contains resourceId] -.links to.-> R
    M --> T[Topic<br/>Subject Area]
    T --> L[Lesson<br/>Instructional Session]
    L --> A[Activity<br/>Learning Experience]
    A --> K[Task<br/>Question/Problem]
    K --> S[Stem<br/>Individual Prompt]
    
    style R fill:#e1f5ff,stroke-dasharray: 5 5
    style M fill:#fff4e1
    style T fill:#ffe1f5
    style L fill:#e1ffe1
    style A fill:#f5e1ff
    style K fill:#ffe1e1
    style S fill:#e1e1ff
```

**Key Points**:
- Modules have a `resourceId` field linking them to their parent Resource
- This link provides context (state, standards body, grade level, edition)
- Content hierarchy starts at Module level for logical organization
- Pages reference content blocks at any level for physical layout
- This separation allows flexible page layouts while maintaining clear content structure

### Complete System Example

This shows how both hierarchies work together:

```mermaid
graph TD
    subgraph Physical Layout
    R["Resource: Grade 4 Math<br/>Student Resource Book<br/>(state: CA, body: CCSS)"]
    R --> P1[Page 1: TOC]
    R --> P42[Page 42: Lesson Start]
    R --> P43[Page 43: Lesson Continued]
    
    P42 --> P42C[References:<br/>Module 1, Lesson 1,<br/>Activate Activity]
    P43 --> P43C[References:<br/>Lesson 1,<br/>Explore Activity]
    end
    
    subgraph Logical Content
    M1["Module 1: Place Value<br/>(resourceId: links to Resource)"] -.context from.-> R
    
    M1 --> T1[Topic 1:<br/>Understanding Place Value]
    M1 --> T2[Topic 2:<br/>Comparing Numbers]
    
    T1 --> L1[Lesson 1:<br/>Ones and Tens]
    T1 --> L2[Lesson 2:<br/>Hundreds]
    
    L1 --> A1[Activity: Activate<br/>Base Ten Blocks]
    L1 --> A2[Activity: Explore<br/>Place Value Chart]
    L1 --> A3[Activity: Reflect<br/>Real World Applications]
    
    A2 --> K1[Task 1:<br/>Complete Chart]
    A2 --> K2[Task 2:<br/>Word Problem]
    
    K1 --> S1[Stem: What digit<br/>is in tens place?]
    K1 --> S2[Stem: Write the<br/>value of digit]
    end
    
    style R fill:#4a90e2,color:#fff
    style P42 fill:#95a5a6,color:#fff
    style P43 fill:#95a5a6,color:#fff
    style M1 fill:#f5a623
    style T1 fill:#bd10e0,color:#fff
    style L1 fill:#7ed321
    style A2 fill:#50e3c2
    style K1 fill:#ff6b6b
    style S1 fill:#4ecdc4
```

## Resource Types

### Understanding the Dual Hierarchy

The system uses two complementary hierarchies:

**1. Physical Layout (Resource → Pages)**
- Describes how content appears in the physical/digital book
- Pages reference content blocks for display
- Handles page numbers, page types, layout
- Example: "Page 42 shows Module 1 introduction and Lesson 1 Activate activity"

**2. Logical Content (Module → ... → Stem)**
- Describes the pedagogical organization of content
- Modules link to Resources (via `resourceId`) for context
- Independent of physical page layout
- Example: "Module 1 contains 3 topics, Topic 1 has 5 lessons"

**Why Modules Link to Resources:**
- Provides state context (e.g., CA, TX, FL)
- Defines standards body (CCSS, TEKS, BEST, CA_CCSS)
- Specifies grade level and edition
- Enables multi-state publishing from same content
- Allows resource-level metadata to inform content

**Example:**
```json
{
  "module": {
    "id": "module-1-uuid",
    "resourceId": "resource-ca-grade4-uuid",  // Links to CA Grade 4 Resource
    "moduleNumber": 1,
    "title": "Place Value"
  }
}
```

The Resource provides context:
```json
{
  "resource": {
    "id": "resource-ca-grade4-uuid",
    "gradeLevel": "4",
    "state": "CA",
    "standardsBody": "CA_CCSS"
  }
}
```

### Three Book Architecture

```mermaid
graph LR
    A[Student Resource Book<br/>SRB] -.Teacher Links.-> B[Teacher Implementation Guide<br/>TIG]
    A -.Practice References.-> C[Student Practice Book<br/>SPB]
    B -.Instructional Guidance.-> A
    B -.Answer Keys.-> C
    
    style A fill:#4a90e2,color:#fff
    style B fill:#f5a623,color:#fff
    style C fill:#7ed321,color:#fff
```

### Resource Type Characteristics

| Feature | Student Resource Book | Student Practice Book | Teacher Implementation Guide |
|---------|----------------------|----------------------|----------------------------|
| **Primary Audience** | Students | Students | Teachers |
| **Content Type** | Instruction & Learning | Practice & Reinforcement | Teaching Strategies |
| **Activities** | Activate, Explore, Reflect | Practice Questions, Games | Instructional Segments |
| **Page Types** | Lesson content, summaries | Practice pages, family guides | Lesson overviews, guidance |
| **Linking** | Referenced by TIG | Referenced by TIG | Links to SRB and SPB |

## Data Flow

### Standards Alignment Flow

```mermaid
graph TD
    A[Standard Definition] --> B[Standards Block]
    B --> C{Alignment Level}
    
    C -->|Resource Level| D[Resource Standards]
    C -->|Module Level| E[Module Standards]
    C -->|Lesson Level| F[Lesson Standards Block]
    C -->|Activity Level| G[Activity Goals]
    
    F --> H[Display in Lesson]
    G --> I[Display in Activity]
    
    style A fill:#e1f5ff
    style B fill:#fff4e1
    style C fill:#ffe1f5
    style D fill:#e1ffe1
    style E fill:#e1ffe1
    style F fill:#f5e1ff
    style G fill:#f5e1ff
```

## Relationship Diagrams

### Core Entity Relationships

This diagram shows both hierarchies:

```mermaid
erDiagram
    RESOURCE ||--o{ PAGE : contains
    RESOURCE ||--o{ STANDARD : aligns-to
    RESOURCE ||--o{ MODULE : provides-context-for
    
    PAGE ||--o{ CONTENT-BLOCK-REF : displays
    
    MODULE ||--|| RESOURCE : links-to-via-resourceId
    MODULE ||--o{ TOPIC : contains
    MODULE ||--o{ IMAGE : uses
    
    TOPIC ||--o{ LESSON : contains
    TOPIC ||--o{ PRACTICE-SECTION : may-have
    
    LESSON ||--o{ ACTIVITY : contains
    LESSON ||--|| STANDARDS-BLOCK : references
    
    ACTIVITY ||--o{ TASK : contains
    ACTIVITY ||--o{ GOALS : has
    ACTIVITY ||--o{ SCAFFOLDING : provides
    
    TASK ||--o{ STEM : contains
    TASK ||--o{ SCAFFOLDING : may-have
    
    STEM ||--|| RESPONSE-AREA : has
    STEM ||--o| IMAGE : may-include
    
    STANDARDS-BLOCK ||--o{ STANDARD : groups
    
    GOALS ||--o{ STANDARD : aligns-to
    
    CONTENT-BLOCK-REF ||--o| MODULE : may-reference
    CONTENT-BLOCK-REF ||--o| TOPIC : may-reference
    CONTENT-BLOCK-REF ||--o| LESSON : may-reference
    CONTENT-BLOCK-REF ||--o| ACTIVITY : may-reference
```

### Teacher-Student Content Linking

```mermaid
graph TD
    subgraph Teacher Implementation Guide
    T1[TIG Resource]
    T2[TIG Module Overview]
    T3[TIG Lesson Overview]
    T4[TIG Activity Guidance]
    T5[TIG Task Instructions]
    end
    
    subgraph Student Resource Book
    S1[SRB Resource]
    S2[SRB Module]
    S3[SRB Lesson]
    S4[SRB Activity]
    S5[SRB Task]
    end
    
    T1 -.linkedStudentResource.-> S1
    T2 -.instructional context.-> S2
    T3 -.linkedStudentLesson.-> S3
    T4 -.linkedStudentActivity.-> S4
    T5 -.linkedStudentTask.-> S5
    
    style T1 fill:#f5a623
    style T2 fill:#f5a623
    style T3 fill:#f5a623
    style T4 fill:#f5a623
    style T5 fill:#f5a623
    style S1 fill:#4a90e2
    style S2 fill:#4a90e2
    style S3 fill:#4a90e2
    style S4 fill:#4a90e2
    style S5 fill:#4a90e2
```

### Image and Media Flow

```mermaid
graph TD
    A[Image Asset] --> B{Image Type}
    
    B -->|MODULE_COVER| C[Module]
    B -->|TOPIC_COVER| D[Topic]
    B -->|LESSON_COVER| E[Lesson]
    B -->|INSTRUCTIONAL| F[Activity/Task/Stem]
    B -->|TECHNICAL_ART| G[Multiple Locations]
    B -->|CHARACTER_SUPPORT| H[Scaffolding]
    
    G --> I[Reusable Across Content]
    
    I --> J[Usage Tracking]
    J --> K[usedInPages]
    J --> L[usedInActivities]
    J --> M[usedInTasks]
    
    style A fill:#e1f5ff
    style B fill:#fff4e1
    style I fill:#7ed321
    style J fill:#50e3c2
```

## Schema Dependencies

### Schema Dependency Graph

```mermaid
graph TD
    subgraph Common Schemas
    PRIM[primitives.json]
    ENUM[enums.json]
    META[metadata.json]
    end
    
    subgraph Content Schemas
    RES[resource.json]
    MOD[module.json]
    TOP[topic.json]
    LES[lesson.json]
    ACT[activity.json]
    TSK[task.json]
    STM[stem.json]
    end
    
    subgraph Supporting Schemas
    PAG[page.json]
    IMG[image.json]
    STD[standard.json]
    STDB[standards-block.json]
    RES_AREA[response-area.json]
    SCAF[scaffolding.json]
    GOALS[activity-goals.json]
    PRAC[practice-section.json]
    end
    
    subgraph Instructional Schemas
    IPROM[instructional-prompt.json]
    ISEG[instructional-segment.json]
    end
    
    PRIM --> RES
    PRIM --> MOD
    PRIM --> TOP
    PRIM --> LES
    PRIM --> ACT
    PRIM --> TSK
    PRIM --> STM
    PRIM --> PAG
    PRIM --> IMG
    PRIM --> STD
    PRIM --> STDB
    PRIM --> RES_AREA
    PRIM --> SCAF
    PRIM --> GOALS
    PRIM --> PRAC
    PRIM --> IPROM
    PRIM --> ISEG
    
    ENUM --> RES
    ENUM --> MOD
    ENUM --> ACT
    ENUM --> TSK
    ENUM --> STM
    ENUM --> PAG
    ENUM --> IMG
    ENUM --> STD
    ENUM --> STDB
    ENUM --> RES_AREA
    ENUM --> SCAF
    ENUM --> GOALS
    ENUM --> PRAC
    ENUM --> IPROM
    ENUM --> ISEG
    
    META --> RES
    META --> MOD
    META --> ACT
    META --> TSK
    META --> PAG
    META --> IMG
    META --> STD
    
    RES --> MOD
    MOD --> TOP
    TOP --> LES
    LES --> ACT
    ACT --> TSK
    TSK --> STM
    
    style PRIM fill:#e1f5ff
    style ENUM fill:#e1f5ff
    style META fill:#e1f5ff
    style RES fill:#4a90e2,color:#fff
    style MOD fill:#f5a623
    style TOP fill:#bd10e0,color:#fff
    style LES fill:#7ed321
    style ACT fill:#50e3c2
    style TSK fill:#ff6b6b
    style STM fill:#4ecdc4
```

### Import Resolution Order

1. **Level 1 (Foundation)**
   - `primitives.json` - Basic types
   - `enums.json` - Enumerated values

2. **Level 2 (Common)**
   - `metadata.json` - Metadata structures (depends on enums, primitives)

3. **Level 3 (Supporting)**
   - `standard.json`
   - `image.json`
   - `response-area.json`
   - `scaffolding.json`

4. **Level 4 (Composite)**
   - `standards-block.json` (depends on standard)
   - `activity-goals.json` (depends on standard)

5. **Level 5 (Content)**
   - `stem.json` (depends on response-area, image)
   - `task.json` (depends on stem, scaffolding)
   - `activity.json` (depends on task, activity-goals, scaffolding)
   - `lesson.json` (depends on activity, standards-block)
   - `topic.json` (depends on lesson)
   - `module.json` (depends on topic)
   - `resource.json` (depends on module, page, standard)

6. **Level 6 (Layout & Instructional)**
   - `page.json`
   - `practice-section.json`
   - `instructional-prompt.json`
   - `instructional-segment.json`

## Design Principles

### 1. Single Responsibility

Each schema represents a single, well-defined concept:
- **Resource**: Book-level properties only
- **Lesson**: Lesson-specific content
- **Activity**: Individual learning experience
- Each entity has clear boundaries and responsibilities

### 2. Composition Over Inheritance

Content is built through composition:
- Resources contain references to modules
- Modules contain references to topics
- Activities contain references to tasks
- Enables flexible recombination

### 3. Explicit Relationships

All relationships are explicit through UUID references:
- Parent-child: `parentId` fields
- Cross-references: Reference objects with `id` and `type`
- Teacher-student: `TeacherStudentLink` objects
- No implicit relationships or conventions

### 4. Metadata Separation

Metadata is separated into reusable structures:
- Publishing metadata
- Localization info
- Copyright info
- Accessibility info
- Prevents duplication across schemas

### 5. Extensibility

The system supports extension:
- Enum values can be added for new types
- Metadata objects are flexible
- Image types are extensible
- Standards bodies can be added

### 6. Validation at Every Level

Each schema includes:
- Required fields
- Type constraints
- Pattern validation (UUIDs, dates)
- Conditional requirements
- Ensures data integrity

### 7. Localization First

Built-in support for multiple languages and locales:
- Language and locale fields in metadata
- Cultural adaptation tracking
- Translation status management
- State-specific variations

### 8. Accessibility by Design

Accessibility is integrated:
- Alt text required for images
- Long descriptions for complex visuals
- Accessibility info structures
- Screen reader compatibility flags

zw