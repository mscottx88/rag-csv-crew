# Usability Test Protocol - RAG CSV Crew

**Success Criterion**: SC-005 - 90% of users can complete core tasks without documentation

**Test Date**: TBD
**Facilitator**: TBD
**Observer/Note-taker**: TBD

## Test Objectives

Validate that users can intuitively complete the following core tasks without referring to documentation:

1. **Upload CSV File**: Upload a CSV file and verify successful ingestion
2. **Submit Natural Language Query**: Ask a question about the data
3. **View Query Results**: Review the HTML-formatted response
4. **Review Query History**: Access past queries and responses
5. **Delete Dataset**: Remove an uploaded dataset

## Participant Criteria

- **Target Users**: Data analysts, business analysts, anyone who works with CSV data
- **Prerequisites**: Basic understanding of CSV files, no prior knowledge of the system required
- **Sample Size**: Minimum 10 participants per SC-005 (90% success = 9/10 must complete all tasks)

## Test Environment

- **System**: Web interface at http://localhost:5173 (frontend) + backend API
- **Sample Data**: Provide sales.csv, customers.csv from examples/ directory
- **Browser**: Chrome/Firefox/Edge latest versions
- **Screen Recording**: Record all sessions for post-test analysis

## Test Procedure

### Pre-Test (5 minutes)

1. **Welcome & Context**:
   - "Thank you for participating. We're testing a new tool for analyzing CSV data using natural language."
   - "Please think aloud as you work - describe what you're trying to do and what you expect to happen."
   - "There are no right or wrong actions. We're testing the interface, not you."

2. **Demographics**:
   - Role/job title
   - Frequency of CSV usage (daily/weekly/monthly/rarely)
   - Technical proficiency (beginner/intermediate/advanced)

3. **System Access**:
   - Provide username (test_user_01, test_user_02, etc.)
   - No password required (username-only authentication)
   - Open web interface

### Task 1: Upload CSV File (5 minutes)

**Instruction**: "Please upload the 'sales.csv' file from the desktop."

**Success Criteria**:
- User finds upload button/area without assistance
- User selects file and initiates upload
- User recognizes upload completion (progress indicator, success message)

**Observations**:
- Time to locate upload interface: _____ seconds
- Confusion points (if any): _____
- Success (yes/no): _____

**Help Threshold**: If >60 seconds with no progress, provide hint: "Look for a file upload area."

### Task 2: Submit Natural Language Query (5 minutes)

**Instruction**: "Ask the system: 'What are the top 5 sales by revenue?'"

**Success Criteria**:
- User finds query input area
- User types or speaks the question
- User submits the query
- User recognizes query is processing (loading indicator)

**Observations**:
- Time to locate query interface: _____ seconds
- Query submission method (type/paste/speak): _____
- Confusion points (if any): _____
- Success (yes/no): _____

**Help Threshold**: If >60 seconds, provide hint: "Look for a text input or search area."

### Task 3: View Query Results (3 minutes)

**Instruction**: "Review the answer to your question."

**Success Criteria**:
- User waits for query to complete (doesn't navigate away)
- User scrolls through HTML-formatted results
- User understands the answer (verified by asking: "What did the system tell you?")

**Observations**:
- Result comprehension (yes/no): _____
- Result presentation clarity (1-5 scale): _____
- Confusion points (if any): _____
- Success (yes/no): _____

### Task 4: Review Query History (3 minutes)

**Instruction**: "Find your previous questions and answers."

**Success Criteria**:
- User locates query history section
- User recognizes past queries in list
- User can click on a past query to view its response again

**Observations**:
- Time to locate history: _____ seconds
- Navigation method (sidebar/menu/button): _____
- Confusion points (if any): _____
- Success (yes/no): _____

**Help Threshold**: If >60 seconds, provide hint: "Check the navigation menu or sidebar."

### Task 5: Delete Dataset (3 minutes)

**Instruction**: "Remove the 'sales.csv' file you uploaded."

**Success Criteria**:
- User locates dataset management area
- User identifies delete action for specific dataset
- User confirms deletion (if prompted)
- User verifies dataset is removed from list

**Observations**:
- Time to locate delete function: _____ seconds
- Hesitation or concern about deletion: _____
- Confusion points (if any): _____
- Success (yes/no): _____

**Help Threshold**: If >60 seconds, provide hint: "Look for the list of uploaded files."

### Post-Test Questionnaire (5 minutes)

**System Usability Scale (SUS) - 10 questions, 1-5 Likert scale**:

1. I think that I would like to use this system frequently.
2. I found the system unnecessarily complex.
3. I thought the system was easy to use.
4. I think that I would need the support of a technical person to be able to use this system.
5. I found the various functions in this system were well integrated.
6. I thought there was too much inconsistency in this system.
7. I would imagine that most people would learn to use this system very quickly.
8. I found the system very cumbersome to use.
9. I felt very confident using the system.
10. I needed to learn a lot of things before I could get going with this system.

**SUS Score Calculation**: ((Sum of odd items - 5) + (25 - sum of even items)) × 2.5
**Target**: SUS score ≥ 68 (above average usability)

**Open-Ended Questions**:

1. What did you like most about the system?
2. What frustrated you the most?
3. What would you change to make it easier to use?
4. Would you use this system for your own work? Why or why not?

## Data Collection

### Task Completion Matrix

| Participant | Task 1 | Task 2 | Task 3 | Task 4 | Task 5 | Success Rate |
|-------------|--------|--------|--------|--------|--------|--------------|
| P01         | ☐      | ☐      | ☐      | ☐      | ☐      | 0/5          |
| P02         | ☐      | ☐      | ☐      | ☐      | ☐      | 0/5          |
| P03         | ☐      | ☐      | ☐      | ☐      | ☐      | 0/5          |
| P04         | ☐      | ☐      | ☐      | ☐      | ☐      | 0/5          |
| P05         | ☐      | ☐      | ☐      | ☐      | ☐      | 0/5          |
| P06         | ☐      | ☐      | ☐      | ☐      | ☐      | 0/5          |
| P07         | ☐      | ☐      | ☐      | ☐      | ☐      | 0/5          |
| P08         | ☐      | ☐      | ☐      | ☐      | ☐      | 0/5          |
| P09         | ☐      | ☐      | ☐      | ☐      | ☐      | 0/5          |
| P10         | ☐      | ☐      | ☐      | ☐      | ☐      | 0/5          |
| **TOTAL**   |        |        |        |        |        | **0/50**     |

**SC-005 Requirement**: ≥45/50 tasks completed (90% success rate)

### Time Metrics

| Task | P01 | P02 | P03 | P04 | P05 | P06 | P07 | P08 | P09 | P10 | Avg | Target |
|------|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|--------|
| T1   |     |     |     |     |     |     |     |     |     |     |     | <60s   |
| T2   |     |     |     |     |     |     |     |     |     |     |     | <60s   |
| T3   |     |     |     |     |     |     |     |     |     |     |     | <30s   |
| T4   |     |     |     |     |     |     |     |     |     |     |     | <60s   |
| T5   |     |     |     |     |     |     |     |     |     |     |     | <60s   |

## Analysis & Reporting

### Quantitative Analysis

1. **Overall Success Rate**: ___ / 50 tasks completed (___%)
   - **Pass/Fail**: SC-005 requires ≥90% (45/50 tasks)

2. **Task-Specific Success Rates**:
   - Task 1 (Upload): ___ / 10 (___%)
   - Task 2 (Query): ___ / 10 (___%)
   - Task 3 (Results): ___ / 10 (___%)
   - Task 4 (History): ___ / 10 (___%)
   - Task 5 (Delete): ___ / 10 (___%)

3. **Average SUS Score**: _____ (target: ≥68)

4. **Time Performance**:
   - Average time per task: _____
   - Tasks exceeding target time: _____

### Qualitative Analysis

1. **Common Pain Points** (from observations + open-ended feedback):
   - Issue 1: _____
   - Issue 2: _____
   - Issue 3: _____

2. **Usability Strengths**:
   - Positive 1: _____
   - Positive 2: _____
   - Positive 3: _____

3. **Recommended Improvements** (prioritized by impact):
   - Priority 1: _____
   - Priority 2: _____
   - Priority 3: _____

### Video Analysis (Optional)

- Review screen recordings for unexpected behaviors
- Document "aha moments" vs "confusion moments"
- Track mouse movements, hesitation patterns, error recovery

## Success Criteria Validation

**SC-005 Requirement**: 90% of users complete core tasks without documentation

**Result**: _____ / 10 users (___%) completed all 5 tasks successfully

**Status**:
- ✅ **PASS**: ≥9/10 users completed all tasks
- ❌ **FAIL**: <9/10 users completed all tasks

**Recommendations**:
- If **PASS**: Document successful patterns for future design reference
- If **FAIL**: Prioritize identified usability issues for redesign, re-test after fixes

## Appendix

### Sample CSV Data (sales.csv)

```csv
date,product,revenue,quantity,region
2024-01-15,Widget A,1500.00,50,North
2024-01-20,Widget B,2300.00,75,South
2024-01-22,Widget A,1200.00,40,East
2024-01-25,Widget C,3500.00,100,West
2024-01-28,Widget B,1800.00,60,North
```

### Sample CSV Data (customers.csv)

```csv
customer_id,customer_name,city,state,total_orders
1,Alice Johnson,San Francisco,CA,12
2,Bob Smith,New York,NY,8
3,Carol Williams,Los Angeles,CA,15
4,David Brown,Chicago,IL,5
5,Eve Davis,Boston,MA,10
```

### Test Script Template

**Facilitator Script**: "I'm going to ask you to complete 5 tasks using this system. Please think aloud as you work - tell me what you're looking for, what you're clicking on, and what you expect to happen. Remember, we're testing the interface, not you. If something is confusing, that's valuable feedback for us. Do you have any questions before we start?"

**Between Tasks**: "Great, let's move to the next task."

**After All Tasks**: "Thank you! Now I have a few questions about your experience."

## Version History

- v1.0 (2026-02-05): Initial protocol created per SC-005 requirement
