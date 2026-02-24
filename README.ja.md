# Secure Agent Launcher

[![Tests](https://github.com/mark0011astra/Secure-Agent-Launcher/actions/workflows/check.yml/badge.svg)](https://github.com/mark0011astra/Secure-Agent-Launcher/actions/workflows/check.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Secure Agent Launcher は、`codex`、`claude`、`gemini` などの AI エージェント CLI を実行するときに、機密パスへのアクセスを実行前に止める macOS 向けツールです。

English README: [README.md](README.md)

## これができる

- AIに触られたくないパスをリストに登録できる
- AIがコマンドを実行する前にパスを検査し、該当する場合は実行をブロックする
- ブロック/実行の判定を監査ログへ残す
- GUI で設定して エージェント起動コマンドを 1 行でコマンドを設定できる

## 初めての方向け: 最短 3 ステップ

1. インストール

```bash
brew install mark0011astra/Secure-Agent-Launcher/secure-agent-locker
```

2. GUI 起動

```bash
secure-agent-locker gui
```

3. 画面でパスを追加し、`Generate Run Command` で生成されたコマンドをターミナルで実行

ブロックされた場合は、実行結果に `blocked_path:` が表示されます。

## 利用環境

- macOS
- `bash`、`curl`、`tar`
- Homebrew（Homebrewで導入する場合）

## インストール

### Homebrew でインストール（推奨）

```bash
brew install mark0011astra/Secure-Agent-Launcher/secure-agent-locker
```

先に tap して導入する場合:

```bash
brew tap mark0011astra/Secure-Agent-Launcher
brew install secure-agent-locker
```

### GitHub Release からインストール

```bash
curl -fsSL https://raw.githubusercontent.com/mark0011astra/Secure-Agent-Launcher/main/scripts/install-from-github.sh \
  | bash -s -- --repo mark0011astra/Secure-Agent-Launcher
```

インストール先:

- `~/.local/bin/secure-agent-locker`
- `~/.local/bin/secure-agent-locker-uninstall`

必要に応じて `~/.local/bin` を `PATH` に追加してください。

特定のタグを指定してインストールする場合:

```bash
bash scripts/install-from-github.sh --repo mark0011astra/Secure-Agent-Launcher --tag v0.1.0
```

### ソースからローカルインストールする場合（Python が必要）

```bash
./scripts/install.sh
```

## アンインストール

```bash
secure-agent-locker-uninstall
```

ポリシーと監査ログも削除する場合:

```bash
secure-agent-locker-uninstall --purge-config
```

Homebrew で導入した場合:

```bash
brew uninstall secure-agent-locker
```

## ファイル配置

- Policy JSON: `~/.config/secure-agent-locker/policy.json`
- Audit log: `~/.local/state/secure-agent-locker/audit.log`
- Audit lock file: `~/.local/state/secure-agent-locker/audit.log.lock`
- ローテート済みログ: `audit.log.1` から `audit.log.3`（約2MBでローテーション開始）

## クイックスタート（GUI）

```bash
secure-agent-locker gui
```

1. 左側の `AI Access Deny List` に保護したいパスを追加します。
2. 右側でエージェントコマンドと作業フォルダを指定します。
3. `Generate Run Command` をクリックします。
4. 生成された1行コマンドを任意のターミナルで実行します。

補足:

- GUI は外部ターミナルを自動起動しません。
- 生成コマンドは、利用可能な場合は `secure-agent-locker` コマンドを使用します。
- 事前チェックでブロック対象パスが検出された場合、コマンド生成は停止します。
- GUI は固定サイズで動作し、フルスクリーン操作は無効化されます。

## CLI の使い方

デフォルトポリシーを初期化:

```bash
secure-agent-locker init
```

現在のポリシー JSON を表示:

```bash
secure-agent-locker show
```

deny paths の管理:

```bash
secure-agent-locker policy list
secure-agent-locker policy add ~/.ssh ~/.aws
secure-agent-locker policy remove ~/.aws
secure-agent-locker policy status
secure-agent-locker policy on
secure-agent-locker policy off
```

ドライラン（チェックのみ）:

```bash
secure-agent-locker run -- codex
```

実行:

```bash
secure-agent-locker run --execute -- codex
```

作業ディレクトリを明示する場合:

```bash
secure-agent-locker run --execute --cwd ~/work/project -- codex --model gpt-5
```

## 動作仕様

- `run` は `deny_paths` とコマンド内のパスを照合します。
- 一致した場合は終了コード `25` でブロックします。
- `--execute` なしの `run` はドライランです。
- `--timeout-sec` は正の整数のみ受け付けます。
- `AGENT_LOCKER_TEST_MODE=1` の場合、終了コード `26` で実行を止めます。
- すべての実行判定は監査ログへ追記されます。

## GitHub でのリリース運用

GitHub でタグ付きリリースを公開すると、`.github/workflows/release-macos.yml` が次のアセットを自動生成して添付します。

- `secure-agent-locker-macos-arm64.tar.gz`
- `secure-agent-locker-macos-x64.tar.gz`

利用者は `scripts/install-from-github.sh` を使って、Python なしで導入できます。

## 開発環境のセットアップ（Python）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## テスト実行

```bash
python3 -m unittest discover -s tests -v
```

## ライセンス

MIT License。詳細は [LICENSE](LICENSE) を参照してください。
