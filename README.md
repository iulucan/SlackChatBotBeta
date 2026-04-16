[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/GlQxzqll)

# 🌿 Project GreenLeaf: Enterprise AI HR Agent (Basel Ops)

## Team: PowerLeaf | Track: Guided Lab (Weeks 1-4)

### 1. Project Overview

This repository contains the logic, data governance, and integration architecture for the GreenLeaf Logistics AI HR Agent. Our goal is to automate the Tier-1 support triage for GreenLeaf employees - it must be accurate, persistent, and secure. We build a production-ready Slack Agent that manages HR knowledge across three domains: Policies (RAG), Holidays (OpenHolidays API), and Expenses (Python Logic).


### 2. 🛠 Tech Stack (Zero-Cost Tier)

-   **Interface:** __Slack Bolt for Python (Socket Mode)__.

-   **Brain:** Gemini 2.5 Flash Gemini 2.5 Flash-Lite (cheap). 

-   **Orchestration:** __Custom Python router__.

-   **Database:** __ChromaDB (Local Vector Store)__ + SQLite (Session Memory).

-   **External APIs:** OpenHolidays API (https://www.openholidaysapi.org) (For Swiss/Cantonal holidays data).
    
-   **Documentation:** GitHub Wiki (Technical Specs).
    
-   **Version Control:** GitHub Classroom.
    

### 3. How to Navigate

-   **`/data`**: Contains the cleaned, non-PII (Personally Identifiable Information) version of the GreenLeaf Handbook.
    
-   **`/logic`**: Exported JSON or Image files of the visual decision trees and system prompts.
    
-   **`Wiki`**: Detailed technical documentation, API specifications, and Swiss FADP (nDSG) compliance notes.
    
-   **`Projects`**: Our Agile Kanban board used for tracking Sprint progress and User Stories.
    

### 4. Project Objectives
1. **Architectual Decisions** Architectural decision are backed by rational arguments that are explainable.

1.  **Multi-Tool Orchestrator:** Identifying if a user query needs to call an API, use RAG or Python Logic.
    
2.  **Persistent Conversations:** Thread mapping and state management.
    
3.  **Data Governance & Security:** No sensitive GreenLeaf data is leaked via prompt injection. The data sent to any external service is non-PII.
    

### 5. Collaboration

-   **Issues:** Used for bug tracking and feature requests.
    
-   **Pull Requests:** All logic changes must be reviewed by the team before merging.
