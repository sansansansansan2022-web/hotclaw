# Account operations MVP

One account is a durable workspace, not a one-off generation request. Manual runs and scheduled runs enter the same account task pipeline. The schedule only triggers a run; it does not make editorial decisions.

## Runtime roles

1. **Account Ops (manager)** reads the account plan, approved articles, recent tasks and review backlog. It records a short retrospective, proposes next topic directions, decides whether this run may proceed, and hands its strategy to the specialists.
2. **Profile** turns the account positioning into a usable editorial profile.
3. **Research** collects current signals and source evidence, guided by the manager's directions.
4. **Planner** selects a distinct topic and title, avoiding recent approved topics.
5. **Writer** produces the draft using approved article memory as style context. If review finds fixable issues, it may revise once.
6. **Audit** checks the draft and any revision. Its final result is the quality gate.

Formatting, draft storage, account memory lookup, and run status are services. Approved or published drafts are the memory source of truth; no separate memory table is needed for this version. Publishing remains an explicit later action.

The flow stays code-orchestrated and inspectable. The manager decides topic direction and run posture; the workflow enforces the five specialist steps, one revision at most, and human draft confirmation. This follows the current guidance to choose code orchestration for predictable paths and persist state at meaningful boundaries ([OpenAI Agents SDK](https://openai.github.io/openai-agents-python/multi_agent/), [LangGraph](https://docs.langchain.com/oss/javascript/langgraph/thinking-in-langgraph)). Adding another workflow framework would duplicate HotClaw's existing task and node persistence for this MVP.

## Acceptance loop

Create an account, run it manually, review and approve a real draft, then run it again and verify that the second run uses the first approved article and avoids repeating its topic. Configure a schedule for the same account and verify that a due run enters the same pipeline and leaves a draft for review. A fresh Windows install must migrate an empty SQLite database and start both backend and frontend.

## Windows start

From the repository root in PowerShell:

```powershell
cd backend
python -m pip install -e .
Copy-Item .env.example .env
# Edit backend/.env and set DEEPSEEK_API_KEY to a working key.
cd ../frontend
npm ci
npm run build
cd ..
.\scripts\start-local.ps1
```

Open `http://127.0.0.1:3460/accounts`. The script migrates SQLite and starts the backend with account scheduling enabled. To stop it, run `.\scripts\stop-local.ps1`.
