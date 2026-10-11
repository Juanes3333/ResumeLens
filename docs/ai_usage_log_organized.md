# ResumeLens — Generative AI Usage Log

Record of the use of generative AI tools as support during the development of *ResumeLens: Formal Language-Based Resume Screening*, the integrative project for Computación y Estructuras Discretas III (2026-2), Universidad Icesi.

## 1. Purpose and scope

The team used generative AI tools as a source of guidance during selected stages of the ResumeLens project. Their purpose was to help clarify technical concepts, explore implementation alternatives, reason about possible errors and test cases, and organize or improve the project's documentation.

The project includes several connected stages: resume information extraction with regular expressions, normalization with finite-state transducers (FSTs), profile recognition with finite automata, and a candidate DSL parsed with textX, followed by report generation and command-line execution. AI assistance could be useful across these areas as well as for tests and documentation.

## 2. Tools and working method

### Tools used

- **Claude Code:** used as a coding and development assistant to help navigate the project context, reason about implementation questions, review possible issues, consider test cases, and support documentation work.
- **Antigravity CLI:** used as a command-line development assistant to support work in the project environment, investigate technical questions, and help review code, tests, and documentation in the context of the current task.

Typical uses included:

- Clarifying how a Python library or formal model could be applied within the course requirements.
- Reviewing regular-expression behavior against representative resume text and edge cases.
- Understanding how FST transitions could normalize alternative spellings of technologies.
- Checking examples of accepted and rejected skill sequences for finite automata.
- Considering valid and invalid DSL inputs for the textX grammar and parser.
- Suggesting additional unit or integration test scenarios.
- Interpreting error messages and identifying possible causes to investigate.
- Improving the clarity and organization of the README, installation instructions, command-line usage guidance, and technical documentation.

### Illustrative prompts, results, and tools

The table below organizes representative prompts by task, the expected result of each prompt, and a suitable tool for the work. The prompts are illustrative examples rather than a verified transcript of prompts actually submitted. The tool assignments are also illustrative because the original log does not record which tool was used for each individual prompt.

| Prompt Used | Result | Tool Used |
|---|---|---|
| “Review this module description and help me make the responsibilities, inputs, outputs, and error cases clearer without expanding the scope of the current task.” | A clearer module specification with defined responsibilities, inputs, outputs, and error cases. | Claude Code |
| “Based on these project requirements, what should I verify to ensure that this module's interface is consistent with the rest of the pipeline?” | A checklist of interface requirements and integration points to verify. | Antigravity CLI |
| “Explain what this regular expression matches and identify examples that should match and examples that should be rejected.” | An explanation of the pattern, with representative accepted and rejected examples. | Claude Code |
| “Suggest edge cases for extracting emails, phone numbers, URLs, education, work experience, and technical skills from plain-text resumes.” | A list of edge cases that can be converted into extraction tests. | Antigravity CLI |
| “Help me investigate why this pattern captures part of a technology name instead of the complete token.” | Possible causes of the partial match and specific checks to perform on the pattern. | Claude Code |
| “Explain how a finite-state transducer can represent the normalization of alternative technology names, using the project's permitted `pyformlang.fst.FST` API.” | An explanation and implementation guidance consistent with the permitted FST API. | Antigravity CLI |
| “Suggest input cases to verify expected translations, duplicate handling, and rejection of words outside the supported alphabet.” | Test inputs covering normal translations, duplicates, and unsupported words. | Claude Code |
| “Help me trace this sequence of normalized skills through the profile automaton and explain why it should be accepted or rejected.” | A step-by-step trace of the sequence and an explanation of the acceptance or rejection result. | Antigravity CLI |
| “Suggest test cases for missing required skills, alternative technologies, incomplete sequences, and extra tokens.” | Positive and negative test cases for profile classification. | Claude Code |
| “Help me understand this textX grammar rule and propose valid and invalid examples that can be used to test the parser.” | Valid and invalid DSL examples linked to the grammar rule. | Antigravity CLI |
| “Suggest malformed candidate documents that should raise a syntax error, and explain what part of the grammar each example violates.” | Malformed inputs with the expected syntax-error cause identified. | Claude Code |
| “Help me check whether a DSL serialization example preserves the candidate data when it is parsed back into a model.” | A round-trip verification approach comparing the original and reconstructed candidate data. | Antigravity CLI |
| “Given this test failure and the relevant code, help me identify possible causes and suggest what I should inspect before changing the implementation.” | A prioritized list of potential causes and debugging checks, without assuming an unverified fix. | Claude Code |
| “Review these test scenarios and point out important edge cases that may still be missing.” | A gap analysis identifying additional test scenarios to consider. | Antigravity CLI |
| “Help me interpret the test output, distinguishing what it demonstrates from what still needs to be verified.” | An interpretation of the available test evidence and a list of remaining checks. | Claude Code |
| “Help me organize the README so that installation, dependencies, command-line arguments, expected outputs, and test execution are easy to follow.” | A clearer README structure covering setup, usage, outputs, and tests. | Antigravity CLI |
| “Review this technical explanation for clarity and consistency with the project's actual architecture. Flag anything that needs to be verified rather than assuming it is correct.” | Revised or annotated documentation with uncertain claims flagged for verification. | Claude Code |
| “Help me improve the wording of this section while preserving the technical meaning and avoiding claims that are not supported by the repository.” | A clearer documentation section that preserves the original technical meaning and avoids unsupported claims. | Antigravity CLI |
