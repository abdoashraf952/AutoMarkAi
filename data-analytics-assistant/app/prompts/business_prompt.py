"""Prompt templates for the Business Analysis Agent."""

BUSINESS_SYSTEM = """You are a Senior Business Intelligence Analyst with 15+ years of experience 
across Sales, Retail, Marketing, Finance, HR, Operations, and E-Commerce. 
You excel at identifying business context from raw data structures."""

BUSINESS_PROMPT = """
Analyze this dataset profile and determine the business domain and context.

## Dataset Overview
- File Name: {file_name}
- Rows: {row_count:,}
- Columns: {column_count}

## Column Names and Types
{column_details}

## Sample Data (first 3 rows)
{sample_data}

## Statistical Summary
{stats_summary}

Based on this information, determine:

Return a JSON object with this exact structure:
{{
  "business_domain": "<one of: Sales, Retail, Marketing, Finance, HR, Operations, E-Commerce, Healthcare, Logistics, Education, Other>",
  "domain_confidence": <float 0.0 to 1.0>,
  "domain_reasoning": "<2-3 sentence explanation of why you chose this domain>",
  "likely_business_processes": ["<process1>", "<process2>", "<process3>"],
  "key_entities": ["<entity1>", "<entity2>"],
  "time_dimension": "<column name if temporal data exists, else null>",
  "primary_metric_columns": ["<col1>", "<col2>"],
  "dimension_columns": ["<col1>", "<col2>"],
  "business_context_summary": "<1 paragraph describing what this data represents>"
}}
"""
