# Rule: Auto-Grader & Multi-Agent Competition Compliance

1. **Metadata Key Precision:** Always match exact schema keys specified in README (`model`, `parameter_size`, `framework`, `runtime`). Never substitute `model` with `model_name`.
2. **Zip Submission Integrity:** Ensure submission zip files contain target JSON files directly at root level without unintended directory nesting.
3. **Secret Isolation & Git Commit:** Always include `.gitignore` for `.env` and `*.zip` artifacts. Commit all source code to git prior to creating the submission zip.
4. **Evidence ID Format Verification:** Verify evidence IDs follow exact string templates (`order:<id>`, `item:<order_id>:<item_id>`, `payment:<order_id>:<seq>`, `seller:<seller_id>`, `policy:<root_cause_code>`).
