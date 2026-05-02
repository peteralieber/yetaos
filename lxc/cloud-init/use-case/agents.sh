# default: Claude CLI and GitHub Copilot CLI installed globally via npm
set -e
npm install -g @anthropic-ai/claude-code
npm install -g @github/copilot-cli

claude --version
github-copilot-cli --version || true
