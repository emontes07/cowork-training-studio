---
name: build-training-lab
description: "Build a training lab, create a hands-on workshop, or make a story-driven Copilot lab with fictional data, checked steps, and a saved offline HTML guide."
license: MIT
metadata:
  author: Cowork Training Studio
  version: "0.1.2"
---

# Build a training lab

Help the learner make a workshop they can follow, finish, and reuse.
Use this skill for "build a training lab", "create a hands-on workshop",
or "make a story-driven Copilot lab".

## Plan the experience

1. Call `list_session_formats`. For a hands-on HTML guide, choose `html_lab`.
   Ask for the audience, products, time available, and what learners should
   leave with. Ask about missing choices that would change what the lab teaches.
2. Call `get_lab_spec_schema` and use the returned contract, not a remembered
   version. Write a complete LabSpec using fictional practice content.
3. Give learners one role, one situation, a deadline, and a useful outcome.
   Keep one running Story sheet or equivalent artifact across the chapters.
   Follow the Close-to-Deck pattern without copying another lab's text or data:
   - Open each chapter with `story_so_far`, `builds_on`, and `you_will_add`.
   - Have each later step use something an earlier step produced.
   - Add named checkpoint files so learners can rejoin when they fall behind.
     For sessions of at least 90 minutes, provide them from chapter three onward.
   - Give prompts a mode, a clear outcome, and plain analyst-to-Copilot wording.
   - Include expected key facts for numerical work, source checks, and a short
     warning about uncertain figures or causes. Offer a manual-paste fallback.
   - Add a challenge without a prompt, with a hint and an answer to reveal later.
   - End with "Make it repeatable": save a reviewed prompt, ask Cowork to create
     a personal skill, approve its draft, and test it on fresh practice inputs.
     If skill creation is unavailable, reuse the saved prompt manually.
   Keep the work and chapter timings realistic for the requested duration.

## Check and render

4. Call `validate_lab_spec` with the complete spec. Fix every error and validate
   again. Address warnings by improving the content; explain any intentional
   remaining warning to the learner rather than hiding it.
5. Once valid, call `render_lab_page` with that same spec. If it returns errors,
   correct the spec and validate again before retrying.

## Save the exact page

6. Use Cowork's file tools to save the **exact returned `html` string** using
   the returned `filename`. Pass the tool result directly as file content:
   do not retype, summarize, reconstruct, wrap in Markdown, or alter the HTML.
   Keep inline styles and scripts so the guide works offline.
7. Confirm the save succeeded, then tell the learner the file name and provide
   the file link returned by the saving tool. If file saving is unavailable,
   say the page was rendered but not saved; do not invent a saved file or link.

## Offer the practice files

8. After saving the page, offer to create the practice files it lists.
   If the learner agrees, use Cowork's own file tools to create and save them:
   - Write the source files from the expected key facts, not the other way round.
     Use the same fictional numbers so the checked calculations reproduce the
     expected results. Make the "next" or test-data file use different input
     numbers from the main practice file, consistent with its own expected facts.
   - Put every quoted key fact (a clause, email sentence or policy wording)
     VERBATIM in the practice file that step uses, with the same section number.
     Preserve required quotes even when preparing fresh numerical test inputs.
   - If the overview or story quotes the same sentence differently, use the
     key-fact version in the practice file and tell the learner about the
     difference. Do not silently rewrite the saved lab.
   - Make each checkpoint contain exactly the state at the START of its chapter:
     carry forward earlier reviewed work, but not that chapter's new answers.
   - Keep answer keys clearly marked for facilitators, separate from learner
     source files and starting checkpoints.
9. Re-read every created file with Cowork's file tools. Confirm that every
   quoted key fact appears exactly: same words, same section number. Report
   any mismatch and fix the FILE, not the lab, then re-read it to confirm.
   Also check the fictional numbers and checkpoint states. If you cannot
   re-read a file, say its contents are unverified rather than claiming success.
   Confirm which files were saved and share the links returned by Cowork.

## Practice-data boundaries

- Use invented companies, role labels, documents and figures only.
- Never put tenant or customer data, real documents, personal information,
  credentials or secrets in the spec. Ask for fictional requirements instead.
- List source and checkpoint files honestly. A file entry is not a created
  workbook; provide links only to practice files that actually exist.
- The service checks and renders content. Cowork handles saving with the
  learner's permission. This is a demo build, not a production deployment.
- For legal, HR and compliance topics, include "practice exercise, not professional advice", use fictional parties only, and keep a "questions for an expert" step that separates interpretation from plain text.
