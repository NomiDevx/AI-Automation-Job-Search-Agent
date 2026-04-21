AI Automation Job Search Agent

Developed an intelligent automation system using Python and Selenium to streamline job discovery for AI-related roles across multiple platforms.

🔹 Key Features:
Automated job scraping from LinkedIn, Indeed, and Google
Extracts structured job data including:
Job Title, Company, Location
Posting Date, Salary (if available)
Job Description & Direct URL
Simulates human-like browsing behavior to avoid detection
Handles dynamic web elements, popups, and pagination
Stores results in organized CSV files (per platform + combined dataset)

🔹 Tech Stack:
Python
Selenium WebDriver
Chrome Automation
CSV Data Handling
Dataclasses for structured data modeling

🔹 Output:
Generates separate datasets:
jobs_linkedin.csv
jobs_indeed.csv
jobs_google.csv
Creates a unified dataset:
jobs_all_combined_<timestamp>.csv

🔹 Highlights:
Built a robust scraping engine with error handling for real-world dynamic websites
Designed reusable utilities for element extraction and scrolling automation
Implemented multi-source aggregation for better job discovery insights
