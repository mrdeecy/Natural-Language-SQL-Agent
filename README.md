# Natural-Language SQL Agent

This project builds a small read-only SQL agent for the Pagila sample database using LangGraph and a human-review loop.

## Setup

1. Create a Python environment with uv:
   - `uv sync`
2. Copy the example env file:
   - `cp .env.example .env`
3. Fill in the values for your local environment.
4. Create the Postgres role and grant read-only access:
   - `psql -d pagila -f db/setup_readonly_role.sql`
5. Verify the role cannot write:
   - `python db/verify_readonly.py`

## Supabase setup

Supabase provides PostgreSQL, so the agent does not need a separate Supabase SDK.

1. Create a Supabase project and copy its Postgres connection string from **Connect**.
   Use the direct connection or session pooler URL and keep `sslmode=require`.
2. Set `SUPABASE_DB_URL` in `.env` or Streamlit deployment secrets. Do not commit it,
   because the URL contains the database password.
3. Load the existing Pagila schema and data into Supabase:

   ```bash
   uv run python db/migrate_pagila_to_supabase.py
   ```

   The command reads `paglia/1. pagila-schema.sql` and `paglia/2. pagila-insert-data.sql`,
   removes local-owner statements that Supabase cannot use, and prints verification counts.
   If a previous run stopped partway through, rerun it with `--reset` to recreate the
   `public` schema before loading the complete dump:

   ```bash
   uv run python db/migrate_pagila_to_supabase.py --reset
   ```

   Use `--reset` only when the schema contains this application's Pagila objects; it removes
   everything in the Supabase `public` schema before reloading.

4. Create a dedicated read-only login in Supabase SQL Editor and grant it access to the
   `public` schema. Set `SUPABASE_DB_URL` to that role's connection string for the running agent.
5. Start the app with `uv run streamlit run app.py` and run a known Pagila question.

`SUPABASE_DB_URL` takes precedence over `DATABASE_URL`, so local development continues to
use the local database when the Supabase variable is absent.

## Streamlit Community Cloud deployment

The deployed app uses Streamlit for its UI and connects directly to Supabase Postgres. A
separate API is not required for this application.

1. Push the `agent_sql` directory to a GitHub repository.
2. In Streamlit Community Cloud, create an app using `app.py` as the main file.
3. Select Python 3.12, which matches the supported range in `pyproject.toml`.
4. Add the following values under the app's **Secrets** settings:

   ```toml
   OPENAI_API_KEY = "..."
   SUPABASE_DB_URL = "postgresql://sql_agent:...@.../postgres?sslmode=require"
   CHAT_MODEL = "gpt-4o-mini"
   CONFIDENCE_THRESHOLD = "0.75"
   MAX_RETRIES = "3"
   ADMIN_EMAILS = "reviewer@example.com"
   ```

   `SUPABASE_DB_URL` must use the dedicated read-only application role. Never use the
   privileged connection string used by the migration script.

5. Configure Google OpenID Connect in the same Secrets editor. Register the deployed
   app's OAuth callback URL with Google, then add:

   ```toml
   [auth]
   redirect_uri = "https://YOUR_APP.streamlit.app/oauth2callback"
   cookie_secret = "generate-a-long-random-value"
   client_id = "...apps.googleusercontent.com"
   client_secret = "..."
   server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
   ```

6. Redeploy and verify that unauthenticated visitors see only the sign-in screen and that
   only addresses in `ADMIN_EMAILS` can approve or reject SQL.

The current review state is held in process memory. This is suitable for a single-instance
demo, but pending reviews can be lost after an app restart and are not a durable shared queue.

## Schema slice

The agent reasons over a condensed Pagila schema centered on:

- film
- customer
- rental
- payment
- inventory
- store
- staff
- actor
- category
- film_category
- film_actor

## Confidence scoring

The generation node asks the model for structured JSON with:

- `sql`
- `confidence` in the range 0..1
- `reasoning`

The score is intentionally conservative when the question is ambiguous, requires a complex join, or follows a failed retry. This is a lightweight uncertainty signal rather than a calibrated measure of correctness.

## Environment variables

| Key                  | Purpose                                                     |
| -------------------- | ----------------------------------------------------------- |
| OPENAI_API_KEY       | LLM access for real model calls                             |
| CHAT_MODEL           | Default model name                                          |
| CONFIDENCE_THRESHOLD | Gate for automatic SQL execution                            |
| MAX_RETRIES          | Retry cap before giving up                                  |
| DATABASE_URL         | Local Postgres DSN for the read-only role                   |
| SUPABASE_DB_URL      | Supabase Postgres DSN; takes precedence over `DATABASE_URL` |
| LANGCHAIN_TRACING_V2 | Enable LangSmith tracing                                    |
| LANGCHAIN_API_KEY    | LangSmith API key                                           |
| LANGCHAIN_PROJECT    | LangSmith project name                                      |
| ADMIN_EMAILS         | Comma-separated Google accounts allowed to review SQL       |

## Run instructions

```bash
cd agent_sql
uv sync
cp .env.example .env
uv run python src/run_agent.py
uv run python eval/run_eval.py
```

## Known limitations

- The confidence score is self-reported and not calibrated against ground truth.
- The agent is intentionally read-only; write questions are refused.
- The schema slice is fixed and not dynamically introspected in all cases.
- The live Supabase migration requires a configured project connection string.
- Human-review state uses in-process memory and is not durable across restarts.
- Google OIDC authentication is required for the public Streamlit deployment.

## Demo

No demo recording is included in this workspace yet.
