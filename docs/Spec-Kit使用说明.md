# Spec Kit 安装与使用说明

## 已完成的安装与初始化

- **uv / uvx** 已安装到 `~/.local/bin`。若终端中执行 `uvx` 提示找不到命令，请将 `export PATH="$HOME/.local/bin:$PATH"` 加入 `~/.zshrc` 或 `~/.bashrc` 并重新打开终端。
- **Spec Kit init 已完成**：项目内已生成 `.specify/`（memory、scripts、templates）与 `.github/agents`、`.github/prompts`（GitHub Copilot 用）。
- **Cursor 中的 Slash 命令**：init 时使用的是 `--ai copilot`，因此默认只生成了 Copilot 用的 `.github/agents/`，**Cursor 不会自动识别该目录**。已在本项目中为 Cursor 单独生成 **`.cursor/commands/`**，并把 Spec Kit 的 9 个命令（如 `/speckit.specify`、`/speckit.plan`）复制为 `.cursor/commands/speckit.*.md`。在 Cursor 聊天框输入 `/` 即可看到并选择这些命令。

## 若需在其他目录重新初始化（`specify init`）

在项目根目录执行：

```bash
cd /Users/yangjiaxing/Coding/CursorProject/stock-assistant
uvx --from git+https://github.com/github/spec-kit.git specify init .
```

本机 init 已通过「从克隆的 spec-kit 仓库用 `uv run specify init . --no-git --ai copilot --script sh --ignore-agent-tools`」完成。若你在其他机器或新项目执行 `uvx ... specify init .` 时报错 **`realpath: command not found`**（常见于 macOS），可按以下方式处理。

### 方式一：安装 GNU coreutils（推荐）

```bash
brew install coreutils
export PATH="/opt/homebrew/opt/coreutils/libexec/gnubin:$PATH"   # Apple Silicon
# 或
export PATH="/usr/local/opt/coreutils/libexec/gnubin:$PATH"      # Intel Mac
```

再将对应的 `export` 行写入 `~/.zshrc`，然后重新打开终端，在项目根目录重新执行 `specify init .`。

### 方式二：不执行 init，仅用 Slash 流程

Spec Kit 的核心是「先写规格再实现」的流程，不依赖 init 也能在 Cursor 里用：

1. 在对话里用自然语言描述要做的功能。
2. 按顺序使用（若你的 Cursor 已配置相应 Slash 命令）：  
   `/speckit.constitution` → `/speckit.specify` → `/speckit.clarify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`  
   若没有这些命令，可直接要求 AI：「按 Spec Kit 流程：先写 constitution，再写 specify，再 plan，再 tasks，再 implement。」
3. 项目下已预留 `.specify/` 目录，init 成功后其中会生成自动化脚本（`.sh` / `.ps1`）。

## 命令行子命令（如 `specify check`）

Spec Kit CLI 除 `init` 外还有 **`check`**（检查 git、AI 助手、VS Code 等是否就绪）、**`version`** 等。若直接运行 `specify check` 提示“没有这个命令”，多半是当前 PATH 里的 `specify` 并非完整 Spec Kit CLI（例如通过 `uvx` 临时运行时的包装脚本在 macOS 上不完整）。

**推荐用法**（与 init 一致，从仓库用 uv 跑完整 CLI）：

```bash
# 若已有克隆的 spec-kit（如 /tmp/spec-kit-ref）
uv run --project /tmp/spec-kit-ref specify check

# 或先克隆再执行
git clone --depth 1 https://github.com/github/spec-kit.git /tmp/spec-kit-ref
uv run --project /tmp/spec-kit-ref specify check
```

**可选**：安装为全局命令后可直接打 `specify check`：

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
# 确保 uv 的 tool 目录在 PATH 中，然后：
specify check
specify --help
```

## 参考链接

- [Spec Kit 官方文档](https://github.github.io/spec-kit/)
- [Quick Start](https://github.github.io/spec-kit/quickstart.html)
- [GitHub 仓库](https://github.com/github/spec-kit)
