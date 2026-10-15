# AI Prompt Log

## Setup — Context and Data

### Prompts

- “ok working on HW 5 - use the HW5 folder”
- “Campus Customs Multi-Agent Operations. setting the context first, we'll work thru the actual problems one at a time so dont start building the whole thing yet lol. we're making an agent team that runs the shop. tickets land on a board for things like customer orders, rent, unpaid bills, discount requests, etc. there are three connected pieces: an MCP server, a FastAPI backend with the multi-agent team, and a React dashboard where a human can watch what's happening and approve requests. […] make a working copy at data/campus_customs_new.db and point the MCP server and backend there. […] for every agent, use ONLY gpt-6-luna through Portkey with PORTKEY_API_KEY. […] for now just get familiar with this setup and flag any questions, then i'll give you the first problem.” (supplied `data.zip` attached)

### Follow-up prompts

- “gpt 6. and by standard stuff i meant venv, go find my API, that stuff” — the first pass flagged a model-name mismatch and set up the data, but hadn't created the project `.venv` or wired up the Portkey key yet.

## Problem 1 — Vibe Coder Prompts

### Prompts

- “ok standard stuff. Problem 1: Vibe coder prompts. create AI_prompts.md now and keep it updated as we work thru the assignment. this should log the actual prompts I send you, with one section per problem. each section needs: the problem number and title; at least one prompt I typed, keeping my actual wording as much as possible; a follow-up prompt if we needed one, plus a sentence explaining what was missing after the first attempt. include this prompt in the Problem 1 section too. dont invent follow-ups if we didnt need them lol. we'll tackle each problem individually as I send it over. any q's before we get going?”

### Follow-up prompts

None needed.

## Problem 2 — Study the Campus Customs Database

### Prompts

- “ok now we're working on Problem 2: Study the Campus Customs database. open data/campus_customs.db and look thru every table and its fields so we understand what we're working with. copy the original to data/campus_customs_new.db for the later problems to update, keeping the original untouched. also study the three open tickets and how they connect to the other tables. lets get familiar with the situation before we start trying to solve everything lol. start output/harness.md. for each table, list its fields and add one short line explaining why that table matters for the agents. we'll keep building on this file in the later problems.”

### Follow-up prompts

None needed.

## Problem 3 — Build the MCP Server

### Prompts

- “good context - keep that in mind! ok now we're working on Problem 3: Build the MCP server. write an MCP server in mcp_server/ using FastMCP, pointed at data/campus_customs_new.db. we dont need to connect or run it for this problem yet. every agent will use the tools in this server, and we'll add more later. for now, pick and write three tools that we'll need based on the actual tickets you studied. give them clear names and only use info from the database, no making stuff up lol. in output/harness.md, list all three tools. for each one, explain which table(s) it reads, which ticket it helps unlock (101, 102, or 103), and one sentence on why it's the right tool for that ticket. be specific about the connection to the ticket, not just "reads inventory." also add a short mcp_server/README.md explaining what the server is for, which database file it uses, and the three tools it has. lmk if anything unclear”

### Follow-up prompts

None needed.

## Problem 4 — Add the MCP Server to Vibe Coder and Test Each Tool

### Prompts

- “nice. good stuff. ok now we're working on Problem 4: Add the MCP server to vibe coder and test each tool. connect the MCP server we built to this project so you can actually call its tools. save the connection JSON in .mcp.json at the project root, or the equivalent local config your setup uses. once connected, test all three tools through that MCP connection. save the actual evidence in output/mcp_smoke.json. for each tool, include: the prompt used to ask you to call it; the tool name; the actual tool output, which needs to match the values in data/campus_customs_new.db. no made up test results lol. if you need me to restart the session or do something to enable the connection, walk me thru it.”

### Follow-up prompts

- “ok restarted and approved campus-customs - go run the smoke test” — after the first attempt, `.mcp.json` was written and the server booted, but the session had loaded its tools before the file existed, so the campus-customs tools weren't available yet.
- (New session opened in the Homework 5 folder) “Problem 4 smoke test: .mcp.json and mcp_server/ are already built (see AI_prompts.md and output/harness.md for context). Call all three campus-customs MCP tools: check_stock_shortfall(CC-HOOD-NAVY, M, 20), get_invoice_status(501), get_rent_status(1). Verify each output against data/campus_customs_new.db with sqlite3, then save output/mcp_smoke.json with the prompt, tool name, and actual output for each. Log Problem 4 in AI_prompts.md (prompt + the follow-up that the first session was rooted in the wrong folder).” — the restart still didn't load the server, because the original session was rooted in the class folder and `.mcp.json` is only read from the session's root folder.
- “ok done - try it now” — back in the original session, to check the results the new session saved.

## Problem 5 — Build the Agent Team and Grow the MCP Tools

### Prompts

- “ok now we're working on Problem 5: Build the agent team and grow the MCP tools. time to give everyone a job lol. build the five agents using PydanticAI: Boss, Inventory, Accounting, Facilities, and Customer Service. include prompts, models, and agent loops with full connectivity, meaning any agent can delegate to any other agent for help. put one prompt file per agent in backend/prompts/, the data types in backend/models.py, and the agent files under backend/. layout can vary as long as the five roles are clear. every agent must use ONLY gpt-6-luna through Portkey with PORTKEY_API_KEY. here's what I want in the agent prompts. flesh these out into detailed instructions covering each agent's work, scope, tools, and relevant shop rules. shared rules for everyone: [get shop facts through MCP / desk.date_today / delegate with clear question and context / payments need human approval / no contacting real people, drafts only / distinguish proposed, awaiting approval, completed, blocked / preserve original DB, no incoming revenue]. Boss: [...] Inventory: [...] Accounting: [...] Facilities: [...] Customer Service: [...] add whatever tools these agents need to the MCP server so they can work on the open tickets. all shop lookups and updates must go through MCP, dont build a separate shop-tools layer that bypasses it. enforce payment approval and cash checks in the tools too. have the agents append to output/audit_trail.json as they run. record enough for each agent-loop step to audit who did what, which ticket it concerned, delegations, tool calls / results, and how the step ended. keep existing entries between runs. update output/harness.md with every agent and MCP tool, including which table(s) each tool uses. add a short safety section covering customer privacy, human control over money, safe database updates, and limits on loops / delegation / tokens so the agents dont yap forever lol. also update mcp_server/README.md to match the expanded tool list, and keep AI_prompts.md updated. anything you need clarified before getting started?” (full per-agent instructions abbreviated here; they're implemented in `backend/prompts/`)

### Follow-up prompts

None needed.

## Problem 6 — Plan the Three Tickets

### Prompts

- “nice! no perpetual yapping lol. ok now we're working on Problem 6: Plan the three tickets. before wiring the backend, lets write down what we expect the team to do for each open ticket. build output/desk_tickets.html as a page I can double click to open, with one tab each for tickets 101, 102, and 103. add Cash and Reflection tabs too, but leave those blank or put a quick "coming later" note for now. for each ticket, fill in an Expected section and leave room for an Actual section we'll fill after running the agents. base the plan on the ticket details and database info we've already studied. in each Expected section, explain: who Boss should call first and why; all the delegations we expect, including which agent asks which other agent for help and what they need; which MCP tools we expect the run to use. make the plan specific to each ticket. dont just have Boss call everyone for everything lol, only involve the specialists who actually have a role in resolving it. we'll compare these plans with what the agents really do later.”

### Follow-up prompts

None needed.

## Problem 7 — Backend Routes

### Prompts

- “looks awesoem. ok now we're working on Problem 7: Backend routes. use FastAPI in backend/main.py to build the routes our React dashboard will call in the next problem. we need routes that: return the three tickets and whether each is open or resolved; take a ticket ID and run the agent team on that ticket; return recent agent events, including what each agent said and which tools they used, so the board can refresh; approve a payment or purchase after a human clicks approve. agents only prepare the payment; this approval route is what actually changes cash; return the current checking balance from cash_accounts; reset the working database to the original values so we can try a fresh run. keep shop lookups and updates going through MCP, and preserve the approval / insufficient cash rules we already set up. the reset should restore data/campus_customs_new.db from the untouched original. start the server from the backend/ folder using: uvicorn main --reload --port 8000. that should make the backend available at http://localhost:8000 for the dashboard. in output/harness.md, list each route with its URL and a one-line explanation of what it does. keep AI_prompts.md updated too. any questions before wiring this up?”

### Follow-up prompts

None needed. (The start command was adjusted to `uvicorn main:app --reload --port 8000`, since uvicorn needs the `module:app` form.)

## Problem 8 — Agent Dashboard

### Prompts

- “swag. ok now we're working on Problem 8: Agent dashboard. build the dashboard in frontend/ using React + Vite + TypeScript, connected to the backend routes from Problem 7. aesthetic direction: steampunk. like monocles and engines type of beat. picturing brass / copper, dark wood, cream paper, mechanical gauges, and some gears or steam animations. make it feel like a Victorian shop operations desk, but keep the text and controls easy to use. the dashboard needs to: list all three tickets with their status; let me select one ticket and start the agent team on it; show each agent and what they're saying / doing while it runs, including tool activity and delegations; mark the ticket resolved when the run successfully finishes, using the actual backend status; show a short summary of what each agent did on that ticket; let a human approve a payment or purchase when requested; show the checking balance and refresh it after approved payments so we can see it drop. give each agent a distinct look so it's easy to follow who's doing what. maybe Boss gets a monocle, Inventory has crates / gears, Accounting gets a ledger, Facilities has an engine / wrench, and Customer Service has a little telegraph setup. subtle animation while an agent is active could be fun. make the ticket list, live activity, and approval requests easy to find. cash could be shown on a brass instrument-style display with the actual dollar amount clearly readable. resolved tickets should get an obvious completed stamp. all the activity and numbers should come from the backend. have the frontend call http://localhost:8000 and configure backend CORS to allow the Vite origin, usually http://localhost:5173. start the dashboard from frontend/ with: npm run dev. write output/design.md explaining the layout and aesthetic choices, how we distinguish the agents, how resolved tickets and cash are displayed, and why the design makes this something a human would actually enjoy using. lmk any q's”

### Follow-up prompts

None needed from the user. While testing live, a re-run of #102 after the rent was paid came back *blocked* instead of resolved: real-clock timestamps and the advanced lease due date confused the agents. That was fixed in the MCP tools and prompts within this problem, and the re-test resolved correctly.

## Problem 9 — Resolve the Tickets

### Prompts

- “crusher behavior. ok now we're working on Problem 9: Resolve the tickets. reset data/campus_customs_new.db to the original values before starting the full run, and record the starting checking balance. then run tickets 101, 102, and 103 through the React board until each is resolved. keep the human approval requirement for payments / purchases, so pause for me to approve those on the dashboard. in output/desk_tickets.html, fill in each ticket's Actual section using what really happened in this run: which agents worked on it, what they delegated and to whom, and which tools they used. preserve the Expected sections so we can compare. fill in the Cash tab with: starting checking balance after the reset; cash changes for each ticket, including which payment / purchase caused the change, the dollar amount, and why; ending checking balance, which must match cash_accounts in the working database. pls reconcile the cash math against the actual payment records. if a ticket didnt change cash, say that and explain why. also save: output/resolved_tickets.json with each ticket's ID, final status, short outcome, each agent's contribution, and any human approvals; output/resolved_board.html as a page I can double click to open, with an actual screenshot of the React board for each resolved ticket. append the real run activity to output/audit_trail.json, keeping the existing history. finish output/harness.md so it covers the tables, MCP tools, all five agents, API routes, dashboard, and safety rules. dont fill in successful outcomes or screenshots unless they actually happened. if something breaks, fix it and rerun as needed, resetting before a fresh full run and making clear which run the final evidence comes from.”

### Follow-up prompts

- “approved the $840 invoice 501 payment on the dashboard - continue” and “approved the $8 tee PO on the dashboard - continue”: approvals during the first attempt.
- “bruh what's going on” / “i mean this feels like it's taking too long, no?”: the first attempt was slow and broke. A Portkey call hung for about 10 minutes (no timeout was set); the agents couldn't see that a paid PO meant the order was placed; and running the test suite reset the real working DB mid-run. After fixing all three:
- “yes start a fresh full run - I'll approve as requests come in”: the clean final run (reset `38bfa3fe471c`). All three tickets resolved, ending at $152.
- “looks like 102 is resolved from the dashboard?” / “are you almost done”: progress check-ins during the final run.

## Problem 10 — Reflection

### Prompts

- “ok now we're working on Problem 10: Reflection. use the evidence review we just did to fill the Reflection tab in output/desk_tickets.html. log THIS prompt as Problem 10 in AI_prompts.md. write it in my voice, thoughtful and specific but not overly formal. be detailed enough to answer all five questions, and tie the answers to the ticket tabs, Cash tab, and actual run evidence. dont include technical run IDs or computer-generated labels in the reflection. just refer to the final run or earlier debugging attempts. here are my takes to develop: 1. how did the agents perform on each ticket? [#101: dependency spotted, approvals worked, clunky coordination with nine repeated calls and a second run; on order ≠ received. #102: correct financial outcome but two runs, duplicated resolve, Boss timeout; DB success ≠ agent-run success. speed: ~4 min and ~7 min runs, ~10 min hung call during earlier debugging; don't over-attribute causes. #103: strongest coordination; 8 at 5% off without spending $264 of $152; a quote, not a sale.] 2. how did Actual compare with Expected? [#101 extra $8 PO and rerun, explain the rush-reprint assumption; #102 Boss did the Accounting hand-off, CS drafted landlord notes; #103 same chain but resolved vs blocked after the rule change, $152 vs $160.] 3. what would have been simpler with one agent and tools? [#102 17 calls / ~55k tokens with a repeated rent lookup; #101 repeated lookups; five runs / ~282k tokens; #103 roles useful; role tool access, but approval and cash checks could be enforced single-agent too; don't claim untested numbers.] 4. three new problems the existing team / tools could handle [Crest Mug PO via Elm City Gifts with the 43 mugs / $150.50 ceiling; next rent on lease 1 vs $152; bulk cap quote.] 5. three problems the current tools couldnt solve, and what we'd need [completing a sale; receiving the tee delivery plus admin shop-date advance; real email / vendor ordering plus ticket creation.] use the Cash tab as evidence: $3,400 starting cash, minus $840 and $8 for #101, minus $2,400 for #102, and no cash change for #103, leaving $152. before finalizing, verify the reported tee arrival date and shop-date chronology, and check the screenshot before repeating the claim that #102 has no Boss report line. the $3,400 starting balance was hard-coded in resolved_tickets.json but matches the reset evidence; dont describe it as a live database read. flag any uncertainty you cant resolve. dont rerun the agents or change the final database for this reflection. use the final run evidence and keep it honest about both the strengths and limitations.” (bracketed parts condensed from the full prompt)

### Follow-up prompts

None needed. (The evidence review just before this, “ok we're gathering context before Problem 10…”, was explicitly a prep request and isn't logged as a problem.)

## Problem 11 — Submit to GitHub

### Prompts

- “ok now we're working on Problem 11: Submit to GitHub. here's the public repo I created: https://github.com/dw565/ai-hw-5-dw.git prepare the final hw5 submission and push it there. make sure the hw5 folder includes: AI_prompts.md, requirements.txt, .env.example, .gitignore, .mcp.json, and README.md; data/campus_customs.db AND data/campus_customs_new.db. include both databases in git, with the original untouched and the working copy preserving our final results; mcp_server/server.py and mcp_server/README.md; frontend/ with the React app; backend/ with main.py, models.py, the agent implementation files, and prompts/ containing boss.md, inventory.md, accounting.md, facilities.md, and customer_service.md; output/ with harness.md,”

### Follow-up prompts

None needed.
