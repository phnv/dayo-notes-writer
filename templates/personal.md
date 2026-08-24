# Personal Note Template

```yaml
---
type: personal-note
date: YYYY-MM-DD
tags: []
important: false
options: []
---
```

## Allowed tags

Use only tags from this list:

* `idea`
* `decision`
* `task`
* `question`
* `reflection`
* `reference`
* `project`
* `personal`

Add a tag only when clearly supported by the content.

## Body

```markdown
# [Main subject]

## [Topic / date]

- Main point
  - Supporting point
  - Supporting point
    - Detail

> Related response, clarification or complementary thought.

**Important:** important content

***Very important:*** very important content

- [ ] Pending item
- [x] Completed item
- [ ] Failed / could not be completed: ...
- [ ] For later: ...
```

## Transformation example

Input:

```text
[18/08] 
=> chatbot project
- finish storage
+ database is working
+ still need to test reload
* important: don't change schema yet

=> job search
- applied to 3 jobs
> still unsure if CV is the problem
** review competitors later
```

Output:

```markdown
---
type: personal-note
date: 2026-08-18
tags:
  - project
  - task
  - reflection
important: true
options: []
---

# Personal Notes

## Chatbot project

- Finish storage
  - Database is working.
  - Still need to test reload.
- **Important:** Do not change the schema yet.

## Job search

- Applied to 3 jobs.
> Still unsure if the CV is the problem.
- **For later:** Review competitors.
```
