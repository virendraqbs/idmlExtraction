# Data Architecture

## Table of Contents

1. [Overview](#overview)
2. [Directory Structure](#directory-structure)
3. [File Organization Patterns](#file-organization-patterns)
4. [Naming Conventions](#naming-conventions)
5. [Storage Recommendations](#storage-recommendations)
6. [Database Schema](#database-schema)
7. [File Management](#file-management)

---

## Overview

The data architecture defines how schema-compliant content is organized in the file system or database. This document provides recommendations for organizing educational content to support efficient development, validation, and publishing workflows.

### Key Principles

1. **Dual Hierarchy Support**: Organization must support both physical layout (pages) and logical content (modules)
2. **Module-Resource Linking**: Clear structure showing module references to resources
3. **Clear Separation**: Separate content, media, and schemas
4. **Reusability**: Shared resources in common locations
5. **Versioning**: Support multiple versions and editions
6. **Localization**: Accommodate multiple languages and locales

### Understanding the Dual Hierarchy in File Organization

**Physical Layout (Pages)**:
```
Resource → Pages → References to Content Blocks
```
Pages are stored with resources and reference content by ID.

**Logical Content (Modules)**:
```
Module (resourceId links to Resource) → Topic → Lesson → Activity → Task → Stem
```
Content starts at module level with explicit resource link for context.

---

## Directory Structure

### Recommended Top-Level Structure

```
educational-content/
├── schemas/                    # JSON Schema definitions
│   ├── common/                # Common schemas
│   │   ├── primitives.json
│   │   ├── enums.json
│   │   └── metadata.json
│   ├── content/               # Content schemas
│   │   ├── resource.json
│   │   ├── module.json
│   │   ├── topic.json
│   │   ├── lesson.json
│   │   ├── activity.json
│   │   ├── task.json
│   │   ├── stem.json
│   │   └── practice-section.json
│   ├── instructional/         # Instructional schemas
│   │   ├── standard.json
│   │   ├── standards-block.json
│   │   ├── instructional-prompt.json
│   │   └── instructional-segment.json
│   ├── media/                 # Media schemas
│   │   └── image.json
│   └── response/              # Response schemas
│       ├── response-area.json
│       ├── scaffolding.json
│       └── activity-goals.json
│
├── content/                   # Actual content files
│   ├── grade-k/
│   ├── grade-1/
│   ├── grade-2/
│   ├── grade-3/
│   ├── grade-4/
│   │   ├── resources/         # Resource-level files
│   │   │   ├── srb-2024.json
│   │   │   ├── spb-2024.json
│   │   │   └── tig-2024.json
│   │   ├── modules/           # Module files
│   │   │   ├── module-1/
│   │   │   │   ├── module.json
│   │   │   │   ├── topics/
│   │   │   │   │   ├── topic-1/
│   │   │   │   │   │   ├── topic.json
│   │   │   │   │   │   └── lessons/
│   │   │   │   │   │       ├── lesson-1/
│   │   │   │   │   │       │   ├── lesson.json
│   │   │   │   │   │       │   ├── activities/
│   │   │   │   │   │       │   │   ├── activate.json
│   │   │   │   │   │       │   │   ├── explore.json
│   │   │   │   │   │       │   │   └── reflect.json
│   │   │   │   │   │       │   ├── tasks/
│   │   │   │   │   │       │   │   ├── task-1.json
│   │   │   │   │   │       │   │   ├── task-2.json
│   │   │   │   │   │       │   │   └── stems/
│   │   │   │   │   │       │   │       ├── stem-1-1.json
│   │   │   │   │   │       │   │       └── stem-1-2.json
│   │   │   │   │   │       │   └── standards-block.json
│   │   │   │   │   │       ├── lesson-2/
│   │   │   │   │   │       └── lesson-3/
│   │   │   │   │   └── topic-2/
│   │   │   │   └── images/
│   │   │   ├── module-2/
│   │   │   └── module-3/
│   │   ├── standards/         # Standards definitions
│   │   │   ├── ccss/
│   │   │   │   ├── 4.NBT.1.json
│   │   │   │   ├── 4.NBT.2.json
│   │   │   │   └── ...
│   │   │   ├── ca-ccss/
│   │   │   └── teks/
│   │   ├── pages/             # Page layouts
│   │   │   ├── srb/
│   │   │   │   ├── page-001.json
│   │   │   │   ├── page-002.json
│   │   │   │   └── ...
│   │   │   ├── spb/
│   │   │   └── tig/
│   │   └── practice/          # Practice sections
│   │       ├── lesson-1-practice.json
│   │       └── ...
│   └── grade-5/
│
├── media/                     # Media assets
│   ├── images/
│   │   ├── covers/
│   │   │   ├── module-covers/
│   │   │   ├── topic-covers/
│   │   │   └── lesson-covers/
│   │   ├── instructional/
│   │   │   ├── grade-4/
│   │   │   │   ├── module-1/
│   │   │   │   │   ├── place-value-chart.png
│   │   │   │   │   └── base-ten-blocks.png
│   │   │   │   └── module-2/
│   │   │   └── grade-5/
│   │   ├── technical-art/
│   │   │   ├── number-lines/
│   │   │   ├── graphs/
│   │   │   ├── shapes/
│   │   │   └── tables/
│   │   ├── characters/
│   │   │   ├── support-characters/
│   │   │   └── avatars/
│   │   └── decorative/
│   ├── image-catalog/         # Image metadata files
│   │   ├── grade-4/
│   │   │   ├── module-1/
│   │   │   │   ├── image-001.json
│   │   │   │   └── image-002.json
│   │   │   └── module-2/
│   │   └── shared/            # Reusable images
│   └── source-files/          # Original design files
│       ├── illustrator/
│       ├── photoshop/
│       └── sketch/
│
├── localization/              # Translated content
│   ├── es-US/                 # Spanish (US)
│   │   └── grade-4/
│   │       └── modules/
│   ├── es-MX/                 # Spanish (Mexico)
│   └── fr-CA/                 # French (Canada)
│
├── output/                    # Generated/published files
│   ├── pdf/
│   ├── web/
│   └── print/
│
├── tools/                     # Validation and build tools
│   ├── validators/
│   │   ├── schema-validator.js
│   │   ├── reference-validator.js
│   │   └── sequence-validator.js
│   ├── generators/
│   │   ├── uuid-generator.js
│   │   └── template-generator.js
│   └── builders/
│       ├── pdf-builder.js
│       └── web-builder.js
│
└── docs/                      # Documentation
    ├── README.md
    ├── ARCHITECTURE.md
    ├── SCHEMA_REFERENCE.md
    ├── IMPLEMENTATION_GUIDE.md
    ├── IMPLEMENTATION_EXAMPLES.md
    └── DATA_ARCHITECTURE.md
```

---

## File Organization Patterns

### Pattern 1: Hierarchical Content Organization

Organize content files to mirror the logical hierarchy:

```
grade-4/
└── modules/
    └── module-1/
        ├── module.json              # Module definition
        ├── topics/
        │   └── topic-1/
        │       ├── topic.json       # Topic definition
        │       └── lessons/
        │           └── lesson-1/
        │               ├── lesson.json        # Lesson definition
        │               ├── activities/        # Activity files
        │               ├── tasks/            # Task and stem files
        │               └── standards-block.json
```

**Benefits**:
- Easy to navigate
- Reflects content structure
- Clear parent-child relationships

### Pattern 2: Flat File Organization

For smaller projects or easier database import:

```
grade-4/
├── resources/
│   ├── srb-2024.json
│   ├── spb-2024.json
│   └── tig-2024.json
├── modules/
│   ├── module-1.json
│   ├── module-2.json
│   └── module-3.json
├── topics/
│   ├── topic-1-1.json  # Module 1, Topic 1
│   ├── topic-1-2.json
│   └── topic-2-1.json
├── lessons/
│   ├── lesson-1-1-1.json  # Module 1, Topic 1, Lesson 1
│   └── ...
└── activities/
    ├── activity-1-1-1-activate.json
    └── ...
```

**Benefits**:
- Easier to import into database
- Simpler file management
- Better for automated processing

### Pattern 3: Resource-Centric Organization

Organize by publication type:

```
grade-4/
├── student-resource-book/
│   ├── resource.json
│   ├── modules/
│   ├── pages/
│   └── content/
├── student-practice-book/
│   ├── resource.json
│   ├── practice-sections/
│   └── pages/
└── teacher-implementation-guide/
    ├── resource.json
    ├── instructional-content/
    ├── pages/
    └── links-to-student-content.json
```

**Benefits**:
- Clear publication boundaries
- Easier to manage separate books
- Good for independent publication workflows

---

## Naming Conventions

### File Naming

**General Pattern**: `{type}-{identifier}.json`

**Examples**:
```
resource-grade4-srb.json
module-1.json
topic-1-2.json
lesson-1-2-3.json
activity-1-2-3-activate.json
task-1-2-3-1.json
stem-1-2-3-1-a.json
image-place-value-chart.json
standard-ccss-4nbt2.json
```

**Rules**:
- Use lowercase
- Use hyphens for separation
- Include identifying numbers
- Be descriptive but concise
- Use consistent prefixes

### Directory Naming

```
modules/         (plural)
module-1/        (singular with number)
topics/          (plural)
activities/      (plural)
```

**Rules**:
- Collection directories: plural
- Instance directories: singular with identifier
- Use hyphens, not underscores
- Avoid spaces

---