# Implementation Examples

## Table of Contents

1. [Complete Lesson Example](#complete-lesson-example)
2. [Student Resource Book Module](#student-resource-book-module)
3. [Teacher Implementation Guide](#teacher-implementation-guide)
4. [Practice Book Section](#practice-book-section)
5. [Standards Integration](#standards-integration)
6. [Multi-Media Content](#multi-media-content)
7. [Response Areas](#response-areas)
8. [Localization Example](#localization-example)

---

## Complete Lesson Example

This example shows a complete Grade 4 math lesson with both hierarchies: physical layout (pages) and logical content (module → lesson).

### Resource (Context Provider & Layout Manager)

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "resourceType": "STUDENT_RESOURCE_BOOK",
  "title": "Grade 4 Mathematics - California Edition",
  "gradeLevel": "4",
  "series": "Math Expressions",
  "edition": "2024",
  "pages": [
    { "id": "page-42-uuid", "type": "PAGES" },
    { "id": "page-43-uuid", "type": "PAGES" }
  ],
  "modules": [
    { "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479", "type": "MODULE", "sequenceNumber": 1 }
  ],
  "metadata": {
    "localizationInfo": {
      "state": "CA",        // State context for modules
      "locale": "en-US"
    }
  }
}
```

### Module Definition (Links to Resource for Context)

```json
{
  "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "resourceId": "550e8400-e29b-41d4-a716-446655440000",  // LINKS TO RESOURCE
  "standardsBody": "CA_CCSS",  // Inherits CA context from resource
  "moduleNumber": 1,
  "title": "Place Value, Addition, and Subtraction to 10,000",
  "moduleSummary": "In this module, students extend their understanding of place value to 10,000, exploring relationships between digits and using place value understanding to add and subtract multi-digit numbers.",
  "gradeLevel": "4",
  "topics": [
    {
      "id": "8e3b5f21-9c7d-4e1a-b234-56789abcdef0",
      "type": "TOPIC",
      "sequenceNumber": 1
    }
  ],
  "images": [
    {
      "id": "cover-module-1-uuid",
      "type": "IMAGE"
    }
  ],
  "metadata": {
    "pacingEstimate": {
      "value": 900,
      "range": {
        "min": 850,
        "max": 950
      }
    }
  }
}
```

### Pages (Physical Layout - References Content)

**Page 42 - Lesson Start**:
```json
{
  "id": "page-42-uuid",
  "resourceId": "550e8400-e29b-41d4-a716-446655440000",
  "pageType": "SRB_LESSON_INTRODUCTION_ACTIVATE",
  "contentBlocks": [
    { "id": "a1b2c3d4-e5f6-4789-0abc-def123456789", "type": "LESSON" },
    { "id": "act-activate-uuid", "type": "ACTIVITY" },
    { "id": "header-image-uuid", "type": "IMAGE" }
  ],
  "metadata": {
    "pageNumberRepresentations": {
      "numeric": 42
    },
    "lessonContext": {
      "moduleNumber": 1,
      "topicNumber": 1,
      "lessonNumber": 1
    }
  }
}
```

**Page 43 - Lesson Continued**:
```json
{
  "id": "page-43-uuid",
  "resourceId": "550e8400-e29b-41d4-a716-446655440000",
  "pageType": "SRB_LESSON_EXPLORE",
  "contentBlocks": [
    { "id": "act-explore-uuid", "type": "ACTIVITY" },
    { "id": "task-explore-1-uuid", "type": "TASK" },
    { "id": "img-place-value-chart-uuid", "type": "IMAGE" }
  ],
  "metadata": {
    "pageNumberRepresentations": {
      "numeric": 43
    }
  }
}
```

### Topic Definition

```json
{
  "id": "8e3b5f21-9c7d-4e1a-b234-56789abcdef0",
  "moduleId": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "topicNumber": 1,
  "title": "Understanding Place Value to 10,000",
  "topicSummary": "Students build on their knowledge of place value to understand the relationships between digits in multi-digit numbers up to 10,000.",
  "lessons": [
    {
      "id": "a1b2c3d4-e5f6-4789-0abc-def123456789",
      "type": "LESSON"
    }
  ],
  "metadata": {
    "pacingEstimate": {
      "value": 300
    }
  }
}
```

### Standards Block

```json
{
  "id": "std-block-4nbt-uuid",
  "body": "CCSS",
  "gradeLevel": "4",
  "title": "Common Core Standards",
  "standardsSubtitle": "This lesson addresses:",
  "standards": [
    {
      "id": "std-ccss-4nbt1-uuid",
      "type": "STANDARDS",
      "sequenceNumber": 1
    },
    {
      "id": "std-ccss-4nbt2-uuid",
      "type": "STANDARDS",
      "sequenceNumber": 2
    }
  ],
  "conceptualOverlaySubtitle": "Big Ideas",
  "conceptualOverlays": [
    {
      "sequenceNumber": 1,
      "text": "Each place in a number represents 10 times the value of the place to its right"
    },
    {
      "sequenceNumber": 2,
      "text": "Understanding place value helps us compare and order numbers"
    }
  ],
  "pageLocationHelpText": "See student book page 42"
}
```

### Standard Definitions

```json
{
  "id": "std-ccss-4nbt1-uuid",
  "body": "CCSS",
  "code": "4.NBT.1",
  "gradeLevel": "4",
  "domain": "Number and Operations in Base Ten",
  "cluster": "Generalize place value understanding for multi-digit whole numbers",
  "description": "Recognize that in a multi-digit whole number, a digit in one place represents ten times what it represents in the place to its right",
  "fullText": "Recognize that in a multi-digit whole number, a digit in one place represents ten times what it represents in the place to its right. For example, recognize that 700 ÷ 70 = 10 by applying concepts of place value and division.",
  "metadata": {
    "publishedDate": "2010-06-02",
    "officialUrl": "http://www.corestandards.org/Math/Content/4/NBT/A/1/"
  }
}
```

```json
{
  "id": "std-ccss-4nbt2-uuid",
  "body": "CCSS",
  "code": "4.NBT.2",
  "gradeLevel": "4",
  "domain": "Number and Operations in Base Ten",
  "cluster": "Generalize place value understanding for multi-digit whole numbers",
  "description": "Read and write multi-digit whole numbers using base-ten numerals, number names, and expanded form",
  "fullText": "Read and write multi-digit whole numbers using base-ten numerals, number names, and expanded form. Compare two multi-digit numbers based on meanings of the digits in each place, using >, =, and < symbols to record the results of comparisons.",
  "metadata": {
    "publishedDate": "2010-06-02",
    "officialUrl": "http://www.corestandards.org/Math/Content/4/NBT/A/2/"
  }
}
```

### Lesson Definition

```json
{
  "id": "a1b2c3d4-e5f6-4789-0abc-def123456789",
  "topicId": "8e3b5f21-9c7d-4e1a-b234-56789abcdef0",
  "lessonNumber": 1,
  "title": "Represent Multi-Digit Numbers to 10,000",
  "lessonSummary": "Students use place value models and charts to represent multi-digit numbers and understand the value of each digit.",
  "learningGoals": [
    "Understand that in a 4-digit number, each digit represents a different place value",
    "Represent numbers using place value models and charts",
    "Read and write numbers in standard, expanded, and word form"
  ],
  "standardsBlock": "std-block-4nbt-uuid",
  "activities": [
    {
      "id": "act-activate-uuid",
      "type": "ACTIVITY",
      "sequenceNumber": 1
    },
    {
      "id": "act-explore-uuid",
      "type": "ACTIVITY",
      "sequenceNumber": 2
    },
    {
      "id": "act-reflect-uuid",
      "type": "ACTIVITY",
      "sequenceNumber": 3
    }
  ],
  "metadata": {
    "pacingEstimate": {
      "value": 45,
      "range": {
        "min": 40,
        "max": 50
      }
    }
  }
}
```

### Activity: Activate

```json
{
  "id": "act-activate-uuid",
  "lessonId": "a1b2c3d4-e5f6-4789-0abc-def123456789",
  "activityType": "ACTIVATE",
  "title": "Review Place Value with Base Ten Blocks",
  "directions": [
    {
      "sequenceNumber": 1,
      "type": "DIRECTION_LINE",
      "text": "Work with a partner to build the number 2,456 using base ten blocks"
    },
    {
      "sequenceNumber": 2,
      "type": "DIRECTION_LINE",
      "text": "Discuss what each type of block represents"
    }
  ],
  "tasks": [
    {
      "id": "task-activate-1-uuid",
      "type": "TASK",
      "sequenceNumber": 1
    }
  ],
  "images": [
    {
      "id": "img-base-ten-blocks-uuid",
      "type": "IMAGE"
    }
  ],
  "goals": [
    {
      "id": "goal-activate-uuid",
      "type": "GOALS"
    }
  ],
  "metadata": {
    "pacingEstimate": {
      "value": 10
    }
  }
}
```

### Activity Goals

```json
{
  "id": "goal-activate-uuid",
  "activityId": "act-activate-uuid",
  "goalType": "HABITS_OF_MIND",
  "goalItems": [
    "Make sense of problems and persevere in solving them",
    "Use appropriate tools strategically"
  ],
  "standards": [
    {
      "id": "std-ccss-4nbt1-uuid",
      "type": "STANDARDS"
    }
  ]
}
```

### Task

```json
{
  "id": "task-activate-1-uuid",
  "activityId": "act-activate-uuid",
  "taskNumber": "1",
  "taskType": "COMPLETION",
  "stems": [
    {
      "id": "stem-1a-uuid",
      "type": "STEM",
      "sequenceNumber": 1
    },
    {
      "id": "stem-1b-uuid",
      "type": "STEM",
      "sequenceNumber": 2
    }
  ],
  "scaffolding": [
    {
      "id": "scaff-hint-uuid",
      "type": "SCAFFOLDING"
    }
  ]
}
```

### Stems

```json
{
  "id": "stem-1a-uuid",
  "taskId": "task-activate-1-uuid",
  "stemType": "TEXT_WITH_RESPONSE_AREA",
  "stemText": "How many thousands blocks did you use?",
  "responseArea": "resp-area-1a-uuid"
}
```

```json
{
  "id": "stem-1b-uuid",
  "taskId": "task-activate-1-uuid",
  "stemType": "TEXT_WITH_RESPONSE_AREA",
  "stemText": "What is the value of the hundreds blocks in your model?",
  "responseArea": "resp-area-1b-uuid"
}
```

### Response Areas

```json
{
  "id": "resp-area-1a-uuid",
  "type": "OPEN_ENDED",
  "description": "Write your answer",
  "specifications": {
    "textAreaLines": 1
  }
}
```

```json
{
  "id": "resp-area-1b-uuid",
  "type": "OPEN_ENDED",
  "description": "Write your answer",
  "specifications": {
    "textAreaLines": 1
  }
}
```

### Scaffolding

```json
{
  "id": "scaff-hint-uuid",
  "scaffoldingType": "CHARACTER_SUPPORT",
  "content": "Remember: The thousands block is the largest. How many did you need for 2,456?",
  "image": "char-support-uuid"
}
```

### Images

```json
{
  "id": "img-base-ten-blocks-uuid",
  "imageType": "INSTRUCTIONAL",
  "filename": "base-ten-blocks-2456.png",
  "filepath": "images/grade-4/module-1/base-ten-blocks-2456.png",
  "altText": "Base ten blocks arranged to show 2 thousands blocks, 4 hundreds blocks, 5 tens rods, and 6 ones cubes",
  "caption": "Figure 1: Base Ten Representation of 2,456",
  "dimensions": {
    "width": 800,
    "height": 600,
    "unit": "PIXELS"
  },
  "format": "PNG",
  "usage": {
    "usedInActivities": [
      {
        "id": "act-activate-uuid",
        "type": "ACTIVITY"
      }
    ],
    "isReusable": true
  },
  "accessibility": {
    "isDecorative": false,
    "longDescription": "The image shows a visual representation using base ten manipulatives. Two large cube blocks represent thousands (1000 each), four flat square blocks represent hundreds (100 each), five long rectangular rods represent tens (10 each), and six small unit cubes represent ones (1 each)."
  },
  "copyright": {
    "holder": "Educational Publisher Inc.",
    "year": 2024,
    "license": "All Rights Reserved"
  },
  "metadata": {
    "createdDate": "2024-01-15",
    "creator": "Design Team",
    "tags": ["place-value", "base-ten-blocks", "manipulatives"]
  }
}
```

### Activity: Explore

```json
{
  "id": "act-explore-uuid",
  "lessonId": "a1b2c3d4-e5f6-4789-0abc-def123456789",
  "activityType": "EXPLORE",
  "title": "Place Value Chart Investigation",
  "directions": [
    {
      "sequenceNumber": 1,
      "type": "DIRECTION_LINE",
      "text": "Complete the place value chart for each number"
    },
    {
      "sequenceNumber": 2,
      "type": "DIRECTION_LINE",
      "text": "Write each number in expanded form"
    }
  ],
  "tasks": [
    {
      "id": "task-explore-1-uuid",
      "type": "TASK",
      "sequenceNumber": 1
    },
    {
      "id": "task-explore-2-uuid",
      "type": "TASK",
      "sequenceNumber": 2
    }
  ],
  "images": [
    {
      "id": "img-place-value-chart-uuid",
      "type": "IMAGE"
    }
  ],
  "metadata": {
    "pacingEstimate": {
      "value": 25
    }
  }
}
```

### Task with Grid Response Area

```json
{
  "id": "task-explore-1-uuid",
  "activityId": "act-explore-uuid",
  "taskNumber": "2",
  "taskType": "COMPLETION",
  "stems": [
    {
      "id": "stem-2-uuid",
      "type": "STEM",
      "sequenceNumber": 1
    }
  ]
}
```

```json
{
  "id": "stem-2-uuid",
  "taskId": "task-explore-1-uuid",
  "stemType": "TEXT_WITH_RESPONSE_AREA",
  "stemText": "Complete the place value chart for 5,432",
  "responseArea": "resp-area-grid-uuid"
}
```

```json
{
  "id": "resp-area-grid-uuid",
  "type": "GRID",
  "description": "Place value chart",
  "specifications": {
    "grid": {
      "gridDimensions": {
        "rows": 2,
        "columns": 4
      },
      "gridStructure": [
        {
          "row": 0,
          "col": 0,
          "editable": false,
          "displayValue": "Thousands",
          "style": "header"
        },
        {
          "row": 0,
          "col": 1,
          "editable": false,
          "displayValue": "Hundreds",
          "style": "header"
        },
        {
          "row": 0,
          "col": 2,
          "editable": false,
          "displayValue": "Tens",
          "style": "header"
        },
        {
          "row": 0,
          "col": 3,
          "editable": false,
          "displayValue": "Ones",
          "style": "header"
        },
        {
          "row": 1,
          "col": 0,
          "editable": true,
          "expectedValue": "5"
        },
        {
          "row": 1,
          "col": 1,
          "editable": true,
          "expectedValue": "4"
        },
        {
          "row": 1,
          "col": 2,
          "editable": true,
          "expectedValue": "3"
        },
        {
          "row": 1,
          "col": 3,
          "editable": true,
          "expectedValue": "2"
        }
      ]
    }
  }
}
```

### Activity: Reflect

```json
{
  "id": "act-reflect-uuid",
  "lessonId": "a1b2c3d4-e5f6-4789-0abc-def123456789",
  "activityType": "REFLECT",
  "title": "Apply Place Value Understanding",
  "directions": [
    {
      "sequenceNumber": 1,
      "type": "DIRECTION_LINE",
      "text": "Answer the following questions about place value"
    }
  ],
  "tasks": [
    {
      "id": "task-reflect-1-uuid",
      "type": "TASK",
      "sequenceNumber": 1
    }
  ],
  "metadata": {
    "pacingEstimate": {
      "value": 10
    }
  }
}
```

```json
{
  "id": "task-reflect-1-uuid",
  "activityId": "act-reflect-uuid",
  "taskNumber": "3",
  "taskType": "OPEN_ENDED",
  "stems": [
    {
      "id": "stem-reflect-uuid",
      "type": "STEM",
      "sequenceNumber": 1
    }
  ]
}
```

```json
{
  "id": "stem-reflect-uuid",
  "taskId": "task-reflect-1-uuid",
  "stemType": "TEXT_WITH_RESPONSE_AREA",
  "stemText": "Explain why the digit 7 in 7,000 represents a greater value than the digit 7 in 700",
  "responseArea": "resp-area-reflect-uuid"
}
```

```json
{
  "id": "resp-area-reflect-uuid",
  "type": "OPEN_ENDED",
  "description": "Write your explanation",
  "specifications": {
    "textAreaLines": 4
  }
}
```

---

## Student Resource Book Module

Complete Module 1 Resource structure:

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
    {
      "id": "page-001-uuid",
      "type": "PAGES"
    },
    {
      "id": "page-042-uuid",
      "type": "PAGES"
    }
  ],
  "modules": [
    {
      "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "type": "MODULE",
      "sequenceNumber": 1
    }
  ],
  "learningGoals": [
    "Develop fluency with multi-digit arithmetic",
    "Understand fraction equivalence and operations",
    "Solve problems involving measurement and data"
  ],
  "standards": [
    {
      "id": "std-ccss-4nbt1-uuid",
      "type": "STANDARDS"
    }
  ],
  "presentation": {
    "pageSize": "LETTER",
    "orientation": "PORTRAIT",
    "binding": "LEFT",
    "coverColor": "#3498db",
    "theme": "STANDARD"
  },
  "metadata": {
    "publishingMetadata": {
      "version": "1.0.0",
      "edition": "2024",
      "publishedDate": "2024-01-15",
      "status": "PUBLISHED"
    },
    "copyrightInfo": {
      "year": 2024,
      "holder": "Educational Publisher Inc.",
      "statement": "© 2024 Educational Publisher Inc. All Rights Reserved",
      "license": "All Rights Reserved",
      "permissions": {
        "canCopy": false,
        "canModify": false,
        "canDistribute": false,
        "commercialUse": false
      }
    },
    "localizationInfo": {
      "language": "en",
      "locale": "en-US"
    },
    "totalPages": 384,
    "subjects": ["Mathematics"],
    "keywords": ["place value", "addition", "subtraction", "multiplication", "division", "fractions"]
  }
}
```

---

## Teacher Implementation Guide

### TIG Resource

```json
{
  "id": "tig-resource-uuid",
  "resourceType": "TEACHER_IMPLEMENTATION_GUIDE",
  "title": "Grade 4 Mathematics",
  "subtitle": "Teacher Implementation Guide",
  "gradeLevel": "4",
  "series": "Math Expressions",
  "edition": "2024",
  "publisher": "Educational Publisher Inc.",
  "teacherGuidance": {
    "linkedStudentResource": {
      "studentPublicationId": "550e8400-e29b-41d4-a716-446655440000",
      "linkType": "MIRRORS"
    },
    "scopeAndSequence": "This curriculum is designed to build mathematical understanding through a three-part lesson structure: Activate prior knowledge, Explore new concepts, and Reflect on learning.",
    "pacing": "Each module is designed for approximately 3-4 weeks of instruction, with flexibility for differentiation and review."
  },
  "modules": [
    {
      "id": "tig-module-1-uuid",
      "type": "MODULE",
      "sequenceNumber": 1
    }
  ]
}
```

### TIG Lesson with Full Guidance

```json
{
  "id": "tig-lesson-uuid",
  "topicId": "tig-topic-uuid",
  "lessonNumber": 1,
  "title": "Lesson Overview: Represent Multi-Digit Numbers",
  "lessonSummary": "This lesson helps students understand place value relationships in 4-digit numbers through hands-on exploration with manipulatives and visual models.",
  "learningGoals": [
    "Students will represent 4-digit numbers using place value models",
    "Students will understand the relationship between adjacent place values"
  ],
  "standardsBlock": "std-block-4nbt-uuid",
  "activities": [
    {
      "id": "tig-act-activate-uuid",
      "type": "ACTIVITY",
      "sequenceNumber": 1
    },
    {
      "id": "tig-act-explore-uuid",
      "type": "ACTIVITY",
      "sequenceNumber": 2
    },
    {
      "id": "tig-act-reflect-uuid",
      "type": "ACTIVITY",
      "sequenceNumber": 3
    }
  ]
}
```

### TIG Activity with Instructional Guidance

```json
{
  "id": "tig-act-activate-uuid",
  "lessonId": "tig-lesson-uuid",
  "activityType": "ACTIVATE",
  "title": "Teaching the Activate Activity",
  "teacherGuidance": {
    "linkedStudentActivity": {
      "studentActivityId": "act-activate-uuid",
      "linkType": "SUPPORTS"
    },
    "instructionType": "WHOLE_CLASS",
    "instructionalText": "Begin by displaying base ten blocks and reviewing what each type represents. Have students work in pairs to build the number 2,456 before proceeding to the task.",
    "teacherPrompts": [
      {
        "id": "prompt-learning-goals-uuid",
        "type": "INSTRUCTIONAL_PROMPT"
      },
      {
        "id": "prompt-materials-uuid",
        "type": "INSTRUCTIONAL_PROMPT"
      }
    ],
    "differentiationStrategies": {
      "advanced": "Challenge advanced students to work with 5-digit numbers or to explain why 10 thousands blocks equal 1 ten-thousands block",
      "ell": "Provide sentence frames: 'I used ___ thousands blocks.' Pair ELL students with native speakers for the partner activity"
    }
  },
  "tasks": [
    {
      "id": "tig-task-uuid",
      "type": "TASK",
      "sequenceNumber": 1
    }
  ]
}
```

### Instructional Prompts

```json
{
  "id": "prompt-learning-goals-uuid",
  "studentContentReferenceId": "tig-lesson-uuid",
  "instructionalPromptType": "LEARNING_GOALS",
  "title": "Learning Goals",
  "contentItems": [
    "Students will represent 4-digit numbers using place value models",
    "Students will identify the value of each digit in a 4-digit number",
    "Students will explain place value relationships"
  ]
}
```

```json
{
  "id": "prompt-materials-uuid",
  "studentContentReferenceId": "tig-act-activate-uuid",
  "instructionalPromptType": "MATERIALS_LIST",
  "title": "Materials Needed",
  "contentItems": [
    "Base ten blocks (1000s, 100s, 10s, 1s) - 1 set per pair",
    "Place value charts - 1 per student",
    "Document camera or overhead projector"
  ]
}
```

```json
{
  "id": "prompt-teacher-story-uuid",
  "studentContentReferenceId": "tig-act-activate-uuid",
  "instructionalPromptType": "TEACHER_STORY",
  "title": "From the Classroom",
  "content": "When I first taught this lesson, I noticed students were confused about why we needed 2 thousands blocks instead of 24 hundreds blocks. I paused the lesson and had a discussion about equivalence. Now I always start with a quick review of how 10 hundreds equal 1 thousand. This prevents the confusion later."
}
```

### Instructional Segments

```json
{
  "id": "seg-setting-stage-uuid",
  "studentContentReferenceId": "act-activate-uuid",
  "instructionalSegmentType": "SETTING_THE_STAGE",
  "directions": [
    {
      "sequenceNumber": 1,
      "text": "Display the number 2,456 prominently on the board",
      "studentQuestions": [
        {
          "questionText": "What do you notice about this number?",
          "sampleAnswers": "It has 4 digits; It's greater than 2,000; The 2 is in the thousands place"
        }
      ]
    },
    {
      "sequenceNumber": 2,
      "text": "Show base ten blocks and review what each type represents",
      "studentQuestions": [
        {
          "questionText": "Which block represents the greatest value?",
          "sampleAnswers": "The thousands block; The big cube"
        },
        {
          "questionText": "How many hundreds blocks equal one thousands block?",
          "sampleAnswers": "10; Ten hundreds equal one thousand"
        }
      ]
    },
    {
      "sequenceNumber": 3,
      "text": "Have students work in pairs to build 2,456 with blocks"
    }
  ]
}
```

```json
{
  "id": "seg-task-guidance-uuid",
  "studentContentReferenceId": "task-activate-1-uuid",
  "instructionalSegmentType": "TASK",
  "directions": [
    {
      "sequenceNumber": 1,
      "text": "Direct students to Task 1 in their books",
      "studentQuestions": [
        {
          "questionText": "How many thousands blocks did you use?",
          "sampleAnswers": "2"
        }
      ]
    },
    {
      "sequenceNumber": 2,
      "text": "Circulate and observe student work. Look for:",
      "studentQuestions": []
    }
  ]
}
```

```json
{
  "id": "prompt-look-fors-uuid",
  "studentContentReferenceId": "task-activate-1-uuid",
  "instructionalPromptType": "STUDENT_LOOK_FORS",
  "title": "What to Look For",
  "contentItems": [
    "Students correctly use 2 thousands, 4 hundreds, 5 tens, and 6 ones",
    "Students can identify the value of each digit",
    "Students recognize that each place is 10 times the value of the place to its right",
    "Common misconception: Using 24 hundreds instead of 2 thousands and 4 hundreds"
  ]
}
```

```json
{
  "id": "seg-closing-uuid",
  "studentContentReferenceId": "act-activate-uuid",
  "instructionalSegmentType": "CLOSING",
  "directions": [
    {
      "sequenceNumber": 1,
      "text": "Bring class back together for discussion",
      "studentQuestions": [
        {
          "questionText": "What was the value of the hundreds blocks in your model?",
          "sampleAnswers": "400; Four hundred because we used 4 hundreds blocks"
        },
        {
          "questionText": "How does understanding place value help us work with large numbers?",
          "sampleAnswers": "It helps us know what each digit means; We can break numbers into parts"
        }
      ]
    }
  ]
}
```

---

## Practice Book Section

### Practice Section with Multiple Activities

```json
{
  "id": "practice-lesson-1-uuid",
  "parentId": "a1b2c3d4-e5f6-4789-0abc-def123456789",
  "practiceSectionType": "LESSON_PRACTICE",
  "title": "Practice: Representing Multi-Digit Numbers",
  "activities": [
    {
      "id": "practice-act-1-uuid",
      "type": "ACTIVITY",
      "sequenceNumber": 1
    },
    {
      "id": "practice-act-2-uuid",
      "type": "ACTIVITY",
      "sequenceNumber": 2
    }
  ]
}
```

### Practice Activity

```json
{
  "id": "practice-act-1-uuid",
  "lessonId": "a1b2c3d4-e5f6-4789-0abc-def123456789",
  "activityType": "PRACTICE_QUESTIONS",
  "title": "Practice Problems",
  "directions": [
    {
      "sequenceNumber": 1,
      "type": "DIRECTION_LINE",
      "text": "Complete each problem. Show your work."
    }
  ],
  "tasks": [
    {
      "id": "practice-task-1-uuid",
      "type": "TASK",
      "sequenceNumber": 1
    },
    {
      "id": "practice-task-2-uuid",
      "type": "TASK",
      "sequenceNumber": 2
    },
    {
      "id": "practice-task-3-uuid",
      "type": "TASK",
      "sequenceNumber": 3
    }
  ]
}
```

### Family Guide Activity

```json
{
  "id": "family-guide-uuid",
  "lessonId": "a1b2c3d4-e5f6-4789-0abc-def123456789",
  "activityType": "PRACTICE_CONVERSATION_STARTERS",
  "title": "Family Conversation Starters",
  "directions": [
    {
      "sequenceNumber": 1,
      "type": "STORY",
      "text": "Dear Family, This week your child learned about place value in multi-digit numbers. Here are some activities you can do together to reinforce these concepts:"
    }
  ],
  "tasks": [
    {
      "id": "family-task-1-uuid",
      "type": "TASK",
      "sequenceNumber": 1
    }
  ]
}
```

---

## Standards Integration

### Cross-Grade Standards Progression

```json
{
  "id": "std-ccss-3nbt1-uuid",
  "body": "CCSS",
  "code": "3.NBT.1",
  "gradeLevel": "3",
  "domain": "Number and Operations in Base Ten",
  "cluster": "Use place value understanding and properties of operations to perform multi-digit arithmetic",
  "fullText": "Use place value understanding to round whole numbers to the nearest 10 or 100."
}
```

```json
{
  "id": "std-ccss-4nbt1-uuid",
  "body": "CCSS",
  "code": "4.NBT.1",
  "gradeLevel": "4",
  "domain": "Number and Operations in Base Ten",
  "cluster": "Generalize place value understanding for multi-digit whole numbers",
  "fullText": "Recognize that in a multi-digit whole number, a digit in one place represents ten times what it represents in the place to its right."
}
```

```json
{
  "id": "std-ccss-5nbt1-uuid",
  "body": "CCSS",
  "code": "5.NBT.1",
  "gradeLevel": "5",
  "domain": "Number and Operations in Base Ten",
  "cluster": "Understand the place value system",
  "fullText": "Recognize that in a multi-digit number, a digit in one place represents 10 times as much as it represents in the place to its right and 1/10 of what it represents in the place to its left."
}
```

---

## Multi-Media Content

### Task with Image and Technical Art

```json
{
  "id": "task-with-diagram-uuid",
  "activityId": "act-explore-uuid",
  "taskNumber": "4",
  "taskType": "STRATEGY_ANALYSIS",
  "stems": [
    {
      "id": "stem-diagram-uuid",
      "type": "STEM",
      "sequenceNumber": 1
    }
  ]
}
```

```json
{
  "id": "stem-diagram-uuid",
  "taskId": "task-with-diagram-uuid",
  "stemType": "TEXT_WITH_IMAGE",
  "ancillaryText": "Maria and Juan",
  "stemText": "Maria and Juan each represented 3,247 differently. Whose representation shows the correct place values? Explain your reasoning.",
  "image": "img-student-work-uuid",
  "responseArea": "resp-area-explanation-uuid"
}
```

```json
{
  "id": "img-student-work-uuid",
  "imageType": "TECHNICAL_ART",
  "technicalArtType": "PLACE_VALUE",
  "filename": "student-work-comparison.png",
  "filepath": "images/grade-4/module-1/student-work-comparison.png",
  "altText": "Two student work samples side by side. Maria's work shows a place value chart with 3 in thousands, 2 in hundreds, 4 in tens, 7 in ones. Juan's work shows 32 hundreds, 4 tens, 7 ones.",
  "dimensions": {
    "width": 1000,
    "height": 400,
    "unit": "PIXELS"
  },
  "format": "PNG",
  "accessibility": {
    "isDecorative": false,
    "longDescription": "The image compares two methods of representing 3,247. Maria's method uses a standard place value chart with one digit in each column. Juan's method groups the thousands and hundreds together, showing 32 in the hundreds column instead of separating them into 3 thousands and 2 hundreds."
  }
}
```

---

## Response Areas

### Algorithm Workspace

```json
{
  "id": "resp-area-algorithm-uuid",
  "type": "ALGORITHM_WORKSPACE",
  "description": "Show your work for long division",
  "specifications": {
    "algorithmType": "LONG_DIVISION",
    "allowedTools": []
  }
}
```

### Number Line

```json
{
  "id": "resp-area-number-line-uuid",
  "type": "NUMBER_LINE",
  "description": "Place the numbers on the number line",
  "specifications": {
    "numberLineRange": {
      "min": 0,
      "max": 10000,
      "increment": 1000
    }
  }
}
```

### Cross Number Puzzle

```json
{
  "id": "resp-area-puzzle-uuid",
  "type": "CROSS_NUMBER_PUZZLE",
  "description": "Complete the cross number puzzle",
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
          "displayValue": "",
          "style": "blocked"
        },
        {
          "row": 0,
          "col": 1,
          "editable": true,
          "expectedValue": "3"
        },
        {
          "row": 0,
          "col": 2,
          "editable": true,
          "expectedValue": "2"
        }
      ]
    }
  }
}
```

---

## Localization Example

### Spanish (US) Localized Content

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000-es",
  "resourceType": "STUDENT_RESOURCE_BOOK",
  "title": "Matemáticas de 4º Grado",
  "subtitle": "Libro de Recursos del Estudiante",
  "gradeLevel": "4",
  "series": "Math Expressions",
  "edition": "2024",
  "publisher": "Educational Publisher Inc.",
  "metadata": {
    "localizationInfo": {
      "language": "es",
      "locale": "es-US",
      "translationStatus": "REVIEWED",
      "translatedBy": "Professional Translation Services",
      "translatedDate": "2024-03-15",
      "reviewedBy": "Dr. Carmen Rodriguez",
      "reviewedDate": "2024-04-01",
      "culturalAdaptations": [
        "Updated examples to include Hispanic cultural references",
        "Modified currency examples to include pesos where appropriate",
        "Adjusted measurement units to include metric system"
      ]
    }
  }
}
```

### Localized Lesson

```json
{
  "id": "a1b2c3d4-e5f6-4789-0abc-def123456789-es",
  "topicId": "8e3b5f21-9c7d-4e1a-b234-56789abcdef0-es",
  "lessonNumber": 1,
  "title": "Representar Números de Múltiples Dígitos hasta 10,000",
  "lessonSummary": "Los estudiantes usan modelos de valor posicional y tablas para representar números de múltiples dígitos y comprender el valor de cada dígito.",
  "learningGoals": [
    "Comprender que en un número de 4 dígitos, cada dígito representa un valor posicional diferente",
    "Representar números usando modelos y tablas de valor posicional",
    "Leer y escribir números en forma estándar, expandida y verbal"
  ],
  "standardsBlock": "std-block-4nbt-uuid-es",
  "metadata": {
    "localizationInfo": {
      "language": "es",
      "locale": "es-US"
    }
  }
}
```

This completes the comprehensive implementation examples showing real-world usage of the schema system.
