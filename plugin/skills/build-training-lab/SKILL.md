---
name: build-training-lab
description: "Build a training lab, create a hands-on workshop, or make a story-driven Copilot lab with fictional data, checked steps, and a saved offline HTML guide."
license: MIT
metadata:
  author: Cowork Training Studio
  version: "0.1.4"
---

# Build a training lab

Help the learner make a workshop they can follow, finish, and reuse.
Use this skill for "build a training lab", "create a hands-on workshop",
or "make a story-driven Copilot lab".
Use the connector's tool names EXACTLY as listed, including prefixes; never guess
a tool name. If a required tool is missing, report the blocker explicitly.

## Plan the experience

1. Call `list_session_formats`. For a hands-on HTML guide, choose `html_lab`.
   Ask for the audience, products, time available, and what learners should
   leave with. Ask about missing choices that would change what the lab teaches.
   If the learner has no shape in mind, call `get_blueprint` without an ID.
   Offer its three choices in one line each, then call it with the chosen
   `blueprint_id` and follow `chapter_outline`, `quality_bar` and `ends_with`.
   For `domain_super_day`, use `chapter_outline` as the day agenda, breaks included.
   Follow each `lab_id` to `lab_outlines` and build each separately as `html_lab`.
   The prompt-challenge close is also `html_lab` until `prompt_a_thon` ships.
   Keep the same invented company across the day; never invent available formats.
2. Call `get_lab_spec_schema` and use the returned contract, not a remembered
   version. Write `schema_version: "2.1"` using fictional practice content.
   Use typed `expected.key_facts`: `quote` or `clause` for document quotations,
   with `source_file` naming a declared file ID and `section` matching its source.
   Use `number` for checked figures and `fact` for other evidence.
3. Give learners one role, one situation, a deadline, and a useful outcome.
   Keep one running Story sheet or equivalent artifact across the chapters.
   Declare `through_line.headings`; only carry forward into those headings.
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

## Check the spec

4. Call `validate_lab_spec` with the complete spec. Fix EVERY error and warning
   and validate again until both counts are zero, before rendering.
   If a warning cannot be resolved, explain the blocker; do not hide or waive it.

## Build the facilitator pack

5. After clean validation, use Cowork's own file tools, with learner permission,
   to build the practice files from the key facts. Save in the output location:
   - Use real .docx or .xlsx where learners would receive Word or Excel files.
     Use Markdown only for plain notes; never rename text files as Office files.
   - `<lab-slug>/learner/`: sources, fresh test data, worksheets and checkpoints.
   - `<lab-slug>/facilitator/`: answer keys and `facilitator-notes.md`.
   - The notes give a run of show by chapter, what to hand out, dates and
     expected answers; mark them and the keys "Facilitator only".
   - Write the source files from the expected key facts, not the other way round.
     Use the same fictional numbers so the checked calculations reproduce the
     expected results. Make the "next" or test-data file use different input
     numbers from the main practice file, consistent with its own expected facts.
   - Put every quoted key fact (a clause, email sentence or policy wording)
     VERBATIM in the practice file that step uses, with the same section number.
     Preserve required quotes even when preparing fresh numerical test inputs.
   - If the overview or story quotes the same sentence differently, use the
     key-fact version and tell the learner about the difference. Correct the
     draft before validation; never silently rewrite an already saved lab.
   - Make each checkpoint contain exactly the state at the START of its chapter:
     carry forward earlier reviewed work, but not that chapter's new answers.
   - Keep answer keys clearly marked for facilitators, separate from learner
     source files and starting checkpoints.
6. Only after saving the files, set learner `files[].href` to `learner/<filename>`
   and `audience: "learner"`. Set keys and notes to `audience: "facilitator"`
   with NO `href`; list the notes with `kind: "answer_key"`. Keep source IDs stable.
   Never invent links to unsaved files or link facilitator material from the page.
7. Validate the updated complete spec again to zero errors AND zero warnings,
   then call `render_lab_page` with that same spec. If it returns errors, correct
   the spec and validate again before retrying.

## Save and verify the exact page

8. Use Cowork's file tools to save the **exact returned `html` string** using
   the returned `filename` at `<lab-slug>/<lab-slug>.html`. Align the pack folder
   name with the returned filename's stem; keep learner/facilitator paths relative.
   Pass the tool result directly as file content: do not retype, summarize,
   reconstruct, wrap in Markdown, or alter HTML. Keep inline styles and scripts.
   Share or publish the folder together, not the HTML alone, so its links work.
9. Re-read EVERY saved file, including the HTML, with Cowork's file tools.
   Confirm every quoted key fact appears word for word with the same section
   number in each practice file that uses it. Report mismatches and fix the FILE,
   not the lab's canonical facts, then re-read it. Check checkpoint starting states.
   Check every date and number calculation with code, using the fictional inputs
   and stated date conventions; do not claim a mental estimate as verification.
   Confirm the saved HTML equals the tool output and every learner link resolves
   within the pack. Fix packaging paths, not the returned HTML.
   Report counts of saved/re-read files, quote/clause placements checked, date
   and number calculations checked, and anything fixed. If a tool cannot save,
   re-read or calculate, name what is unsaved/unverified instead of claiming success.
10. Confirm saves succeeded and share only links returned by Cowork's tools.
    If saving is unavailable, say the page was rendered but not saved (if true);
    never invent a saved file or link. Offer to zip the complete folder.
    Keep the complete pack for facilitators; share only the guide and learner
    subtree with learners. Folder labels and absent hrefs are not access control.

## Department notes

- **Legal:** deliver a clause-and-notice review note. Quote clauses with sections,
  include a notice/deadline trap and questions for counsel. Test the personal
  skill on a new fictional notice date or revised clause with its own key facts.
- **HR:** deliver a policy-based case and escalation brief, with no real employee
  data and an explicit escalation path. Test a new fictional case or policy date.
- **Finance:** deliver a reconciled variance brief with a variance challenge.
  Test a fresh fictional period with different figures and checked control totals.
- **Sales:** deliver a fictional account plan with a deal-risk challenge.
  Test a new invented account or changed deal figures against fresh expected facts.
- **Operations:** deliver a stock or schedule plan with checked maths and a
  "what-if" challenge. Test different stock, lead-time or capacity inputs.

## Practice-data boundaries

- Use invented companies, role labels, documents and figures only.
- Never put tenant or customer data, real documents, personal information,
  credentials or secrets in the spec. Ask for fictional requirements instead.
- List source and checkpoint files honestly. A file entry is not a created
  workbook; provide links only to practice files that actually exist.
- The service checks and renders content. Cowork handles saving with the
  learner's permission. This is a demo build, not a production deployment.
- The server never creates files, mail or calendar items.
- For legal, HR, compliance, privacy and medical topics, include "practice exercise,
  not professional advice", use fictional parties only, and keep a "questions for
  an expert" step that separates interpretation from plain text.
