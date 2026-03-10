
# 🌿 Project GreenLeaf: Enterprise AI HR Agent (Basel Ops)

## Team: [Team Name] | Track: Guided Lab (Weeks 1-4)

### 1. Project Overview

This repository contains the logic, data governance, and integration architecture for the GreenLeaf Logistics AI HR Agent. Our goal is to automate the Tier-1 support triage for GreenLeaf employees - it must be accurate, persistent, and secure. We build a production-ready Slack Agent that manages HR knowledge across three domains: Policies (RAG), Holidays (Live API), and Expenses (Python Logic).


### 2. 🛠 Tech Stack (Zero-Cost Tier)
-   **Interface:** Slack Bolt for Python (Socket Mode).

-   **Brain:** Gemini 2.0 Flash.

-   **Orchestration:** LangChain Agents or custom Python Router.

-   **Database:** ChromaDB (Local Vector Store) + SQLite (Session Memory)

-   **Holidays:** https://www.openholidaysapi.org (Swiss/Cantonal data)
    
-   **Documentation:** GitHub Wiki (Technical Specs)
    
-   **Version Control:** GitHub Classroom
    

### 3. How to Navigate

-   **`/data`**: Contains the cleaned, non-PII (Personally Identifiable Information) version of the GreenLeaf Handbook.
    
-   **`/logic`**: Exported JSON or Image files of the visual decision trees and system prompts.
    
-   **`Wiki`**: Detailed technical documentation, API specifications, and Swiss FADP (nDSG) compliance notes.
    
-   **`Projects`**: Our Agile Kanban board used for tracking Sprint progress and User Stories.
    

### 4. Project Objectives

1.  **Spec-First Design:** Use GitHub Spec Kit to map the "Bereavement" and "Vacation" logic before coding.

1.  **Multi-Tool Orchestrator:** Successfully identify if a user query needs to call an API, uses RAG or Python Logic.
    
2.  **Persistent Conversations:** Ensure thread mapping and state management.
    
3.  **Data Governance & Security:** Ensure no sensitive GreenLeaf data is leaked via prompt injection. Make sure the data sent to any external service is non-PII.
    

### 5. Collaboration

-   **Issues:** Used for bug tracking and feature requests.
    
-   **Pull Requests:** All logic changes must be reviewed by the team before merging.
