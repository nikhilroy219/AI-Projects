# AI Lead Qualification

This project started as a manual ChatGPT workflow - a structured prompt with an embedded qualification ruleset that the sales team used to process prospect lists in batches. Once the logic was validated and adopted, I rebuilt it as a fully automated n8n pipeline: the same ruleset, now running on a schedule, processing companies autonomously, and writing results directly to a CRM sheet without any manual intervention.

![Workflow Canvas](workflow_canvas.png)

## What It Does

Sales teams waste hours manually researching and qualifying prospect lists. This workflow automates the entire process - from raw company names to fully populated sales rows with AOS, website, and call-ready news leverage.

Every Friday at 4pm it:

1. Reads the Raw List sheet and filters only unprocessed companies (blank Status)
2. Loops through each company one by one
3. Sends each company to Claude for qualification against the embedded ruleset
4. Routes GREEN companies to Perplexity for live research
5. Formats the research into structured sales intelligence via a second Claude call
6. Appends qualified companies to the Master Sheet with AOS, link, and news leverage
7. Marks every processed company in the Raw List as Checked with GREEN or NOT GREEN

## Workflow Architecture

```
Schedule Trigger (Friday 4pm)
└── Get rows from Raw List (blank status only)
    └── Loop Over Items (one company at a time)
        └── Claude (qualify against ruleset)
            ├── [GREEN]  Perplexity (research company)
            │   └── Claude (format output)
            │       └── Code node (parse JSON)
            │           └── Append to Master Sheet
            │               └── Update Raw List: Checked + GREEN
            └── [NOT GREEN] Update Raw List: Checked + NOT GREEN
```

Key design decisions:

- Batch size of 1 so each company is processed individually and errors are isolated
- Qualification ruleset embedded in Claude system prompt for consistent decisions every run
- Perplexity only called for GREEN companies to avoid wasted API calls
- Code node defensively parses Claude JSON output with fallbacks for inconsistent key names
- On Error set to Continue so one failed company does not kill the full run

## Qualification Ruleset

The ruleset is the core of the workflow. It is embedded directly into the Claude system prompt so every qualification decision is made against the same criteria, every time, with no drift.

Companies qualify as GREEN if they:

- Operate energy assets, industrial facilities, or technology infrastructure in Europe
- Have senior decision-makers in operations, technology, or strategy
- Employ 50+ people with a track record of operational activity

Hard disqualifiers: consultancies, government bodies, universities, pure software vendors with no energy or industrial customer base.

The ruleset is also available as a standalone PDF in this folder (`Lead_Qualification_Ruleset_V1.2.pdf`) for reference and adaptation to other verticals.

## Output

![Master Sheet and Raw List](output_sheets.png)

After each run, the Master Sheet is populated with qualified companies including AOS, website link, and news leverage ready for outreach. The Raw List is updated with a GREEN or NOT GREEN status on every processed company so nothing is processed twice.

## Stack

| Tool | Purpose |
|---|---|
| n8n (self-hosted) | Workflow orchestration |
| Anthropic Claude (claude-sonnet-4-6) | Lead qualification and output formatting |
| Perplexity AI | Real-time company research and news retrieval |
| Google Sheets | Raw company list and master sales sheet |

## Setup

### Prerequisites

- n8n Community Edition (self-hosted)
- Anthropic API key
- Perplexity API key
- Google account with Sheets access

### Installation

1. Download `AI Lead Qualification.json`
2. Import into your n8n instance via Workflows → Import
3. Configure credentials in n8n:
   - Anthropic: HTTP Header Auth (`x-api-key: YOUR_ANTHROPIC_API_KEY`, `anthropic-version: 2023-06-01`)
   - Perplexity: HTTP Header Auth (`Authorization: Bearer YOUR_PERPLEXITY_API_KEY`)
   - Google Sheets: OAuth2
4. Create a Google Sheet with two tabs:
   - Raw List: Company Name, Status, Output
   - Master Sheet: Company Name, AOS, Link, Status, Contact Name, Contact Title, Deal Stage, Notes, News & Leverage, Last Updated
5. Update the Google Sheet ID in the workflow nodes
6. Activate the workflow

## How to Use

1. Paste raw company names into the Raw List tab with blank Status and Output columns
2. The workflow runs automatically every Friday at 4pm
3. Check the Master Sheet for qualified companies with research populated
4. Check the Raw List for GREEN or NOT GREEN results on every processed company

---

Built by [Nikhil Roy](https://nikhilroy.lovable.app), Berlin
