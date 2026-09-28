#!/usr/bin/env bash
# Installs a `barca-intelligence` command that starts the app from any folder.
#
#   make install-command     # creates ~/.local/bin/barca-intelligence
#   make uninstall-command   # removes it again
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$HOME/.local/bin"
TARGET="$BIN/barca-intelligence"

if [ "${1:-}" = "--uninstall" ]; then
  rm -f "$TARGET"
  echo "Removed $TARGET"
  exit 0
fi

mkdir -p "$BIN"
cat > "$TARGET" <<EOF
#!/usr/bin/env bash
# Starts Barça Intelligence (installed by \`make install-command\`).
ROOT="$ROOT"
if [ ! -f "\$ROOT/scripts/start.sh" ]; then
  echo "Barça Intelligence is no longer at \$ROOT. Run \\\`make install-command\\\` in its new folder." >&2
  exit 1
fi
exec bash "\$ROOT/scripts/start.sh"
EOF
chmod +x "$TARGET"
echo "Installed $TARGET -> $ROOT"

# Make sure the folder is on PATH for new terminals.
case ":$PATH:" in
  *":$BIN:"*) on_path=1 ;;
  *) on_path=0 ;;
esac
if [ "$on_path" = 0 ]; then
  case "${SHELL:-}" in
    */zsh) rc="$HOME/.zshrc" ;;
    */bash) rc="$HOME/.bash_profile" ;;
    *) rc="" ;;
  esac
  line='export PATH="$HOME/.local/bin:$PATH"'
  if [ -n "$rc" ]; then
    if ! grep -qsF "$line" "$rc"; then
      printf '\n# personal commands (added by barca-intelligence make install-command)\n%s\n' "$line" >> "$rc"
      echo "Added ~/.local/bin to PATH in $rc"
    fi
    echo "Open a new terminal (or run: source $rc), then type: barca-intelligence"
  else
    echo "Add this line to your shell's startup file, then open a new terminal:"
    echo "  $line"
  fi
else
  echo "Type: barca-intelligence"
fi
