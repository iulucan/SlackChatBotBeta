
# Project: GreenLeaf Smart Ops Assistant

## Team: [Team Name] | Track: Guided Lab (Weeks 1-4)

### 1. Project Overview

This repository contains the logic, data governance, and integration architecture for the GreenLeaf Logistics AI Agent. Our goal is to automate the Tier-1 support triage for GreenLeaf employees, specifically focusing on holiday logic and onboarding documentation.

### 2. Tech Stack

-   **Logic Engine:** Voiceflow / Botpress (AI Conversational Logic)
    
-   **Integration:** Zapier / Make.com (Workflow Automation)
    
-   **Database:** Google Sheets API (Knowledge Base & Logging)
    
-   **Documentation:** GitHub Wiki (Technical Specs)
    
-   **Version Control:** GitHub Classroom
    

### 3. How to Navigate

-   **`/data`**: Contains the cleaned, non-PII (Personally Identifiable Information) version of the GreenLeaf Handbook and the Cantonal Holiday CSV.
    
-   **`/logic`**: Exported JSON or Image files of the visual decision trees and system prompts.
    
-   **`Wiki`**: Detailed technical documentation, API specifications, and Swiss FADP (nDSG) compliance notes.
    
-   **`Projects`**: Our Agile Kanban board used for tracking Sprint progress and User Stories.
    

### 4. Project Objectives

1.  **Triage Agent:** Successfully identify if a user query is a "Standard" vs. "High-Priority" case.
    
2.  **Holiday Logic:** Correctly calculate leave eligibility based on Basel-specific vs. National holiday data.
    
3.  **Data Governance:** Ensure no sensitive GreenLeaf data is leaked via prompt injection.
    

### 5. Collaboration

-   **Issues:** Used for bug tracking and feature requests.
    
-   **Pull Requests:** All logic changes must be reviewed by the team before merging.
