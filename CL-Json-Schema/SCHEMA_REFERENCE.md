# Schema Reference

## Table of Contents

- [Common Schemas](#common-schemas)
  - [primitives.json](#primitivesjson)
  - [enums.json](#enumsjson)
  - [metadata.json](#metadatajson)
- [Content Schemas](#content-schemas)
  - [resource.json](#resourcejson)
  - [module.json](#modulejson)
  - [topic.json](#topicjson)
  - [lesson.json](#lessonjson)
  - [activity.json](#activityjson)
  - [task.json](#taskjson)
  - [stem.json](#stemjson)
- [Layout Schemas](#layout-schemas)
  - [page.json](#pagejson)
- [Standards Schemas](#standards-schemas)
  - [standard.json](#standardjson)
  - [standards-block.json](#standards-blockjson)
- [Media Schemas](#media-schemas)
  - [image.json](#imagejson)
- [Response Schemas](#response-schemas)
  - [response-area.json](#response-areajson)
  - [scaffolding.json](#scaffoldingjson)
  - [activity-goals.json](#activity-goalsjson)
- [Practice Schemas](#practice-schemas)
  - [practice-section.json](#practice-sectionjson)
- [Instructional Schemas](#instructional-schemas)
  - [instructional-prompt.json](#instructional-promptjson)
  - [instructional-segment.json](#instructional-segmentjson)

---

## Common Schemas

### primitives.json

**Purpose**: Defines fundamental data types used across all schemas.

**Definitions**:

#### UUID
```json
{
  "type": "string",
  "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
}
```
- Standard UUID format (8-4-4-4-12 hexadecimal)
- Used as unique identifier for all entities
- Example: `"550e8400-e29b-41d4-a716-446655440000"`

#### Reference
```json
{
  "type": "object",
  "properties": {
    "id": { "$ref": "#/definitions/UUID" },
    "type": { "$ref": "../common/enums.json#/definitions/ReferenceType" }
  },
  "required": ["id", "type"]
}
```
- Used to reference other entities
- Type indicates what kind of entity is referenced
- Enables type-safe references

#### Image
```json
{
  "type": "object",
  "properties": {
    "id": { "$ref": "#/definitions/UUID" },
    "type": { "$ref": "../common/enums.json#/definitions/ImageType" },
    "url": { "type": "string", "format": "uri" },
    "altText": { "type": "string" },
    "caption": { "type": "string" }
  },
  "required": ["id", "type", "altText"]
}
```
- Embedded image reference
- Alt text required for accessibility
- Can include optional caption

---

### enums.json

**Purpose**: Defines all enumerated types used throughout the system.

**Key Enumerations**:

#### Language
```
"en", "es", "fr", "de", "zh", "it"
```
- ISO 639-1 language codes
- Used for internationalization

#### Locale
```
"en-US", "es-US"
```
- Full locale identifiers
- Language + region combination

#### State
All 50 US state codes:
```
"AL", "AK", "AZ", ... "WY"
```
- Used for state-specific content variations

#### StandardsBody
```
"CCSS", "CA_CCSS", "TEKS", "BEST"
```
- Common Core State Standards
- California Common Core State Standards
- Texas Essential Knowledge and Skills
- Florida BEST Standards

#### ResourceType
```
"STUDENT_RESOURCE_BOOK", "STUDENT_PRACTICE_BOOK", "TEACHER_IMPLEMENTATION_GUIDE"
```
- Three main publication types

#### PageType
46 specific page types including:
- **SRB_**: Student Resource Book pages (TOC, lesson pages, summaries)
- **SPB_**: Student Practice Book pages (practice, continued pages)
- **TIG_**: Teacher Implementation Guide pages (overviews, guidance)

Examples:
```
"SRB_LESSON_INTRODUCTION_ACTIVATE"
"SPB_LESSON_PRACTICE"
"TIG_LESSON_OVERVIEW"
```

#### ActivityType
```
"ACTIVATE", "EXPLORE", "REFLECT", "KEY_TERMS", "KEY_IDEAS", 
"PRACTICE_QUESTIONS", "PRACTICE_CONVERSATION_STARTERS", 
"GAMES_AND_ADDITIONAL_RESOURCES"
```
- Lesson activities: Activate → Explore → Reflect
- Practice activities: Key terms, practice questions, games

#### TaskType
```
"COMPLETION", "CALCULATION", "STRATEGY_ANALYSIS", "MULTIPLE_CHOICE", 
"SHORT_ANSWER", "WORD_PROBLEM", "OPEN_ENDED"
```
- Different question/problem formats

#### ResponseAreaType
```
"STEM", "OPEN_ENDED", "CROSS_NUMBER_PUZZLE", "NUMBER_LINE", 
"GRID", "ALGORITHM_WORKSPACE"
```
- Different ways students provide answers

#### ImageType
```
"MODULE_COVER", "TOPIC_COVER", "LESSON_COVER", "INSTRUCTIONAL", 
"DECORATIVE", "TECHNICAL_ART", "CHARACTER_SUPPORT", "MANIPULATIVE", "ICON"
```

#### TechnicalArtType
```
"NUMBER_LINES", "BAR_GRAPHS", "WOLS", "SHAPES_OUTLINED", "SHAPES_FILLED", 
"SHAPES_3D", "TABLES", "CLOCKS", "SHAPES_GRID", "PLACE_VALUE", 
"CROSS_NUMBER_PUZZLES", "BAR_AND_LINE_GRAPHS", "COUNTING_CHART", 
"SPINNER_CHARTS", "SHAPES_GRIDS_AND_COUNTERS", "SHAPES_ANGLE_MEASUREMENTS"
```
- Specific types of technical art/diagrams

#### InstructionalPromptType
```
"LEARNING_GOALS", "LANGUAGE_GOALS", "DAILY_MATH_ROUTINES", 
"MULTILINGUAL_LEARNER_SUPPORT", "TEACHER_STORY", "HABITS_OF_MIND", 
"STUDENT_LOOK_FORS", "CULTIVATE_CONNECTIONS", 
"STUDENT_EDITION_PAGE_IMAGE", "MATERIALS_LIST"
```

#### InstructionalSegmentType
```
"INTRODUCTION", "ABOUT_THE_MATH", "LESSON_STRUCTURE_AND_PACING", 
"SETTING_THE_STAGE", "TASK", "CLOSING", "DIFFERENTIATION_STRATEGY", 
"ONGOING_ASSESSMENT", "LANGUAGE_LINK"
```

#### RelationshipType
```
"MIRRORS", "EXTENDS", "SUPPORTS", "ANSWERS", "REFERENCES"
```
- Describes teacher-student content relationships

#### Status
```
"NOT_STARTED", "IN_PROGRESS", "COMPLETE", "REVIEWED", "PUBLISHED"
```
- Content workflow states

---

### metadata.json

**Purpose**: Reusable metadata structures used across multiple schemas.

**Key Definitions**:

#### PageNumberRepresentations
```json
{
  "numeric": 165,
  "romanNumeral": "CLXV",
  "wordForm": "one hundred sixty-five",
  "primeFactorization": "3 × 5 × 11"
}
```
- Educational feature: multiple representations
- Only `numeric` is required

#### LessonContext
```json
{
  "moduleNumber": 1,
  "moduleTitle": "Place Value",
  "topicNumber": 2,
  "topicTitle": "Understanding Digits",
  "lessonNumber": 3,
  "lessonTitle": "Tens and Ones"
}
```
- Provides curriculum placement context

#### PacingEstimate
```json
{
  "value": 45,
  "range": {
    "min": 40,
    "max": 50
  }
}
```
- Time estimates in minutes
- Can be single value or range

#### ISBN
```json
{
  "isbn13": "978-1-234-56789-0",
  "isbn10": "1234567890"
}
```
- Standard book identifiers

#### CopyrightInfo
```json
{
  "year": 2024,
  "holder": "Educational Publisher Inc.",
  "statement": "© 2024 All Rights Reserved",
  "license": "All Rights Reserved",
  "permissions": {
    "canCopy": false,
    "canModify": false,
    "canDistribute": false,
    "commercialUse": false
  }
}
```

#### TeacherStudentLink
```json
{
  "studentPublicationId": "uuid",
  "studentPageId": "uuid",
  "studentActivityId": "uuid",
  "studentTaskId": "uuid",
  "linkType": "MIRRORS",
  "notes": "Direct correspondence"
}
```
- Links teacher guide content to student content
- `linkType` required, IDs optional based on granularity

#### LocalizationInfo
```json
{
  "language": "es",
  "locale": "es-US",
  "state": "CA",
  "translationStatus": "REVIEWED",
  "translatedBy": "Translation Service Inc.",
  "translatedDate": "2024-06-15",
  "reviewedBy": "Maria Garcia",
  "reviewedDate": "2024-06-20",
  "culturalAdaptations": [
    "Changed currency to pesos",
    "Adapted cultural references"
  ]
}
```

#### DifferentiationStrategies
```json
{
  "advanced": "For advanced students, extend to 6-digit numbers",
  "ell": "Provide visual aids and sentence frames"
}
```

#### PublishingMetadata
```json
{
  "version": "1.2.0",
  "edition": "2024",
  "publishedDate": "2024-01-15",
  "lastModifiedDate": "2024-06-20T10:30:00Z",
  "lastModifiedBy": "john.smith@publisher.com",
  "status": "PUBLISHED",
  "reviewers": [
    {
      "name": "Jane Doe",
      "role": "Content Editor",
      "date": "2024-06-18",
      "approved": true
    }
  ]
}
```

---

## Content Schemas

### resource.json

**Purpose**: Top-level container representing a physical book or publication. Provides context (state, standards body, grade level) for modules and manages physical page layout.

**Required Fields**: `id`, `resourceType`, `title`, `gradeLevel`

**Key Properties**:

- **resourceType**: One of `STUDENT_RESOURCE_BOOK`, `STUDENT_PRACTICE_BOOK`, `TEACHER_IMPLEMENTATION_GUIDE`
- **title**: Main resource title (e.g., "Grade 4 Mathematics")
- **subtitle**: Additional descriptive text
- **gradeLevel**: "K", "1", "2", "3", "4", "5"
- **series**: Series name (e.g., "Math Expressions")
- **edition**: Edition identifier (e.g., "2024")
- **publisher**: Publisher name
- **isbn**: ISBN information object
- **pages**: Array of page references (physical layout hierarchy)
- **modules**: Array of module references (for context - modules link back via resourceId)
- **learningGoals**: Resource-level learning goals
- **standards**: Resource-level standards alignment

**Dual Role of Resource**:

1. **Context Provider**: Modules link to resource via `resourceId` to get:
   - State context (CA, TX, FL, etc.)
   - Standards body (CCSS, CA_CCSS, TEKS, BEST)
   - Grade level and edition
   - Publisher and series information

2. **Physical Layout Manager**: 
   - Contains references to all pages
   - Pages reference content blocks (modules, topics, lessons, activities) for display
   - Manages book structure and presentation

**Resource-Module Relationship**:
```json
// Resource references modules for awareness
"modules": [
  { "id": "module-1-uuid", "type": "MODULE", "sequenceNumber": 1 }
]

// Modules reference resource for context
// (in module.json)
"resourceId": "resource-uuid"
```

**Teacher-Specific**:
```json
"teacherGuidance": {
  "linkedStudentResource": {
    "studentPublicationId": "uuid",
    "linkType": "MIRRORS"
  },
  "scopeAndSequence": "Overview text",
  "pacing": "Suggested pacing guidance"
}
```

**Presentation Properties**:
```json
"presentation": {
  "pageSize": "LETTER",
  "orientation": "PORTRAIT",
  "binding": "LEFT",
  "coverColor": "#3498db",
  "theme": "STANDARD"
}
```

**Example**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "resourceType": "STUDENT_RESOURCE_BOOK",
  "title": "Grade 4 Mathematics",
  "subtitle": "Student Resource Book",
  "gradeLevel": "4",
  "series": "Math Expressions",
  "edition": "2024",
  "publisher": "Educational Publisher Inc.",
  "isbn": {
    "isbn13": "978-1-234-56789-0"
  },
  "pages": [
    { "id": "page-uuid-1", "type": "PAGES" },
    { "id": "page-uuid-2", "type": "PAGES" }
  ],
  "modules": [
    { "id": "module-uuid-1", "type": "MODULE", "sequenceNumber": 1 },
    { "id": "module-uuid-2", "type": "MODULE", "sequenceNumber": 2 }
  ],
  "metadata": {
    "localizationInfo": {
      "state": "CA",
      "locale": "en-US"
    }
  }
}
```

---

### module.json

**Purpose**: Major curriculum unit containing multiple topics. Modules link to Resources for context (state, standards body, grade level) but serve as the starting point for logical content hierarchy.

**Required Fields**: `id`, `moduleNumber`, `title`, `gradeLevel`, `resourceId`

**Key Properties**:

- **resourceId**: UUID linking to parent Resource (provides context like state, standards body)
- **moduleNumber**: Numeric identifier (1, 2, 3, ...)
- **title**: Module title (e.g., "Addition and Subtraction")
- **moduleSummary**: Brief overview
- **gradeLevel**: Grade level identifier (inherits from resource but can be explicit)
- **standardsBody**: Standards framework (e.g., "CCSS") - typically inherited from resource
- **topics**: Ordered array of topic references with sequence numbers
- **images**: Module-level images (covers, diagrams)

**Resource Link Importance**:
The `resourceId` field is critical because it:
- Links module to specific edition and publication
- Provides state context (CA, TX, FL, etc.)
- Defines which standards body applies
- Enables same module content to be used in multiple resources with different contexts

**Metadata**:
```json
"metadata": {
  "pacingEstimate": {
    "value": 900,
    "range": { "min": 850, "max": 950 }
  },
  "localizationInfo": {
    "language": "en",
    "locale": "en-US"
  }
}
```

**Example**:
```json
{
  "id": "module-uuid-1",
  "resourceId": "resource-uuid",  // Critical: links to Resource for context
  "standardsBody": "CCSS",
  "moduleNumber": 1,
  "title": "Place Value, Addition, and Subtraction",
  "moduleSummary": "Students build understanding of place value...",
  "gradeLevel": "4",
  "topics": [
    { 
      "id": "topic-uuid-1", 
      "type": "TOPIC", 
      "sequenceNumber": 1 
    },
    { 
      "id": "topic-uuid-2", 
      "type": "TOPIC", 
      "sequenceNumber": 2 
    }
  ]
}
```

---

### topic.json

**Purpose**: Specific subject area within a module containing lessons.

**Required Fields**: `id`, `topicNumber`, `title`, `moduleId`

**Key Properties**:

- **topicNumber**: Numeric identifier within module
- **title**: Topic title
- **topicSummary**: Brief overview
- **lessons**: Ordered array of lesson references
- **images**: Topic-level images

**Example**:
```json
{
  "id": "topic-uuid-1",
  "moduleId": "module-uuid-1",
  "topicNumber": 1,
  "title": "Understanding Place Value",
  "topicSummary": "Students explore the meaning of digits...",
  "lessons": [
    { "id": "lesson-uuid-1", "type": "LESSON" },
    { "id": "lesson-uuid-2", "type": "LESSON" }
  ],
  "metadata": {
    "pacingEstimate": { "value": 300 }
  }
}
```

---

### lesson.json

**Purpose**: Individual instructional session containing activities.

**Required Fields**: `id`, `lessonNumber`, `title`, `topicId`

**Key Properties**:

- **lessonNumber**: Numeric identifier within topic
- **title**: Lesson title
- **lessonSummary**: Brief overview
- **learningGoals**: Array of learning goal strings
- **standardsBlock**: Reference to standards block
- **activities**: Ordered array of activity references
- **images**: Lesson-level images

**Example**:
```json
{
  "id": "lesson-uuid-1",
  "topicId": "topic-uuid-1",
  "lessonNumber": 1,
  "title": "Represent Numbers to 10,000",
  "lessonSummary": "Students use place value models...",
  "learningGoals": [
    "Understand that digits in a 4-digit number represent amounts",
    "Compare numbers using place value understanding"
  ],
  "standardsBlock": "standards-block-uuid",
  "activities": [
    { 
      "id": "activity-uuid-1", 
      "type": "ACTIVITY", 
      "sequenceNumber": 1 
    },
    { 
      "id": "activity-uuid-2", 
      "type": "ACTIVITY", 
      "sequenceNumber": 2 
    },
    { 
      "id": "activity-uuid-3", 
      "type": "ACTIVITY", 
      "sequenceNumber": 3 
    }
  ],
  "metadata": {
    "pacingEstimate": { 
      "value": 45,
      "range": { "min": 40, "max": 50 }
    }
  }
}
```

---

### activity.json

**Purpose**: Learning experience within a lesson (Activate, Explore, Reflect).

**Required Fields**: `id`, `activityType`, `lessonId`

**Key Properties**:

- **activityType**: `ACTIVATE`, `EXPLORE`, `REFLECT`, or practice types
- **title**: Activity title
- **directions**: Ordered array of direction objects
- **tasks**: Ordered array of task references
- **goals**: References to activity-specific learning goals
- **scaffolding**: References to learning supports
- **images**: Activity-level images

**Direction Object**:
```json
{
  "sequenceNumber": 1,
  "type": "DIRECTION_LINE",
  "text": "Work with a partner to solve..."
}
```

**Teacher Guidance** (TIG only):
```json
"teacherGuidance": {
  "linkedStudentActivity": {
    "studentActivityId": "uuid",
    "linkType": "MIRRORS"
  },
  "instructionType": "WHOLE_CLASS",
  "instructionalText": "Begin by asking students...",
  "teacherPrompts": [
    { "id": "prompt-uuid-1", "type": "INSTRUCTIONAL_PROMPT" }
  ],
  "differentiationStrategies": {
    "advanced": "Challenge advanced students with...",
    "ell": "Support ELL students by..."
  }
}
```

**Example**:
```json
{
  "id": "activity-uuid-1",
  "lessonId": "lesson-uuid-1",
  "activityType": "ACTIVATE",
  "title": "Represent Numbers with Base Ten Blocks",
  "directions": [
    {
      "sequenceNumber": 1,
      "type": "DIRECTION_LINE",
      "text": "Use base ten blocks to represent the number 2,456"
    }
  ],
  "tasks": [
    { 
      "id": "task-uuid-1", 
      "type": "TASK", 
      "sequenceNumber": 1 
    }
  ],
  "goals": [
    { "id": "goal-uuid-1", "type": "GOALS" }
  ],
  "metadata": {
    "pacingEstimate": { "value": 15 }
  }
}
```

---

### task.json

**Purpose**: Specific question or problem within an activity.

**Required Fields**: `id`, `taskNumber`, `taskType`, `activityId`, `stem`

**Key Properties**:

- **taskNumber**: Identifier (e.g., "1", "2a", "3")
- **taskType**: Type of task (see TaskType enum)
- **stems**: Ordered array of stem references
- **scaffolding**: Optional learning supports

**Teacher Guidance**:
```json
"teacherGuidance": {
  "linkedStudentTask": {
    "studentTaskId": "uuid",
    "linkType": "ANSWERS"
  }
}
```

**Example**:
```json
{
  "id": "task-uuid-1",
  "activityId": "activity-uuid-1",
  "taskNumber": "1",
  "taskType": "COMPLETION",
  "stems": [
    { 
      "id": "stem-uuid-1", 
      "type": "STEM", 
      "sequenceNumber": 1 
    },
    { 
      "id": "stem-uuid-2", 
      "type": "STEM", 
      "sequenceNumber": 2 
    }
  ]
}
```

---

### stem.json

**Purpose**: Individual question prompt with response area.

**Required Fields**: `id`, `stemType`, `taskId`

**Key Properties**:

- **stemType**: `TEXT_ONLY`, `TEXT_WITH_IMAGE`, `TEXT_WITH_RESPONSE_AREA`
- **ancillaryText**: Supporting text (e.g., character names)
- **stemText**: The actual question or prompt
- **image**: Optional image reference
- **responseArea**: Reference to response area

**Example**:
```json
{
  "id": "stem-uuid-1",
  "taskId": "task-uuid-1",
  "stemType": "TEXT_WITH_RESPONSE_AREA",
  "stemText": "What digit is in the hundreds place?",
  "responseArea": "response-area-uuid-1"
}
```

---

## Layout Schemas

### page.json

**Purpose**: Physical page in a publication. Pages bridge the physical layout and logical content hierarchies by referencing content blocks at any level (modules, topics, lessons, activities, tasks).

**Required Fields**: `id`, `pageNumber`, `pageType`, `resourceId`

**Key Properties**:

- **pageType**: Specific page type (see PageType enum)
- **contentBlocks**: Array of content block references - can reference any level of content hierarchy:
  - Modules (e.g., module introduction page)
  - Topics (e.g., topic overview)
  - Lessons (e.g., lesson start)
  - Activities (e.g., activity pages)
  - Tasks (e.g., specific problems)
  - Images, standards blocks, etc.
- **metadata**: Page number representations and lesson context

**Content Block References**:
Pages can reference content at any level of the hierarchy, enabling flexible layouts:
```json
"contentBlocks": [
  { "id": "module-1-uuid", "type": "MODULE" },      // Module intro
  { "id": "lesson-1-uuid", "type": "LESSON" },      // Lesson header
  { "id": "activity-1-uuid", "type": "ACTIVITY" },  // Activity content
  { "id": "image-1-uuid", "type": "IMAGE" }         // Supporting image
]
```

**Example**:
```json
{
  "id": "page-uuid-1",
  "resourceId": "resource-uuid",
  "pageType": "SRB_LESSON_INTRODUCTION_ACTIVATE",
  "contentBlocks": [
    { "id": "lesson-uuid-1", "type": "LESSON" },      // Lesson header info
    { "id": "activity-uuid-1", "type": "ACTIVITY" },  // Activate activity
    { "id": "image-uuid-1", "type": "IMAGE" }         // Header image
  ],
  "metadata": {
    "pageNumberRepresentations": {
      "numeric": 42,
      "romanNumeral": "XLII",
      "wordForm": "forty-two"
    },
    "lessonContext": {
      "moduleNumber": 1,
      "moduleTitle": "Place Value",
      "topicNumber": 2,
      "topicTitle": "Understanding Digits",
      "lessonNumber": 1,
      "lessonTitle": "Representing Numbers"
    }
  }
}
```

**Page Types and Content References**:
Different page types typically reference different content levels:
- `SRB_MODULE_INTRODUCTION`: References Module
- `SRB_LESSON_INTRODUCTION_ACTIVATE`: References Lesson + Activate Activity
- `SRB_LESSON_EXPLORE`: References Explore Activity + Tasks
- `TIG_LESSON_OVERVIEW`: References Lesson + Instructional Segments

---

## Standards Schemas

### standard.json

**Purpose**: Individual educational standard definition.

**Required Fields**: `id`, `body`, `code`, `gradeLevel`, `fullText`

**Key Properties**:

- **body**: Standards framework (CCSS, TEKS, etc.)
- **code**: Standard code (e.g., "4.NBT.4")
- **gradeLevel**: Grade level
- **domain**: Content domain
- **cluster**: Subcategory within domain
- **description**: Short description
- **fullText**: Complete standard text

**Example**:
```json
{
  "id": "standard-uuid-1",
  "body": "CCSS",
  "code": "4.NBT.2",
  "gradeLevel": "4",
  "domain": "Number and Operations in Base Ten",
  "cluster": "Generalize place value understanding for multi-digit whole numbers",
  "description": "Read and write multi-digit numbers using base-ten numerals",
  "fullText": "Read and write multi-digit whole numbers using base-ten numerals, number names, and expanded form. Compare two multi-digit numbers based on meanings of the digits in each place, using >, =, and < symbols to record the results of comparisons.",
  "metadata": {
    "publishedDate": "2010-06-02",
    "officialUrl": "http://www.corestandards.org/Math/Content/4/NBT/A/2/"
  }
}
```

---

### standards-block.json

**Purpose**: Grouped standards for display in lessons.

**Required Fields**: `id`, `gradeLevel`

**Key Properties**:

- **body**: Standards framework
- **title**: Display title (e.g., "California Standards")
- **conceptualOverlays**: Optional overlay statements
- **standards**: Ordered array of standard references
- **standardsSubtitle**: Subtitle for standards section
- **pageLocationHelpText**: Help text for finding standards

**Example**:
```json
{
  "id": "standards-block-uuid-1",
  "body": "CCSS",
  "gradeLevel": "4",
  "title": "Common Core Standards",
  "standardsSubtitle": "This lesson addresses:",
  "standards": [
    {
      "id": "standard-uuid-1",
      "type": "STANDARDS",
      "sequenceNumber": 1
    },
    {
      "id": "standard-uuid-2",
      "type": "STANDARDS",
      "sequenceNumber": 2
    }
  ],
  "conceptualOverlaySubtitle": "Big Ideas:",
  "conceptualOverlays": [
    {
      "sequenceNumber": 1,
      "text": "Place value is based on groups of ten"
    }
  ]
}
```

---

## Media Schemas

### image.json

**Purpose**: Image asset used in content.

**Required Fields**: `id`, `imageType`, `filename`, `altText` (unless decorative)

**Key Properties**:

- **imageType**: Type of image (see ImageType enum)
- **technicalArtType**: Specific type if `imageType` is `TECHNICAL_ART`
- **filename**: File name
- **filepath**: Relative path
- **url**: External URL
- **sourceFilename**: Original source file (.ai, .psd)
- **altText**: Accessibility text (required except for decorative images)
- **caption**: Display caption
- **dimensions**: Width, height, unit
- **format**: PNG, JPG, SVG, etc.

**Usage Tracking**:
```json
"usage": {
  "usedInPages": [42, 43],
  "usedInActivities": [
    { "id": "activity-uuid-1", "type": "ACTIVITY" }
  ],
  "usedInTasks": [
    { "id": "task-uuid-1", "type": "TASK" }
  ],
  "isReusable": true
}
```

**Accessibility**:
```json
"accessibility": {
  "isDecorative": false,
  "longDescription": "Detailed description for complex image",
  "transcriptUrl": "https://example.com/transcript"
}
```

**Copyright**:
```json
"copyright": {
  "holder": "Educational Publisher Inc.",
  "year": 2024,
  "license": "All Rights Reserved",
  "attribution": "Created by Jane Doe",
  "source": "Original"
}
```

**Example**:
```json
{
  "id": "image-uuid-1",
  "imageType": "TECHNICAL_ART",
  "technicalArtType": "PLACE_VALUE",
  "filename": "place-value-chart.png",
  "filepath": "images/module1/place-value-chart.png",
  "altText": "Place value chart showing thousands, hundreds, tens, and ones columns",
  "caption": "Figure 1: Place Value Chart",
  "dimensions": {
    "width": 800,
    "height": 600,
    "unit": "PIXELS"
  },
  "format": "PNG",
  "usage": {
    "usedInActivities": [
      { "id": "activity-uuid-1", "type": "ACTIVITY" }
    ],
    "isReusable": true
  }
}
```

---

## Response Schemas

### response-area.json

**Purpose**: Area where students provide answers.

**Required Fields**: `id`, `type`

**Key Properties**:

- **type**: Response area type (see ResponseAreaType enum)
- **description**: Description of the area
- **specifications**: Type-specific configuration

**Grid Specification** (for GRID, CROSS_NUMBER_PUZZLE):
```json
"specifications": {
  "grid": {
    "gridDimensions": {
      "rows": 5,
      "columns": 5
    },
    "gridStructure": [
      {
        "row": 0,
        "col": 0,
        "editable": false,
        "displayValue": "2",
        "style": "bold"
      },
      {
        "row": 0,
        "col": 1,
        "editable": true,
        "expectedValue": "4"
      }
    ]
  }
}
```

**Number Line Specification**:
```json
"specifications": {
  "numberLineRange": {
    "min": 0,
    "max": 100,
    "increment": 10
  }
}
```

**Algorithm Workspace**:
```json
"specifications": {
  "algorithmType": "LONG_DIVISION",
  "allowedTools": ["CALCULATOR"]
}
```

**Example**:
```json
{
  "id": "response-area-uuid-1",
  "type": "OPEN_ENDED",
  "description": "Write your answer",
  "specifications": {
    "textAreaLines": 3
  }
}
```

---

### scaffolding.json

**Purpose**: Learning support for students.

**Required Fields**: `id`, `scaffoldingType`, `content`

**Key Properties**:

- **scaffoldingType**: Type of support (e.g., `CHARACTER_SUPPORT`)
- **content**: Support text or guidance
- **image**: Optional supporting image

**Example**:
```json
{
  "id": "scaffolding-uuid-1",
  "scaffoldingType": "CHARACTER_SUPPORT",
  "content": "Remember to start with the ones place!",
  "image": "character-image-uuid"
}
```

---

### activity-goals.json

**Purpose**: Learning goals for activities.

**Required Fields**: `id`, `goalType`, `activityId`

**Key Properties**:

- **goalType**: Type of goal (see GoalType enum)
- **goalItems**: Array of goal statements
- **standards**: References to aligned standards

**Example**:
```json
{
  "id": "goal-uuid-1",
  "activityId": "activity-uuid-1",
  "goalType": "HABITS_OF_MIND",
  "goalItems": [
    "Make sense of problems and persevere in solving them",
    "Reason abstractly and quantitatively"
  ],
  "standards": [
    { "id": "standard-uuid-1", "type": "STANDARDS" }
  ]
}
```

---

## Practice Schemas

### practice-section.json

**Purpose**: Section containing practice activities.

**Required Fields**: `id`, `parentId`, `practiceSectionType`

**Key Properties**:

- **practiceSectionType**: `LESSON_PRACTICE`, `FAMILY_GUIDE`
- **title**: Section title
- **activities**: Ordered array of practice activity references

**Example**:
```json
{
  "id": "practice-section-uuid-1",
  "parentId": "lesson-uuid-1",
  "practiceSectionType": "LESSON_PRACTICE",
  "title": "Practice: Place Value",
  "activities": [
    {
      "id": "activity-uuid-10",
      "type": "ACTIVITY",
      "sequenceNumber": 1
    },
    {
      "id": "activity-uuid-11",
      "type": "ACTIVITY",
      "sequenceNumber": 2
    }
  ]
}
```

---

## Instructional Schemas

### instructional-prompt.json

**Purpose**: Teacher guidance elements (learning goals, language goals, etc.).

**Required Fields**: `id`, `instructionalPromptType`

**Key Properties**:

- **instructionalPromptType**: Type of prompt (see enum)
- **studentContentReferenceId**: Reference to associated student content
- **title**: Optional title
- **content**: Prompt text (if not in list form)
- **contentItems**: List items (if in list form)
- **images**: Associated images

**Example**:
```json
{
  "id": "prompt-uuid-1",
  "studentContentReferenceId": "lesson-uuid-1",
  "instructionalPromptType": "LEARNING_GOALS",
  "title": "Learning Goals",
  "contentItems": [
    "Understand place value to 10,000",
    "Read and write numbers in multiple forms"
  ]
}
```

---

### instructional-segment.json

**Purpose**: Instructional guide sections for teachers.

**Required Fields**: `id`, `instructionalSegmentType`

**Key Properties**:

- **instructionalSegmentType**: Type of segment (see enum)
- **studentContentReferenceId**: Reference to student content
- **directions**: Ordered array of instructional directions
- **images**: Instructional images

**Direction with Student Questions**:
```json
{
  "sequenceNumber": 1,
  "text": "Display the number 3,456",
  "studentQuestions": [
    {
      "questionText": "What digit is in the thousands place?",
      "sampleAnswers": "3"
    }
  ]
}
```

**Example**:
```json
{
  "id": "segment-uuid-1",
  "studentContentReferenceId": "activity-uuid-1",
  "instructionalSegmentType": "TASK",
  "directions": [
    {
      "sequenceNumber": 1,
      "text": "Have students work in pairs to complete the task",
      "studentQuestions": [
        {
          "questionText": "What strategy did you use?",
          "sampleAnswers": "I counted by hundreds"
        }
      ]
    }
  ]
}
```

---

## Conditional Requirements

Several schemas have conditional requirements:

### image.json
- If `imageType` is `"DECORATIVE"`, then `altText` must be empty string
- If `imageType` is `"TECHNICAL_ART"`, then `technicalArtType` is required

### instructional-segment.json
- If `instructionalSegmentType` is `"TASK"`, `"SETTING_THE_STAGE"`, `"CLOSING"`, or `"DIFFERENTIATION_STRATEGY"`, then `directions` is required
- If `instructionalSegmentType` is `"INTRODUCTION"`, `"ABOUT_THE_MATH"`, or `"LESSON_STRUCTURE_AND_PACING"`, then `contentItems` is required

---

## Sequence Numbers

Many schemas use sequence numbers to maintain order:
- `sequenceNumber` must be `>= 1`
- Should be continuous (1, 2, 3, ...)
- Used in: modules' topics, lessons' activities, activities' tasks, tasks' stems, etc.

---

## Reference Types

The `ReferenceType` enum defines all possible reference types:
```
"LESSON", "ACTIVITY", "TASK", "STANDARDS_BLOCK", "STANDARDS",
"INSTRUCTIONAL_GUIDE_PROMPT", "GOALS", "IMAGE", "STEM",
"SCAFFOLDING", "PAGES", "INSTRUCTIONAL_SEGMENT", "INSTRUCTIONAL_PROMPT"
```

Use appropriate type when creating Reference objects to enable type-safe lookups.
