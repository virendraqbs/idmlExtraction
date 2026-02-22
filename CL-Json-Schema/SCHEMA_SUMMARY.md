# Schema Summary

## Quick Reference Guide

This document provides a concise overview of all schemas in the Educational Content Schema System.

---

## Core Content Schemas

### 📘 Resource
**File**: `resource.json`  
**Purpose**: Represents a physical or digital book (Student Resource Book, Practice Book, or Teacher Guide)

**Key Properties**:
- `resourceType`: STUDENT_RESOURCE_BOOK | STUDENT_PRACTICE_BOOK | TEACHER_IMPLEMENTATION_GUIDE
- `title`, `subtitle`, `gradeLevel`, `series`, `edition`
- `pages[]`: References to all pages in the resource
- `modules[]`: References to content modules
- `teacherGuidance`: Links to student resources (teacher guides only)
- `presentation`: Physical/visual properties (pageSize, orientation, binding)

**Required**: id, resourceType, title, gradeLevel

---

### 📦 Module
**File**: `module.json`  
**Purpose**: Large organizational unit containing multiple topics

**Key Properties**:
- `moduleNumber`: Sequential number (1, 2, 3...)
- `title`, `moduleSummary`
- `standardsBody`: CCSS | CA_CCSS | TEKS | BEST
- `topics[]`: Ordered references to topics
- `gradeLevel`

**Required**: id, moduleNumber, title, gradeLevel

**Hierarchy**: Resource → **Module** → Topic → Lesson

---

### 📑 Topic
**File**: `topic.json`  
**Purpose**: Thematic grouping of lessons within a module

**Key Properties**:
- `topicNumber`: Sequential within module
- `title`, `topicSummary`
- `lessons[]`: References to lessons
- `images[]`: Topic-level images

**Required**: id, topicNumber, title, moduleId

**Hierarchy**: Resource → Module → **Topic** → Lesson

---

### 📖 Lesson
**File**: `lesson.json`  
**Purpose**: Individual instructional unit (typically 1-2 class periods)

**Key Properties**:
- `lessonNumber`: Sequential within topic
- `title`, `lessonSummary`
- `learningGoals[]`: Lesson objectives
- `standardsBlock`: Reference to standards coverage
- `activities[]`: Ordered activities (Activate, Explore, Reflect)
- `pacingEstimate`: Time in minutes

**Required**: id, lessonNumber, title, topicId

**Hierarchy**: Resource → Module → Topic → **Lesson** → Activity

**Structure**: Typically contains:
1. Activate activity (introduction/warmup)
2. Explore activity (main instruction)
3. Reflect activity (closure/assessment)

---

### 🎯 Activity
**File**: `activity.json`  
**Purpose**: Discrete instructional segment within a lesson

**Key Properties**:
- `activityType`: ACTIVATE | EXPLORE | REFLECT | PRACTICE | KEY_TERMS | KEY_IDEAS
- `title`, `directions[]`
- `goals[]`: References to activity-level goals
- `tasks[]`: Ordered tasks
- `scaffolding[]`: Learning supports
- `teacherGuidance`: Teacher instructions (teacher guides only)

**Required**: id, activityType, lessonId

**Hierarchy**: Lesson → **Activity** → Task

**Activity Types**:
- **ACTIVATE**: Introduction, prior knowledge activation
- **EXPLORE**: Main instructional content
- **REFLECT**: Closure, assessment, reflection
- **PRACTICE**: Additional practice exercises
- **KEY_TERMS**: Vocabulary focus
- **KEY_IDEAS**: Concept summary

---

### ✓ Task
**File**: `task.json`  
**Purpose**: Individual problem, question, or exercise

**Key Properties**:
- `taskNumber`: Identifier (e.g., "1", "2a", "3b")
- `taskType`: COMPLETION | CALCULATION | STRATEGY_ANALYSIS | MULTIPLE_CHOICE | SHORT_ANSWER | WORD_PROBLEM | OPEN_ENDED
- `stems[]`: Ordered question stems
- `scaffolding[]`: Task-level supports
- `teacherGuidance`: Links to student task (teacher guides)

**Required**: id, taskNumber, taskType, activityId, stem

**Hierarchy**: Activity → **Task** → Stem

---

### 🌱 Stem
**File**: `stem.json`  
**Purpose**: Individual question prompt or problem stem

**Key Properties**:
- `stemType`: TEXT_ONLY | TEXT_WITH_IMAGE | TEXT_WITH_RESPONSE_AREA
- `stemText`: Question or prompt text
- `ancillaryText`: Supporting text (names, context)
- `image`: Reference to associated image
- `responseArea`: Where students answer

**Required**: id, stemType, taskId

**Hierarchy**: Task → **Stem**

---

## Supporting Content Schemas

### 📄 Page
**File**: `page.json`  
**Purpose**: Physical or digital page in a resource

**Key Properties**:
- `pageType`: SRB_LESSON_INTRODUCTION_ACTIVATE | TIG_LESSON_OVERVIEW | SPB_LESSON_PRACTICE | etc.
- `contentBlocks[]`: Content elements on the page
- `pageNumberRepresentations`: Numeric, roman numeral, word form, prime factorization
- `lessonContext`: Module, topic, lesson information

**Required**: id, pageNumber, pageType, resourceId

**Page Type Prefixes**:
- **SRB_**: Student Resource Book pages
- **SPB_**: Student Practice Book pages
- **TIG_**: Teacher Implementation Guide pages

---

### 📝 Practice Section
**File**: `practice-section.json`  
**Purpose**: Collection of practice activities

**Key Properties**:
- `practiceSectionType`: LESSON_PRACTICE | FAMILY_GUIDE
- `title`
- `activities[]`: Ordered practice activities

**Required**: id, parentId, practiceSectionType

**Use Cases**:
- Lesson practice pages in Practice Book
- Family review guides
- Additional exercises

---

### 🎯 Activity Goals
**File**: `activity-goals.json`  
**Purpose**: Learning goals specific to standards frameworks

**Key Properties**:
- `goalType`: HABITS_OF_MIND | COMMON_CORE_LEARNING_GOAL | NGSS_PERFORMANCE_EXPECTATION
- `goalItems[]`: Individual goal statements
- `standards[]`: Associated standards

**Required**: id, goalType, activityId

**Common Goal Types**:
- **HABITS_OF_MIND**: Mathematical or scientific practices
- **COMMON_CORE_LEARNING_GOAL**: CCSS-aligned objectives
- **NGSS_PERFORMANCE_EXPECTATION**: Science standards

---

### 🪜 Scaffolding
**File**: `scaffolding.json`  
**Purpose**: Learning support for tasks or activities

**Key Properties**:
- `scaffoldingType`: CHARACTER_SUPPORT (additional types may be added)
- `content`: Scaffolding text
- `image`: Optional supporting image

**Required**: id, scaffoldingType, content

**Purpose**: Provides hints, prompts, or character-based support for struggling learners

---

### ✏️ Response Area
**File**: `response-area.json`  
**Purpose**: Defines where and how students provide answers

**Key Properties**:
- `type`: OPEN_ENDED | CROSS_NUMBER_PUZZLE | NUMBER_LINE | GRID | ALGORITHM_WORKSPACE | STEM
- `specifications`: Type-specific details
  - Grid dimensions and structure
  - Number line range
  - Algorithm type
  - Allowed tools

**Required**: id, type

**Response Types**:
- **OPEN_ENDED**: Free text response
- **CROSS_NUMBER_PUZZLE**: Numeric crossword-style
- **NUMBER_LINE**: Visual number line interaction
- **GRID**: Structured grid entry
- **ALGORITHM_WORKSPACE**: Space for showing work
- **STEM**: Response embedded in stem

---

## Media & Assets

### 🖼️ Image
**File**: `image.json`  
**Purpose**: Image assets used throughout content

**Key Properties**:
- `imageType`: MODULE_COVER | TOPIC_COVER | LESSON_COVER | INSTRUCTIONAL | DECORATIVE | TECHNICAL_ART | CHARACTER_SUPPORT | MANIPULATIVE | ICON
- `technicalArtType`: NUMBER_LINES | BAR_GRAPHS | SHAPES_OUTLINED | etc. (if imageType is TECHNICAL_ART)
- `filename`, `filepath`, `url`
- `altText`: Required for non-decorative images
- `caption`, `title`
- `dimensions`, `format`, `fileSize`
- `usage`: Where the image is used
- `accessibility`: Extended descriptions
- `copyright`: Licensing information

**Required**: id, imageType, filename
**Conditionally Required**: 
- altText (unless imageType is DECORATIVE)
- technicalArtType (if imageType is TECHNICAL_ART)

**Image Types**:
- **INSTRUCTIONAL**: Teaching-focused images
- **TECHNICAL_ART**: Diagrams, graphs, mathematical representations
- **CHARACTER_SUPPORT**: Character mascots providing hints
- **DECORATIVE**: Visual interest only (no alt text needed)

---

## Standards & Alignment

### 📏 Standard
**File**: `standard.json`  
**Purpose**: Individual educational standard

**Key Properties**:
- `body`: CCSS | CA_CCSS | TEKS | BEST
- `code`: Standard code (e.g., "4.NBT.4")
- `gradeLevel`: "K", "1", "2", etc.
- `domain`: Content domain (e.g., "Number and Operations in Base Ten")
- `cluster`: Subcategory within domain
- `description`: Short description
- `fullText`: Complete standard text
- `metadata`: Publishing date, official URL

**Required**: id, body, code, gradeLevel, fullText

**Standard Bodies**:
- **CCSS**: Common Core State Standards
- **CA_CCSS**: California Common Core
- **TEKS**: Texas Essential Knowledge and Skills
- **BEST**: Florida's B.E.S.T. Standards

---

### 📋 Standards Block
**File**: `standards-block.json`  
**Purpose**: Collection of standards with contextual information

**Key Properties**:
- `body`: Standards body
- `gradeLevel`
- `title`: Block title (e.g., "California Standards")
- `conceptualOverlaySubtitle`, `conceptualOverlays[]`: Conceptual context
- `standardsSubtitle`, `standards[]`: Ordered standard references
- `pageLocationHelpText`: Guide for finding standards in resources

**Required**: id, gradeLevel

**Use Case**: Groups related standards together with explanatory overlays for lesson or topic coverage

---

## Teacher Content

### 💬 Instructional Prompt
**File**: `instructional-prompt.json`  
**Purpose**: Teacher support elements and prompts

**Key Properties**:
- `instructionalPromptType`: LEARNING_GOALS | LANGUAGE_GOALS | DAILY_MATH_ROUTINES | MULTILINGUAL_LEARNER_SUPPORT | TEACHER_STORY | HABITS_OF_MIND | STUDENT_LOOK_FORS | CULTIVATE_CONNECTIONS | STUDENT_EDITION_PAGE_IMAGE | MATERIALS_LIST
- `studentContentReferenceId`: Links to student content
- `title`, `content`, `contentItems[]`
- `images[]`: Supporting images
- `displayStyle`: BOX | SIDEBAR | INLINE | CALLOUT

**Required**: id, instructionalPromptType

**Prompt Types**:
- **LEARNING_GOALS**: Lesson objectives
- **LANGUAGE_GOALS**: Language development targets
- **TEACHER_STORY**: Narrative guidance
- **HABITS_OF_MIND**: Mathematical/scientific practices
- **STUDENT_LOOK_FORS**: What to observe
- **MATERIALS_LIST**: Required materials

---

### 📚 Instructional Segment
**File**: `instructional-segment.json`  
**Purpose**: Teacher instruction segments for lessons/topics

**Key Properties**:
- `instructionalSegmentType`: INTRODUCTION | ABOUT_THE_MATH | LESSON_STRUCTURE_AND_PACING | SETTING_THE_STAGE | TASK | CLOSING | DIFFERENTIATION_STRATEGY | ONGOING_ASSESSMENT | LANGUAGE_LINK
- `studentContentReferenceId`: Links to student content
- `directions[]`: Ordered instructional steps
  - Each direction can include `studentQuestions[]` with sample answers
- `images[]`: Instructional images

**Required**: id, instructionalSegmentType
**Conditionally Required**:
- `directions[]` for TASK, SETTING_THE_STAGE, CLOSING, DIFFERENTIATION_STRATEGY
- `contentItems[]` for INTRODUCTION, ABOUT_THE_MATH, LESSON_STRUCTURE_AND_PACING

**Segment Types**:
- **INTRODUCTION**: Overview of content
- **ABOUT_THE_MATH**: Mathematical/content background
- **TASK**: Step-by-step task guidance
- **SETTING_THE_STAGE**: Pre-lesson setup
- **CLOSING**: Lesson wrap-up
- **DIFFERENTIATION_STRATEGY**: Support for diverse learners

---

## Foundation Schemas

### 🔧 Primitives
**File**: `primitives.json`  
**Purpose**: Base types used across all schemas

**Definitions**:
- **UUID**: String pattern for unique identifiers
- **Reference**: Object with id and type (used for linking)
- **Image**: Basic image object structure

---

### 📊 Enums
**File**: `enums.json`  
**Purpose**: Enumerated values for consistent categorization

**Key Enumerations**:
- Language: en, es, fr, de, zh, it
- Locale: en-US, es-US
- State: All 50 US states
- StandardsBody: CCSS, CA_CCSS, TEKS, BEST
- ResourceType: STUDENT_RESOURCE_BOOK, STUDENT_PRACTICE_BOOK, TEACHER_IMPLEMENTATION_GUIDE
- PageType: 40+ specific page types
- ActivityType: ACTIVATE, EXPLORE, REFLECT, PRACTICE, KEY_TERMS, KEY_IDEAS, etc.
- TaskType: COMPLETION, CALCULATION, STRATEGY_ANALYSIS, MULTIPLE_CHOICE, etc.
- ImageType: MODULE_COVER, INSTRUCTIONAL, TECHNICAL_ART, DECORATIVE, etc.
- Status: NOT_STARTED, IN_PROGRESS, COMPLETE, REVIEWED, PUBLISHED

---

### 📋 Metadata
**File**: `metadata.json`  
**Purpose**: Reusable metadata structures

**Definitions**:
- **PageNumberRepresentations**: numeric, romanNumeral, wordForm, primeFactorization
- **LessonContext**: Module, topic, lesson placement
- **PacingEstimate**: Time estimates (value or range)
- **ISBN**: ISBN-13 and ISBN-10
- **CopyrightInfo**: Copyright holder, year, license, permissions
- **TeacherStudentLink**: Links teacher content to student content
- **AccessibilityInfo**: Accessibility features and compliance
- **LocalizationInfo**: Language, locale, translation status
- **DifferentiationStrategies**: Support for different learner levels
- **MaterialsList**: Required, optional, and digital materials
- **PublishingMetadata**: Version, edition, publication dates, status

---

## Schema Relationships

### Parent-Child Relationships
```
Resource
  └─ Module
      └─ Topic
          └─ Lesson
              └─ Activity
                  └─ Task
                      └─ Stem
```

### Cross-References
- **Pages** → Content Blocks (activities, tasks)
- **Standards Blocks** → Standards
- **Activities/Tasks** → Images, Scaffolding, Goals
- **Teacher Content** → Student Content (via TeacherStudentLink)
- **Practice Sections** → Activities → Tasks

### Linking Patterns
1. **Direct References**: UUID stored in property
2. **Reference Objects**: `{ id: UUID, type: ReferenceType, sequenceNumber?: number }`
3. **Teacher-Student Links**: `TeacherStudentLink` metadata object

---

## Common Patterns

### Sequence Ordering
Most array references include `sequenceNumber` for explicit ordering:
```json
{
  "activities": [
    { "id": "uuid-1", "type": "ACTIVITY", "sequenceNumber": 1 },
    { "id": "uuid-2", "type": "ACTIVITY", "sequenceNumber": 2 }
  ]
}
```

### Teacher Guidance
Teacher-specific properties are nested under `teacherGuidance`:
```json
{
  "teacherGuidance": {
    "linkedStudentActivity": { "studentActivityId": "uuid", "linkType": "MIRRORS" },
    "instructionType": "DIRECT_INSTRUCTION",
    "teacherPrompts": [...]
  }
}
```

### Metadata
Complex metadata is nested under `metadata` property:
```json
{
  "metadata": {
    "pacingEstimate": { "value": 45 },
    "localizationInfo": { "language": "en", "locale": "en-US" }
  }
}
```

---

## Required vs. Optional Fields

### Always Required
- `id` (UUID) - Every entity
- Type identifiers (resourceType, activityType, taskType, etc.)
- Key identifiers (moduleNumber, lessonNumber, taskNumber)
- Parent references (resourceId, moduleId, topicId, etc.)

### Commonly Optional
- `title`, `description` - Descriptive text
- `images[]` - Visual assets
- `metadata` - Extended metadata
- `teacherGuidance` - Teacher-specific content

### Conditionally Required
- `altText` - Required for all non-decorative images
- `technicalArtType` - Required when imageType is TECHNICAL_ART
- `directions[]` - Required for specific instructional segment types

---

## Version & Standards

- **JSON Schema Version**: Draft 07
- **Schema Version**: 1.0.0
- **UUID Format**: RFC 4122 compliant
- **Date Format**: ISO 8601 (YYYY-MM-DD)
- **DateTime Format**: ISO 8601 with timezone

---

## Quick Schema Lookup

| Need to model... | Use schema... |
|-----------------|---------------|
| A book | `resource.json` |
| Major content unit | `module.json` |
| Topic grouping | `topic.json` |
| Single lesson | `lesson.json` |
| Lesson segment | `activity.json` |
| Individual problem | `task.json` |
| Question prompt | `stem.json` |
| Physical page | `page.json` |
| Practice grouping | `practice-section.json` |
| Learning objective | `activity-goals.json` |
| Student support | `scaffolding.json` |
| Answer space | `response-area.json` |
| Picture/diagram | `image.json` |
| Educational standard | `standard.json` |
| Standard grouping | `standards-block.json` |
| Teacher prompt | `instructional-prompt.json` |
| Teacher instruction | `instructional-segment.json` |

---

For detailed implementation guidance, see the [Implementation Guide](../guides/IMPLEMENTATION_GUIDE.md).
