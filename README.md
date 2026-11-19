# Fieldnotes — Personal News Dashboard

Fieldnotes is a personal, mobile-friendly news homepage focused on:
- AI and local computing, cybersecurity, GRC and AI governance
- Kansas City and Missouri news, entrepreneurship, business and policy
- Smart-home technology, repair and consumer electronics
- Laser cutting, vector/CAD design and maker projects
- Practical Missouri homesteading, seasonal gardening, composting and food growing

**Planned live address:** https://tekno2k.github.io/fieldnotes-news/

## One-time GitHub Pages setup

Open **Settings → Pages → Build and deployment → Source** and choose **GitHub Actions**:
https://github.com/Tekno2k/fieldnotes-news/settings/pages

Then open **Actions → Fieldnotes Daily News Refresh → Run workflow** to publish immediately:
https://github.com/Tekno2k/fieldnotes-news/actions/workflows/daily-refresh.yml

The workflow also deploys the site when code changes and at around **8:00 AM America/Chicago** each day, subject to GitHub scheduling delays.

## How it updates

The job runs `python scripts/update_feed.py`, collects public RSS/Atom headlines and descriptions, filters by topic, and redeploys `index.html` and `data/latest.json`. If feeds fail, the last stored edition is used and timestamps make staleness visible. Publisher RSS descriptions are source-provided summaries, not independent fact checking. The "why it matters" notes are relevance explanations based on the reader's stated interests.

The gardening section includes local, season-aware checklists and weekend DIY and homestead projects. Some long-lived extension guides are kept alongside fresh headlines. Search, sorting, and saved stories run locally in the browser; no user accounts or analytics are included.

## Customize later

Edit feed selections and relevance explanations in `scripts/update_feed.py`. Edit seasonal checklists, project ideas and site styling in `index.html`. All article links point to their original publishers.
