---
name: build-demo-pack
description: "Build a demo pack or demo prompt pack, prepare a Cowork demo for <customer>, or set up a Copilot demo with fictional Office inputs, checked payoffs, and a presenter guide."
license: MIT
metadata:
  author: Cowork Training Studio
  version: "0.1.4"
---

# Build a demo pack

Skills own judgment; the MCP owns consistency. Cowork's own tools create assets
with permission. The server never creates files, mail, calendar items or chats.
Use the connector's tool names EXACTLY as listed, including any prefixes.
The logical names below identify those tools; never guess a tool name.
If a required capability is missing, report the blocker, not invented success.

## Agree inputs in one round

1. Call `list_session_formats` and choose `demo_pack`. Ask once for missing inputs:
   - Customer name and HTTPS website, both optional; default: no named customer.
   - Mode: `function_pack` by default, covering HR, Finance, Marketing and Sales;
     or `prompt_pack` from a pasted prompt, which must be kept verbatim.
     If none is pasted, offer a clearly labelled fictional procurement default.
   - Presenter name (optional, conversation only) and role (default: facilitator).
   - Length (default: 20 minutes) and seeded items (default: none).
   State the defaults and proceed with them for unanswered optional choices;
   never stall on repeated preference rounds. Never invent permissions or sources.
   Put only the role in `presenter.role`, never the presenter's real name or address.
   Use the first three ASCII letters of the customer name, ignoring spaces and
   nonletters, uppercased, as `audience.prefix`; without a customer use `DEM`.
   If a name cannot yield three letters, explain the constraint rather than
   inventing a prefix that fails validation. Choose a wholly fictional stand-in.

## Research and draft the plan

2. With available web tools, research public customer context, never tenant data.
   Keep `context.facts` separate from `context.assumptions`; every fact needs a
   verified HTTPS `source_url`. If no sources can be found, use assumptions only
   and disclose the limitation. Never invent citations or turn guesses into facts.
   Omit an unverified website. Without a customer, use fictional assumptions.
3. Call `get_demo_pack_schema` and draft the returned DemoPackSpec 1.0 contract.
   Set `as_of_date` explicitly and `default_minutes` to the agreed duration.
   For `prompt_pack`, retain `source_prompt` verbatim; label any agreed default.
   Plan input files and payoffs first; finish every input before producing the
   prompt pack or outputs, never in parallel. Draft prompts may name planned
   inputs, but do not run them against missing or partially written files.
   Work backwards from each deliverable to typed `payoffs[].evidence`, with its
   `evidence_file_id`, `scenario_id`, `source_file` and clause `section` when needed.
   Use six to nine fictional cast members, including an executive and an external
   party; three to five dated tensions, at least one slipping; and two buried payoffs.
   Make sources slightly disagree on purpose, with a specific, evidenced resolution.
   Every scenario references its inputs and payoffs, has two follow-ups and a
   150-300 word talk track. Function packs default to four distinct functions and
   each scenario requests .xlsx, .docx, .pptx and .html outputs.
   All function-pack input and output filenames start with `<PREFIX>_`.
   Run-of-show minutes must sum exactly to `default_minutes`.
   State "All people and data are fictional." Add "Real customer names are used
   only as context." when `audience.customer_name` is present.
   For sensitive domains, include "practice exercise, not professional advice",
   fictional-party wording and questions for an expert that separate interpretation
   from plain source text. Keep cleanup steps in `cleanup` for the returned README.
   Call `validate_demo_pack`; fix EVERY error and warning and repeat until 0/0.
   If a warning cannot be resolved, explain the blocker; never hide or waive it.
4. The operating company in ALL data is a fictional stand-in, not the customer
   with "(demo data)" appended. Invent every person, record, figure and document.
   The real customer name belongs only in audience fields, the pack title, talk
   tracks and filename prefix; do not repeat it in fictional records or context prose.
   Never pass real documents, personal details, mailbox identifiers or secrets
   to the server. Public source URLs are metadata, not imported tenant records.

## Build, render and save

5. After clean validation and permission to save, build every input with Cowork's
   own file tools. Use real .xlsx for tables/figures and .docx for briefs/notes;
   use real .pptx only when slides are an input. Never substitute Markdown, CSV
   or renamed text files for these Office assets. README.md is pack metadata,
   not a demo input, and is the required Markdown exception.
   Plant each payoff in its declared file, matching typed evidence word for word,
   with the exact clause section, numbers and dates. Build sources from the
   canonical evidence, not the other way round. Finish inputs before the prompt pack.
   Keep IDs and filenames consistent with the spec; do not fabricate saved links.
6. Only after the input saves succeed, set attendee `files[].href` to the real
   relative `files/<filename>` path and `audience: "attendee"`. Presenter files
   have `audience: "presenter"` and no href. Revalidate the complete spec to 0/0.
   Call `render_demo_guide` with that same spec. If it returns errors, fix and
   revalidate before retrying. Save its EXACT `html` using the returned `filename`
   and its EXACT `readme_md` as `README.md`; do not retype, summarize or reconstruct
   either value. Preserve the HTML's inline styles, scripts and relative links.
7. Use `<PREFIX>-demo-pack/` as the pack folder, with:
   - The returned guide HTML and `README.md` at the root, for the presenter only.
   - `files/` for the shareable inputs the demo opens.
   - `presenter/` for any other presenter-only files, such as answer notes in .docx.
   Folder labels and absent links are NOT access control: share `files/` only.
   Never share the guide, README, payoffs or full ZIP as attendee materials.
   Presenter notes are collapsed in the guide, but appear in print.

## Verify, optionally seed and hand off

8. Re-read EVERY saved file, including Office contents, guide HTML and README.
   Use code to check every payoff exists in its declared file and every number,
   calculation, date and clause section matches the spec. Verify deliberate
   discrepancies against their own declared facts; do not erase planted findings.
   Check every file link resolves to a saved file inside `files/`, with no
   presenter-only links. Confirm saved HTML/README equal the returned strings.
   Fix the source file to match canonical evidence; re-read and recheck it.
   If paths or metadata change, validate again and re-render, never patch HTML.
   Report counts of saved/re-read files, payoffs, calculations/dates and links
   checked, plus fixes. If tools cannot create Office files, re-read or execute
   checks, report exactly what remains unbuilt/unverified; never claim completion.
9. Seeded items are optional and off by default. Allow only email or meeting
   items in the presenter's OWN mailbox/calendar, and only after explicit
   confirmation of the planned subjects, bodies, counts and computed dates.
   Compute dates from `as_of_date` plus `day_offset` with code; keep within 30 days,
   at most eight emails and five meetings. Copy each body's exact first label line
   from the validated spec; keep the authenticated sender unchanged, never spoof it.
   Prefer own-mailbox drafts; never send to anyone else or invite other attendees.
   Never create Teams chats or relay across users. If tools cannot guarantee
   self-only scope, leave items unseeded and say so. Use only Cowork's own tools,
   never the MCP server. The exact returned README must list cleanup steps;
   remove only presenter-owned demo items explicitly created with permission.
10. Confirm saves and checks, offer to zip the complete pack folder for the
    presenter, and share only links returned by the file tools. If saving or
    zipping is unavailable, state that clearly; do not invent a file or link.

Credit: Shailesh Mittal (master prompt) and Giovanna [LAST NAME] (cowork-demo-pack skill).
