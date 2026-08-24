# Personal Note — Template Instructions

Transform the input into a concise, readable Markdown note while preserving its complete meaning and information.

Prioritize **hierarchy, grouping and readability** over rewriting prose. Do not summarize away information. Keep the author's original distinctions, status markers, dates and emphasis.

## Marker grammar

Interpret markers as structural metadata:

| Marker       | Meaning                                                            |
| ------------ | ------------------------------------------------------------------ |
| `[dd/mm/yy]` | Everything below belongs to this date. Year may be omitted.        |
| `=>`         | Main heading or top-level list item                                |
| `+>`         | Subheading / sublist under `=>`                                    |
| `-`          | List item                                                          |
| `+`          | Subitem                                                            |
| `++`         | Sub-subitem                                                        |
| `>`          | Block/quote responding to or complementing the preceding statement |
| `>>...`      | In-progress item; any sequence of `>` indicates progress           |
| `*`          | Important                                                          |
| `**`         | For later consideration/action                                     |
| `***`        | Very important                                                     |
| `***text***` | Very important reminder; highlight it                              |
| `ok`         | Done                                                               |
| `X`          | Could not be done                                                  |
| `fail`       | Attempted but unsuccessful                                         |

Hierarchy:

`=>` > `+>` and `=>` > `-` > `+` > `++`

Preserve marker meaning even when converting it into Markdown structure.

## Transformation rules

* Convert markers into clear Markdown structure rather than reproducing the markers literally.
* Preserve dates and their scope.
* Preserve status and priority information.
* Preserve quotes/responses as subordinate context.
* Group related material only when the relationship is explicit.
* Do not infer relationships that are not present.
* Keep unclear or incomplete statements rather than "fixing" their meaning.
* Use the template's frontmatter fields only for information supported by the input.
