# OpenTalon

An agentic coding assistant powered by free LLMs via OpenRouter. Run natural-language coding tasks from your terminal — OpenTalon plans, executes tool calls, and iterates until the task is done.

## What it does

```bash
opentaion effort "list all Python files and find any unused imports"
```

```
  ◆ Model: nvidia/nemotron-3-super-120b-a12b:free (low tier)
  ◆ run_command(command='find . -type f -name "*.py"')
  ◆ read_file(path='src/opentaion/agent.py')
  ...
✓ Task complete.  Tokens: 8,421  |  Cost: $0.0000
```

## Quick Start

### 1. Sign up

Go to your OpenTalon web dashboard → enter your email → click the magic link → you're in.

### 2. Generate an API key

Dashboard → **API Keys** → **Generate Key** → copy the key (shown once).

### 3. Install the CLI

```bash
# Clone the repo and install locally
git clone https://github.com/Miao-tech/opentaion.git
cd opentaion/cli
uv run python -m opentaion login
```

Enter your Railway API URL and the API key you just generated.

### 4. Run a task

```bash
uv run python -m opentaion effort "fix the type errors in auth.py"
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `opentaion login` | Configure the proxy URL and API key |
| `opentaion effort "<task>"` | Run an agentic coding task |
| `opentaion --version` | Show version |
| `opentaion --help` | Show help |

## Links

- [Full User & Deployment Guide](docs/guide.md)
- [Running OpenTalon Locally](docs/local-deployment.md)
- [Using OpenTalon with Opencode](docs/opencode-integration.md)
- [Web Dashboard](https://opentaion.vercel.app)
