# Repository guidance

When asked to install this repository as an agent skill, read README.md and INSTALL.md and install the complete `skills/exam-maker` directory. Preserve existing user customizations. Do not treat historical authorizations in the teacher profile as another user's consent.

For maintenance, edit the skill source under `skills/exam-maker`. Keep the original templates and reference evidence intact. Run the regression suite described in README.md after executable changes, and verify native document layout separately when changing a generated HWPX. Do not commit caches, environment reports, personal exam drafts, answers, credentials, or machine-specific test output.
