#!/usr/bin/env python3
"""
MarketScout V7 - AI-Powered Business Feasibility Analyzer

A professional tool that uses Google's Gemini AI to conduct comprehensive
market research and feasibility analysis for business ideas.

Features:
- Multi-agent AI system (Researcher, Analyst, Visualizer)
- PESTLE and SWOT analysis
- Visual radar charts showing success probability
- Command-line interface with flexible options

Author: AI Agent System
Version: 7.0
"""

import json
import re
import ast
import os
import sys
import argparse
from math import pi
from typing import Dict, List, Optional, Tuple

# Third-party imports (will be checked/installed)
try:
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    from google import genai
    from google.genai import types
except ImportError as e:
    print(f" Missing required package: {e}")
    print("Install dependencies: pip install google-genai matplotlib numpy pandas")
    sys.exit(1)


class MarketScout:
    """
    Main class for conducting AI-powered market research and feasibility analysis.
    
    This class orchestrates three AI agents:
    1. Researcher: Gathers market data and competitive intelligence
    2. Analyst: Performs PESTLE and SWOT analysis
    3. Visualizer: Creates radar charts and visual reports
    """
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        """
        Initialize MarketScout with API credentials.
        
        Args:
            api_key: Google Gemini API key
            model: Gemini model to use (default: gemini-2.0-flash)
        """
        self.api_key = api_key
        self.model = model
        self.client = None
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize the Gemini AI client."""
        try:
            print("Initializing MarketScout V7...")
            self.client = genai.Client(api_key=self.api_key)
            print("System Online.\n")
        except Exception as e:
            print(f"Authentication Error: {e}")
            sys.exit(1)
    
    def research(self, topic: str) -> str:
        """
        Agent 1: Research - Gather comprehensive market data.
        
        Args:
            topic: The business idea or topic to research
            
        Returns:
            Raw research data as text
        """
        print(f"🔎 SCOUT: Conducting 360° research on '{topic}'...")
        
        prompt = (
            f"Research topic: {topic}\n"
            f"MISSION: Gather data for a comprehensive feasibility study.\n"
            f"REQUIRED DIMENSIONS:\n"
            f"1. Market: TAM/SAM/SOM, Growth Rate, Competitor Density.\n"
            f"2. PESTLE: Regulatory hurdles, Economic tailwinds, Social trends.\n"
            f"3. Financials: Margins, CapEx requirements, Burn rate.\n"
            f"4. Risks: Porter's 5 Forces (Supplier power, Barrier to entry).\n"
            f"OUTPUT: A dense Fact Sheet with citations."
        )
        
        search_tool = types.Tool(google_search=types.GoogleSearch())
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(tools=[search_tool])
            )
            print("✅ Research complete.\n")
            return response.text
        except Exception as e:
            error_msg = f"Research Error: {e}"
            print(f"{error_msg}")
            return error_msg
    
    def analyze(self, raw_data: str, goal: str) -> str:
        """
        Agent 2: Analyst - Perform strategic analysis.
        
        Args:
            raw_data: Research data from the research agent
            goal: Analysis objective
            
        Returns:
            Structured analysis report with PESTLE, SWOT, and JSON data
        """
        print("ANALYST: Running PESTLE & Risk Models...")
        
        prompt = (
            f"You are a Chief Strategy Officer. Goal: {goal}\n"
            f"Data: {raw_data}\n\n"
            f"TASK: Perform a Deep Spectrum Analysis. Use PROFESSIONAL FORMATTING.\n\n"
            f"SECTION 1: EXECUTIVE SUMMARY\n"
            f"- The 'BLUF' (Bottom Line Up Front).\n"
            f"- Success Probability Score (0-100%).\n\n"
            f"SECTION 2: PESTLE ANALYSIS (Use a Markdown Table)\n"
            f"| Factor | Trend | Implication |\n"
            f"| Political | ... | ... |\n\n"
            f"SECTION 3: SWOT ANALYSIS (Use a Markdown Table)\n"
            f"| Strengths | Weaknesses |\n"
            f"| Opportunities | Threats |\n\n"
            f"SECTION 4: FINANCIAL VERDICT\n"
            f"- Clear Go/No-Go recommendation with rationale.\n\n"
            f"SECTION 5: JSON DATA (Strict Format)\n"
            f"Generate the raw JSON for the Radar Chart. Use DOUBLE QUOTES for keys.\n"
            f'Format: ```json\n{{"Success_Probability": "75%", "Scores": [80, 40, 60, 90, 70]}}\n```'
        )
        
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            print("Analysis complete.\n")
            return response.text
        except Exception as e:
            error_msg = f"Analysis Error: {e}"
            print(f"{error_msg}")
            return error_msg
    
    def visualize(self, analyst_output: str, save_path: Optional[str] = None) -> Optional[Dict]:
        """
        Agent 3: Visualizer - Create radar chart from analysis.
        
        Args:
            analyst_output: Analysis report containing JSON data
            save_path: Optional path to save the chart image
            
        Returns:
            Dictionary containing the visualization data, or None if error
        """
        print("🎨 VISUALIZER: Generating Radar Chart...")
        
        try:
            # Extract JSON data from the analysis
            json_match = re.search(r"```json\n(.*?)\n```", analyst_output, re.DOTALL)
            if not json_match:
                print("No JSON data found in analysis output")
                return None
            
            json_str = json_match.group(1)
            
            # Parse JSON (try both json.loads and ast.literal_eval)
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                data = ast.literal_eval(json_str)
            
            scores = data['Scores']
            success_prob = data['Success_Probability']
            categories = [
                'Market Demand',
                'Low Competition',
                'Regulatory Ease',
                'Financial Upside',
                'Tech Readiness'
            ]
            
            # Validate scores
            if len(scores) != len(categories):
                print(f"Score count mismatch: got {len(scores)}, expected {len(categories)}")
                return None
            
            # Create radar chart
            N = len(categories)
            angles = [n / float(N) * 2 * pi for n in range(N)]
            angles += angles[:1]
            scores += scores[:1]
            
            fig = plt.figure(figsize=(10, 10))
            ax = plt.subplot(111, polar=True)
            
            # Configure chart
            plt.xticks(angles[:-1], categories, size=12)
            ax.set_rlabel_position(0)
            plt.yticks([20, 40, 60, 80], ["20", "40", "60", "80"], color="grey", size=10)
            plt.ylim(0, 100)
            
            # Plot data
            ax.plot(angles, scores, linewidth=2, linestyle='solid', color='#2E86AB')
            ax.fill(angles, scores, color='#2E86AB', alpha=0.25)
            
            # Add title
            plt.title(
                f"Venture Viability Profile\nSuccess Probability: {success_prob}",
                size=16,
                weight='bold',
                y=1.1
            )
            
            # Save or show
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                print(f"Chart saved to: {save_path}")
            else:
                plt.show()
            
            plt.close()
            
            return data
            
        except Exception as e:
            print(f"Visualization Error: {e}")
            return None
    
    def run_analysis(
        self,
        topic: str,
        goal: str = "Comprehensive Feasibility Study",
        save_chart: Optional[str] = None,
        save_report: Optional[str] = None
    ) -> Tuple[str, Optional[Dict]]:
        """
        Run complete end-to-end analysis.
        
        Args:
            topic: Business idea to analyze
            goal: Analysis objective
            save_chart: Optional path to save the radar chart
            save_report: Optional path to save the markdown report
            
        Returns:
            Tuple of (analysis_report, visualization_data)
        """
        print(f"{'='*70}")
        print(f"🚀 DEEP DIVE ANALYSIS: {topic}")
        print(f"{'='*70}\n")
        
        # Step 1: Research
        research_data = self.research(topic)
        
        # Step 2: Analyze
        analysis = self.analyze(research_data, goal)
        
        # Step 3: Visualize
        viz_data = self.visualize(analysis, save_path=save_chart)
        
        # Step 4: Clean up report (remove JSON section)
        clean_report = re.sub(r"SECTION 5: JSON DATA.*", "", analysis, flags=re.DOTALL)
        
        # Save report if requested
        if save_report:
            with open(save_report, 'w', encoding='utf-8') as f:
                f.write(f"# Market Analysis: {topic}\n\n")
                f.write(f"**Analysis Goal:** {goal}\n\n")
                f.write(clean_report)
            print(f"Report saved to: {save_report}\n")
        
        # Print report to console
        print(f"\n{'='*70}")
        print("📊 ANALYSIS REPORT")
        print(f"{'='*70}\n")
        print(clean_report)
        
        return clean_report, viz_data


def get_api_key() -> str:
    """
    Get Gemini API key from environment or user input.
    
    Returns:
        API key string
    """
    api_key = os.environ.get('GEMINI_API_KEY')
    
    if not api_key:
        print("🔑 API Key not found in environment variables.")
        api_key = input("Enter your Gemini API Key: ").strip()
    
    if not api_key:
        print("API key is required to run MarketScout")
        sys.exit(1)
    
    return api_key


def main():
    """Main entry point for command-line usage."""
    parser = argparse.ArgumentParser(
        description="MarketScout V7 - AI-Powered Business Feasibility Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic analysis
  python market_scout.py "start a coffee shop in Seattle"
  
  # With custom goal
  python market_scout.py "AI tutoring platform" --goal "Market sizing and competitive analysis"
  
  # Save outputs
  python market_scout.py "electric scooter rental" --save-chart chart.png --save-report report.md
  
  # Set API key via environment
  export GEMINI_API_KEY="your-key-here"
  python market_scout.py "blockchain startup"
        """
    )
    
    parser.add_argument(
        'topic',
        type=str,
        help='Business idea or topic to analyze'
    )
    
    parser.add_argument(
        '--goal',
        type=str,
        default='Comprehensive Feasibility Study',
        help='Analysis objective (default: Comprehensive Feasibility Study)'
    )
    
    parser.add_argument(
        '--save-chart',
        type=str,
        metavar='PATH',
        help='Save radar chart to file (e.g., chart.png)'
    )
    
    parser.add_argument(
        '--save-report',
        type=str,
        metavar='PATH',
        help='Save analysis report to markdown file (e.g., report.md)'
    )
    
    parser.add_argument(
        '--api-key',
        type=str,
        help='Gemini API key (or set GEMINI_API_KEY environment variable)'
    )
    
    parser.add_argument(
        '--model',
        type=str,
        default='gemini-2.0-flash',
        help='Gemini model to use (default: gemini-2.0-flash)'
    )
    
    args = parser.parse_args()
    
    # Get API key
    api_key = args.api_key or get_api_key()
    
    # Initialize MarketScout
    scout = MarketScout(api_key=api_key, model=args.model)
    
    # Run analysis
    scout.run_analysis(
        topic=args.topic,
        goal=args.goal,
        save_chart=args.save_chart,
        save_report=args.save_report
    )
    
    print(f"\n{'='*70}")
    print("✨ Analysis Complete!")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
