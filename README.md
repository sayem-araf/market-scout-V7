# MarketScout V7

AI-Powered Business Feasibility Analyzer using Google Gemini AI.

## Overview

MarketScout performs comprehensive market research and feasibility analysis for business ideas using a multi-agent AI system.

## Features

- **Research Agent** - Gathers market data using Google Search
- **Analyst Agent** - Performs PESTLE and SWOT analysis
- **Visualizer Agent** - Creates radar charts with success probability

## Installation

```bash
pip install google-genai matplotlib numpy pandas
```

## Setup

Get your Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

Set as environment variable:
```bash
export GEMINI_API_KEY="your-api-key-here"
```

## Usage

### Basic Analysis
```bash
python market_scout.py "start a coffee shop in Seattle"
```

### With Custom Goal
```bash
python market_scout.py "AI tutoring platform" --goal "Market sizing and competitive analysis"
```

### Save Outputs
```bash
python market_scout.py "electric scooter rental" --save-chart chart.png --save-report report.md
```

### All Options
```bash
python market_scout.py "your business idea" \
  --goal "Analysis objective" \
  --save-chart output.png \
  --save-report report.md \
  --api-key "your-key" \
  --model "gemini-2.0-flash"
```

## Command Options

| Option | Description |
|--------|-------------|
| `topic` | Business idea to analyze (required) |
| `--goal` | Analysis objective (default: "Comprehensive Feasibility Study") |
| `--save-chart PATH` | Save radar chart to file |
| `--save-report PATH` | Save analysis report to markdown file |
| `--api-key` | Gemini API key (or use GEMINI_API_KEY env var) |
| `--model` | Gemini model to use (default: gemini-2.0-flash) |

## Output

The tool generates:
1. **Executive Summary** with success probability score
2. **PESTLE Analysis** table (Political, Economic, Social, Technological, Legal, Environmental)
3. **SWOT Analysis** table (Strengths, Weaknesses, Opportunities, Threats)
4. **Financial Verdict** with Go/No-Go recommendation
5. **Radar Chart** visualizing 5 key dimensions

## Main Functions

### `MarketScout.__init__(api_key, model)`
Initialize the analyzer with API credentials.

### `MarketScout.research(topic)`
Gather comprehensive market data for the topic.

### `MarketScout.analyze(raw_data, goal)`
Perform strategic analysis with PESTLE and SWOT.

### `MarketScout.visualize(analyst_output, save_path)`
Create radar chart from analysis data.

### `MarketScout.run_analysis(topic, goal, save_chart, save_report)`
Run complete end-to-end analysis pipeline.

## Requirements

- Python 3.7+
- google-genai
- matplotlib
- numpy
- pandas

## Version

7.0 (March 2026)
EOF
