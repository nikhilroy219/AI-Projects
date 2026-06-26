# AI Lead Qualification

An automated B2B lead qualification workflow built with n8n. Takes a raw list of target companies, qualifies each one against a custom ruleset using Claude (Anthropic), researches qualified companies via Perplexity AI, and writes results directly into a master sales sheet — all on a weekly schedule with no manual input required.

![Workflow Canvas](workflow_canvas.png)

## What It Does

Sales teams waste hours manually researching and qualifying prospect lists. This workflow automates the entire process — from raw company name to a fully populated sales row with AOS, website, and call-ready news leverage.

Every Friday at 4pm it:

1. Reads the Raw List sheet and filters only unprocessed companies (blank Status)
2. Loops through each company one by one
3. Sends each company to Claude for qualification against a defined ruleset
4. Routes GREEN companies to Perplexity for live research
5. Formats the research into structured sales intelligence via a second Claude call
6. Appends qualified companies to the Master Sheet with AOS, link, and news leverage
7. Marks every processed company in the Raw List as Checked with GREEN or NOT GREEN

## Workflow Architecture

Schedule Trigger (Friday 4pm)
    └── Get rows from Raw List (blank status only)
            └── Loop Over Items (one company at a time)
                    └── HTTP Request → Claude (qualify against ruleset)
                            └── If (GREEN or NOT GREEN?)
                                    ├── [GREEN]  HTTP Request → Perplexity (research)
                                    │               └── HTTP Request → Claude (format output)
                                    │                       └── Code node (parse JSON)
                                    │                               └── Append row to Master Sheet
                                    │                                       └── Update Raw List: Checked + GREEN
                                    └── [NOT GREEN] Update Raw List: Checked + NOT GREEN

Key design decisions:

- Batch size of 1 so each company is processed individually and errors are isolated
- Qualification ruleset embedded in Claude system prompt for consistent decisions
- Perplexity only called for GREEN companies to avoid wasted API calls
- Code node defensively parses Claude JSON output with fallbacks for inconsistent key names
- On Error set to Continue so one failed company does not kill the full run

## Stack

| Tool | Purpose |
|---|---|
| n8n (self-hosted) | Workflow orchestration |
| Anthropic Claude (claude-sonnet-4-6) | Lead qualification and output formatting |
| Perplexity AI | Real-time company research and news retrieval |
| Google Sheets | Raw company list and master sales sheet |

## Qualification Ruleset

Companies qualify as GREEN if they:

- Operate energy assets, industrial facilities, or technology infrastructure in Europe
- Have senior decision-makers in operations, technology, or strategy
- Employ 50+ people with a track record of operational activity

Hard disqualifiers: consultancies, government bodies, universities, pure software vendors with no energy customer base.

## Setup

### Prerequisites

- n8n Community Edition (self-hosted)
- Anthropic API key
- Perplexity API key
- Google account with Sheets access

### Installation

1. Clone this repo
2. Import AI Lead Qualification.json into your n8n instance via Workflows → Import
3. Configure credentials in n8n:
   - Anthropic: HTTP Header Auth (x-api-key: YOUR_ANTHROPIC_API_KEY, anthropic-version: 2023-06-01)
   - Perplexity: HTTP Header Auth (Authorization: Bearer YOUR_PERPLEXITY_API_KEY)
   - Google Sheets: OAuth2
4. Create a Google Sheet with two tabs:
   - Raw List: Company Name, Status, Output
   - Master Sheet: Company Name, AOS, Link, Status, Contact Name, Contact Title, Deal Stage, Notes, News & Leverage, Last Updated
5. Update the Google Sheet ID in the workflow nodes
6. Activate the workflow

## How to Use

1. Paste company names into the Raw List tab with blank Status and Output columns
2. The workflow runs automatically every Friday at 4pm
3. Check the Master Sheet for qualified companies with research populated
4. Check the Raw List for GREEN or NOT GREEN results on every processed company

## Author

Nikhil Roy, Berlin-based operator with a background in project management, business development, and AI workflow automation.

Portfolio: https://nikhilroy.lovable.app
