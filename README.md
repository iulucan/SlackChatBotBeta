[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/GlQxzqll)

# 🌿 Project GreenLeaf: Enterprise AI HR Agent (Basel Ops)

## Team: GreenLeaf | Track: Guided Lab (Weeks 1-4)

### 1. Project Overview

This repository contains the logic, data governance, and integration architecture for the GreenLeaf Logistics AI HR Agent. Our goal is to automate the Tier-1 support triage for GreenLeaf employees - it must be accurate, persistent, and secure. We build a production-ready Slack Agent that manages HR knowledge across three domains: Policies (RAG / Context Stuffing), Holidays (Live API), and Expenses (Python Logic).


### 2. 🛠 Tech Stack (Zero-Cost Tier)
Generally speaking the Tech Stack is open for you to choose from. However be mindfull about which technologies you choose and make sure to be able to argument about why you made which decision.

-   **Interface:** Slack Bolt for Python (Socket Mode), React (or any other Web Framework), or Python CLI with Textual.

-   **Brain:** Gemini 2.5 Flash (cheap), but any other model is fine as well. We will provie API keys for you upon request. 

-   **Orchestration:** LangChain Agents, custom Python Router or Agent Development Kit from Google.

-   **Database:** ChromaDB (Local Vector Store) + SQLite (Session Memory), or any equivalent.

-   **External APIs:** OpenHolidays API (https://www.openholidaysapi.org) (For Swiss/Cantonal data).
    
-   **Documentation:** GitHub Wiki (Technical Specs)
    
-   **Version Control:** GitHub Classroom
    

### 3. How to Navigate

-   **`/data`**: Contains the cleaned, non-PII (Personally Identifiable Information) version of the GreenLeaf Handbook.
    
-   **`/logic`**: Exported JSON or Image files of the visual decision trees and system prompts.
    
-   **`Wiki`**: Detailed technical documentation, API specifications, and Swiss FADP (nDSG) compliance notes.
    
-   **`Projects`**: Our Agile Kanban board used for tracking Sprint progress and User Stories.
    

### 4. Project Objectives
1. **Architectual Decisions** Each architectural decision must be backed by rational arguments that you must be able to explain.

1.  **Multi-Tool Orchestrator:** Successfully identify if a user query needs to call an API, use RAG or Python Logic.
    
2.  **Persistent Conversations:** Ensure thread mapping and state management.
    
3.  **Data Governance & Security:** Ensure no sensitive GreenLeaf data is leaked via prompt injection. Make sure the data sent to any external service is non-PII.
    

### 5. Collaboration

-   **Issues:** Used for bug tracking and feature requests.
    
-   **Pull Requests:** All logic changes must be reviewed by the team before merging.
