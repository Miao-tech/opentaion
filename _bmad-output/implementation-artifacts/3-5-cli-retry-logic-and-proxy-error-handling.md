# Story 3.5: CLI Retry Logic and Proxy Error Handling

Status: done

## Story

As a developer building OpenTalon,
I want the CLI to automatically retry a failed proxy connection once on the first call and exit cleanly with an actionable error on any unrecoverable failure,
So that transient failures (e.g. Railway cold start) recover automatically and permanent failures fail visibly without leaving partial state.

## Acceptance Criteria

**AC1 — First-call connection error: silent retry:**
Given the very first proxy request in a task fails with a connection error (`httpx.ConnectError`, `httpx.ConnectTimeout`, or `httpx.NetworkError`)
When the CLI detects the failure on iteration 0
Then it silently retries that same request once — no error output on the first attempt (satisfies FR9)

**AC2 — First-call retry succeeds: execution continues normally:**
Given the first call fails but the retry succeeds
When the retry response is received
Then execution continues normally with the agent loop — the user sees only progress bullets and the final cost summary

**AC3 — Both first-call attempts fail: show error and exit 1:**
Given the retry of the first call also fails
When the second connection error occurs
Then the CLI prints to stderr:
```
✗ Proxy unreachable: <proxy_url>
  Could not connect to the OpenTalon API server.
  Check that your Railway deployment is running.

  Run `opentaion login` to update your proxy URL.
```
And exits with code 1 — no cost summary is shown (satisfies FR10, NFR10, UX-DR8)

**AC4 — Mid-loop connection error: fail immediately, no retry:**
Given a connection error occurs on iteration > 0 (after one or more iterations have already completed successfully)
When the error is detected
Then the task fails immediately with the same `✗ Proxy unreachable` error message and exits with code 1 — no retry attempted, no partial cost summary shown (clean failure semantics: the metering contract holds or the command fails)

**AC5 — HTTP 401 at any point: auth error, no retry:**
Given the proxy returns HTTP 401 at any point in the loop
When the error is received
Then the CLI prints `✗ Authentication failed: invalid API key. Run \`opentaion login\` to reconfigure.` and exits with code 1 — no retry on auth failures

**AC6 — Tests pass:**
Given tests are run
When `uv run pytest` is executed from `cli/`
Then tests pass for: retry on first-call failure + success, both first-call attempts fail (exit 1, message), mid-loop connection error fails immediately without retry, no retry on 401

## Tasks / Subtasks

- [x] Task 1: Write tests FIRST in `tests/test_effort.py` — add new section for retry tests (TDD)
  - [x] Tests for AC1–AC5 all fail before modifications to `effort.py`

- [x] Task 2: Add `_call_proxy_request()` helper to `effort.py` (AC: 1, 2, 3, 4, 5)
  - [x] Single HTTP POST to the proxy — no retry logic inside
  - [x] Raises exceptions as-is (caller handles retry and error routing)

- [x] Task 3: Modify `_run_agent_loop()` in `effort.py` (AC: 1–5)
  - [x] Wrap iteration 0 call with first-call retry logic
  - [x] Handle `httpx.ConnectError` / `httpx.ConnectTimeout` / `httpx.NetworkError` → `_show_proxy_error()` + `sys.exit(1)`
  - [x] Handle `httpx.HTTPStatusError` with status 401 → `_show_auth_error()` + `sys.exit(1)`
  - [x] Mid-loop errors (iteration > 0): same proxy error, no retry

- [x] Task 4: Run tests green (AC: 6)
  - [x] `uv run pytest tests/test_effort.py -v`
  - [x] `uv run pytest` — full CLI suite passes

## Dev Notes

### Prerequisite: Story 3.4 Must Be Complete

`cli/src/opentaion/commands/effort.py` must exist with `_run_agent_loop()` (Story 3.4).
This story modifies that file — it does NOT replace it from scratch.

### Modified `effort.py` — New Helpers + Updated Agent Loop

Add these helpers and modify `_run_agent_loop()`. All other Story 3.4 code is unchanged.

```python
# ── Error display helpers ─────────────────────────────────────────────────────

def _show_proxy_error(proxy_url: str) -> None:
    """Print the proxy unreachable error to stderr (UX-DR8 ErrorLine format)."""
    err_console.print(f"[bold red]✗ Proxy unreachable: {proxy_url}[/bold red]")
    err_console.print("[dim]  Could not connect to the OpenTalon API server.[/dim]")
    err_console.print("[dim]  Check that your Railway deployment is running.[/dim]")
    err_console.print("")
    err_console.print("  Run [cyan]`opentaion login`[/cyan] to update your proxy URL.")


def _show_auth_error() -> None:
    """Print the 401 auth error to stderr."""
    err_console.print(
        "[bold red]✗ Authentication failed: invalid API key.[/bold red]"
    )
    err_console.print(
        "  Run [cyan]`opentaion login`[/cyan] to reconfigure."
    )


# ── Single proxy request (no retry) ──────────────────────────────────────────

async def _call_proxy_request(
    client: httpx.AsyncClient,
    proxy_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
) -> dict:
    """Make one POST to the proxy. Raises on any failure — caller handles retry."""
    response = await client.post(
        f"{proxy_url}/v1/chat/completions",
        json={
            "model": model,
            "messages": messages,
            "tools": TOOLS,
        },
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    response.raise_for_status()
    return response.json()
```

### Updated `_run_agent_loop()` — Full Function

Replace the Story 3.4 version with this:

```python
async def _run_agent_loop(proxy_url: str, api_key: str, tier: str, prompt: str) -> None:
    """Multi-turn agent loop with retry on first call and clean error handling."""
    model = EFFORT_MODELS[tier]
    console.print(f"[dim]  ◆ Model: {model} ({tier} tier)[/dim]")

    messages: list[dict] = [{"role": "user", "content": prompt}]
    total_prompt_tokens = 0
    total_completion_tokens = 0

    async with httpx.AsyncClient(timeout=PROXY_TIMEOUT) as client:
        for iteration in range(MAX_ITERATIONS):
            try:
                if iteration == 0:
                    # First call: one silent retry on connection failure (FR9)
                    try:
                        data = await _call_proxy_request(client, proxy_url, api_key, model, messages)
                    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError):
                        # Silent first failure — retry once
                        data = await _call_proxy_request(client, proxy_url, api_key, model, messages)
                        # If retry also fails, the exception propagates to outer handler
                else:
                    # Mid-loop: no retry (clean failure semantics — metering contract)
                    data = await _call_proxy_request(client, proxy_url, api_key, model, messages)

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    _show_auth_error()
                else:
                    _show_proxy_error(proxy_url)
                sys.exit(1)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError):
                _show_proxy_error(proxy_url)
                sys.exit(1)

            # Accumulate token counts
            usage = data.get("usage", {})
            total_prompt_tokens += int(usage.get("prompt_tokens", 0))
            total_completion_tokens += int(usage.get("completion_tokens", 0))

            # Extract the assistant's message
            choices = data.get("choices", [])
            if not choices:
                break
            message = choices[0].get("message", {})

            # Check for termination: no tool_calls = final answer
            tool_calls = message.get("tool_calls")
            if not tool_calls:
                break  # natural termination

            # Append assistant message (with tool_calls) to conversation
            messages.append(message)

            # Execute each tool call and collect results
            for tool_call in tool_calls:
                tool_name = tool_call["function"]["name"]
                try:
                    tool_args = json.loads(tool_call["function"]["arguments"])
                except (json.JSONDecodeError, KeyError):
                    tool_args = {}

                console.print(f"[dim]  ◆ {tool_name}({_args_summary(tool_args)})[/dim]")
                result = _execute_tool(tool_name, tool_args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result,
                })
        else:
            console.print("[dim]  ◆ Max iterations reached. Stopping.[/dim]")

    # Cost summary (only reached on clean completion — sys.exit(1) skips this)
    total_tokens = total_prompt_tokens + total_completion_tokens
    cost = _compute_cost(model, total_prompt_tokens, total_completion_tokens)
    console.print(
        f"[bold]✓ Task complete.[/bold]  "
        f"[dim]Tokens: {total_tokens:,}[/dim]  "
        f"[dim]|[/dim]  "
        f"[bold cyan]Cost: ${cost:.4f}[/bold cyan]"
    )
```

### Why Only the First Call Gets a Retry

The retry is asymmetric by design:
- **First call only:** Railway free tier has cold starts (~30s). The first request after a period of inactivity may fail as the dyno wakes. One retry handles this transparently.
- **Mid-loop calls:** If iteration 2 fails, the task has already consumed tokens and partially modified the developer's files. Retrying mid-loop could create ambiguous state (did the LLM's last tool call write a file? Was the DB log written?). **Clean failure is safer than partial recovery.** The developer can re-run the task cleanly.

This is the "metering contract" mentioned in the architecture: "The metering contract must hold or the command must fail visibly."

### Why No Retry on 401

HTTP 401 from the proxy means the stored `api_key` is invalid or revoked. Retrying doesn't change this — the user must run `opentaion login` with a new key. Retrying would:
1. Delay the error by 5s (wasted time)
2. Create confusion about what happened
3. Potentially trigger rate limiting on repeated invalid auth attempts

### NFR10 Trade-off: "Within 5 Seconds" vs Two 5-Second Connect Timeouts

NFR10 says: "exit within 5 seconds of a proxy connection failure, after one retry attempt."

With `PROXY_TIMEOUT = httpx.Timeout(connect=5.0, read=120.0)`, two connection attempts can take up to 10 seconds total (5s + 5s). This is a known trade-off:
- The architecture explicitly specifies `connect=5.0` per attempt
- The "5 seconds" in NFR10 describes the failure-to-exit response time (how quickly the error appears after the FINAL failure), not the total elapsed time
- After the retry fails, `_show_proxy_error()` + `sys.exit(1)` execute immediately — there is no additional 5-second wait

If the Railway deployment is completely unreachable, the user will wait up to ~10 seconds before seeing the error. This is documented as the expected behavior for Railway cold start detection.

### Connection Error Types to Catch

```python
except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError):
```

- `httpx.ConnectError` — TCP connection refused, DNS resolution failure, host unreachable
- `httpx.ConnectTimeout` — connect phase exceeded `connect=5.0` timeout
- `httpx.NetworkError` — base class for various low-level network failures

Do NOT catch `httpx.ReadTimeout` here — a read timeout means the proxy connected but OpenRouter is taking too long. This is a different failure mode (should surface as a separate error in a future story, not a proxy unreachable message).

### Tests to Add to `tests/test_effort.py`

Add this section after the existing Story 3.4 tests:

```python
# ── Retry logic tests ─────────────────────────────────────────────────────────

def test_retry_first_call_success_on_retry(tmp_config):
    """First call raises ConnectError, retry succeeds → task completes normally."""
    call_count = [0]

    async def fake_post(url, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise httpx.ConnectError("Connection refused")
        # Second call succeeds
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=make_proxy_response(tool_calls=None))
        return mock_resp

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=fake_post)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, ["effort", "low", "hello"])

    assert result.exit_code == 0, result.output
    assert "✓ Task complete." in result.output
    assert call_count[0] == 2  # first attempt + one retry


def test_retry_first_call_no_output_on_first_failure(tmp_config):
    """First call fails silently — no error output on first attempt."""
    call_count = [0]

    async def fake_post(url, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise httpx.ConnectError("Connection refused")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value=make_proxy_response(tool_calls=None))
        return mock_resp

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=fake_post)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, ["effort", "low", "hello"])

    # No "unreachable" error in stdout (success path)
    assert "unreachable" not in result.output.lower()


def test_both_first_call_attempts_fail_exits_1(tmp_config):
    """Both first-call attempts fail → exit code 1."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, ["effort", "low", "hello"])

    assert result.exit_code == 1


def test_both_first_call_attempts_fail_no_cost_summary(tmp_config):
    """On double failure, no cost summary is shown."""
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, ["effort", "low", "hello"])

    assert "✓ Task complete." not in result.output


def test_both_first_call_attempts_fail_exactly_two_calls(tmp_config):
    """Verify exactly 2 calls made (original + one retry), not more."""
    call_count = [0]

    async def counting_post(url, **kwargs):
        call_count[0] += 1
        raise httpx.ConnectError("Connection refused")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=counting_post)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner(mix_stderr=False)
        runner.invoke(main, ["effort", "low", "hello"])

    assert call_count[0] == 2  # exactly original + one retry, not more


def test_mid_loop_connection_error_exits_1(tmp_config, tmp_path):
    """Connection error on iteration 1 (mid-loop) → exit 1, no retry."""
    test_file = tmp_path / "utils.py"
    test_file.write_text("def add(a, b): return a + b\n")

    call_count = [0]

    async def fake_post(url, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # First call succeeds (with tool call)
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json = MagicMock(return_value=make_proxy_response(
                tool_calls=[make_tool_call("read_file", {"path": str(test_file)})],
            ))
            return mock_resp
        # Second call (iteration 1) fails — mid-loop
        raise httpx.ConnectError("Connection dropped")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=fake_post)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, ["effort", "low", "read utils.py"])

    assert result.exit_code == 1


def test_mid_loop_connection_error_no_retry(tmp_config, tmp_path):
    """Mid-loop failure: exactly 2 calls total (iteration 0 success + iteration 1 fail, no retry)."""
    test_file = tmp_path / "utils.py"
    test_file.write_text("def add(a, b): return a + b\n")

    call_count = [0]

    async def fake_post(url, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            mock_resp = MagicMock()
            mock_resp.raise_for_status = MagicMock()
            mock_resp.json = MagicMock(return_value=make_proxy_response(
                tool_calls=[make_tool_call("read_file", {"path": str(test_file)})],
            ))
            return mock_resp
        raise httpx.ConnectError("Connection dropped")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=fake_post)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner(mix_stderr=False)
        runner.invoke(main, ["effort", "low", "read utils.py"])

    # 2 calls: iteration 0 (success) + iteration 1 (fail, no retry = only 1 attempt)
    assert call_count[0] == 2


def test_http_401_exits_1(tmp_config):
    """HTTP 401 response → exit 1, no retry."""
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=mock_response,
        )
    )

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(main, ["effort", "low", "hello"])

    assert result.exit_code == 1


def test_http_401_no_retry(tmp_config):
    """HTTP 401: exactly 1 call (no retry on auth failures)."""
    call_count = [0]
    mock_response = MagicMock()
    mock_response.status_code = 401

    async def counting_post(url, **kwargs):
        call_count[0] += 1
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "401 Unauthorized",
                request=MagicMock(),
                response=mock_response,
            )
        )
        return mock_response

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=counting_post)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("opentaion.commands.effort.httpx.AsyncClient", return_value=mock_client):
        runner = CliRunner(mix_stderr=False)
        runner.invoke(main, ["effort", "low", "hello"])

    assert call_count[0] == 1  # no retry — only one attempt
```

### `httpx.HTTPStatusError` Mock Pattern

`httpx.HTTPStatusError` requires both `request` and `response` kwargs:

```python
httpx.HTTPStatusError(
    "message",
    request=MagicMock(),   # httpx.Request mock
    response=mock_response,  # must have .status_code attribute
)
```

The `raise_for_status()` mock must return a `side_effect` that raises this exception — not just be set to `MagicMock()` (which returns without raising):

```python
mock_response.raise_for_status = MagicMock(
    side_effect=httpx.HTTPStatusError("401", request=MagicMock(), response=mock_response)
)
```

### Architecture Cross-References

From `architecture.md`:
- CLI exits with code 1 on proxy failure — no silent fallbacks [Source: architecture.md#Cross-Cutting Concerns]
- `httpx.Timeout(connect=5.0, read=120.0)` — same timeout for retry [Source: architecture.md#Gaps Resolved]
- Single retry mechanism for Railway cold start [Source: architecture.md#Technical Constraints]

From `epics.md`:
- FR9: "The CLI automatically retries a failed proxy connection once before reporting failure" [Source: epics.md#FR9]
- FR10: "The CLI exits with a non-zero status code and an actionable error message when the proxy is unreachable after the retry" [Source: epics.md#FR10]
- NFR10: "The CLI must surface a deterministic error message and exit within 5 seconds of a proxy connection failure, after one retry attempt" [Source: epics.md#NFR10]
- UX-DR8: `ErrorLine` format: `[bold red]✗ {title}[/bold red]` + dimmed detail + cyan recovery command [Source: epics.md#UX-DR8]

### What This Story Does NOT Include

- Retry on mid-loop failures — clean failure semantics only
- Retry on HTTP errors other than connection failures (e.g. 429, 500) — fail immediately
- Exponential backoff — single retry only
- Timeout adjustment for the retry attempt — same `PROXY_TIMEOUT` as the original call
- Any API changes — this is CLI-only

### Final Modified Files

```
cli/
└── src/opentaion/
    └── commands/
        └── effort.py    ← MODIFIED — add _show_proxy_error(), _show_auth_error(),
                           _call_proxy_request(), updated _run_agent_loop()
tests/
└── test_effort.py       ← MODIFIED — add retry logic test section
```

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

- Story spec uses `CliRunner(mix_stderr=False)` but Click 8.3.1 doesn't support `mix_stderr` param — used `CliRunner()` throughout
- With default CliRunner (mix_stderr=True), stderr from `err_console` is merged into `result.output` — tests checking exit_code only still validate correctly

### Completion Notes List

- TDD red: 1 test failed (retry logic not yet implemented), 5 already passed (correct exit code 1 for unimplemented paths)
- Added `_show_proxy_error()`, `_show_auth_error()`, `_call_proxy_request()` helpers to `effort.py`
- Replaced `_run_agent_loop()` inline request with `_call_proxy_request()` + nested try/except for first-call retry
- 9 new retry tests; 24/24 effort tests pass; 56/56 full suite passes

### File List

- `cli/src/opentaion/commands/effort.py` — MODIFIED: added error helpers, `_call_proxy_request()`, updated `_run_agent_loop()` with retry logic
- `cli/tests/test_effort.py` — MODIFIED: added 9 retry logic tests
