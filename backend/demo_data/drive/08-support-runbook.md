# Phoenix support runbook

Phoenix is a customer onboarding workspace led by Maya Chen, with Arjun Patel owning engineering and Elena Ruiz owning QA. The launch moved from November 8 to November 15, 2026, to give QA an extra week. The SSO callback mismatch tracked as PHX-7 is the launch blocker. PHX-12 tracks the accessibility review. The release requires SSO login, an import checklist, and a verified admin handoff.

For a failed SSO login, verify the tenant callback URL and check PHX-7 status. For roster imports, collect the error code and retry only after the customer confirms the file. Escalate to Arjun Patel for auth failures and Priya Shah for onboarding questions.
