# Plans folder

Upload plan files (`something.json`) written in the Claude chat here. Each upload starts the
**Render videos from plans** workflow, which makes one video per plan at the same time (up to 5),
then moves finished plans into `plans/done/`. A plan that fails stays here so you can retry it
(Actions → Render videos from plans → Run workflow).

## Plan format

```json
{
  "title": "The Day Constantinople Fell",
  "alt_titles": ["...", "..."],
  "thumbnail_text": "THE LAST DAY",
  "description_summary": "Two or three sentences for the top of the description.",
  "tags": ["fall of constantinople", "byzantine empire"],
  "lane": "Big events & empires",
  "publish_at": "2026-10-01T16:00:00+01:00",
  "sources": [{"title": "Britannica: Fall of Constantinople", "url": "https://..."}],
  "unverified": [{"claim": "...", "reason": "only one source"}],
  "scenes": [
    {
      "chapter": "Introduction",
      "narration": "On the night of 28 May 1453, ...",
      "shots": [
        {"file": "File:Le siège de Constantinople (1453) by Jean Le Tavernier after 1455.jpg",
         "caption": "The siege, illuminated manuscript, c. 1455"},
        {"query": "Theodosian Walls Istanbul", "caption": "The Theodosian Walls today"}
      ]
    },
    {"chapter": null, "narration": "...", "shots": [ ... ]}
  ]
}
```

- `chapter`: a short title on the first scene of each chapter, `null` on the rest.
- Each shot uses `file` (an exact Wikimedia Commons file name) or `query` (a specific Commons
  search), or both (`query` is the fallback if the file can't be used).
- Only public domain, CC0 and CC BY images are used; the rest are skipped automatically.
- `publish_at` is optional (UK time with offset).
