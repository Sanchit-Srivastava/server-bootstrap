# ~/.zshrc — managed by server-bootstrap

# SSH forwards TERM, not the client's terminfo database. Unknown xterm variants
# (e.g. xterm-ghostty) leave ZLE without cursor-motion capabilities and break
# redraws, especially with highlighting/autosuggestions. Fix this before OMZ.
# Keep known terminals, tmux/screen, dumb and noninteractive shells unchanged.
if [[ -o interactive && "$TERM" == xterm-* ]] && command -v infocmp >/dev/null 2>&1; then
    if ! infocmp -x -- "$TERM" >/dev/null 2>&1 &&
        infocmp -x xterm-256color >/dev/null 2>&1; then
        export TERM=xterm-256color
    fi
fi

export ZSH="${HOME}/.oh-my-zsh"
# Dependency updates are deliberate operator actions, not login side effects.
zstyle ':omz:update' mode disabled
if [[ -f "${ZSH}/oh-my-zsh.sh" ]]; then
    plugins=(
        git
        sudo
        zsh-autosuggestions
        zsh-syntax-highlighting
        fzf-tab
    )
    ZSH_THEME="afowler"
    source "${ZSH}/oh-my-zsh.sh"
else
    print -ru2 -- "[zshrc] oh-my-zsh is missing; run: just dotfiles"
fi

HISTFILE="${XDG_STATE_HOME:-$HOME/.local/state}/zsh/history"
HISTSIZE=100000
SAVEHIST=100000
mkdir -p "$(dirname "$HISTFILE")"
setopt HIST_IGNORE_DUPS SHARE_HISTORY EXTENDED_HISTORY HIST_EXPIRE_DUPS_FIRST HIST_IGNORE_SPACE

if command -v fzf >/dev/null 2>&1; then
    [[ -f /usr/share/doc/fzf/examples/key-bindings.zsh ]] && source /usr/share/doc/fzf/examples/key-bindings.zsh
    [[ -f /usr/share/doc/fzf/examples/completion.zsh ]] && source /usr/share/doc/fzf/examples/completion.zsh
    export FZF_DEFAULT_OPTS="--height 40% --layout=reverse --border"
    export FZF_DEFAULT_COMMAND='fd --type f --hidden --follow --exclude .git'
    export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND"
    zstyle ':fzf-tab:*' fzf-flags --height=40% --layout=reverse --border
fi

if command -v zoxide >/dev/null 2>&1; then
    eval "$(zoxide init zsh)"
fi

if command -v bat >/dev/null 2>&1; then
    alias cat='bat --style=plain'
elif command -v batcat >/dev/null 2>&1; then
    alias cat='batcat --style=plain'
fi

if command -v eza >/dev/null 2>&1; then
    alias ls='eza --group-directories-first --icons=auto'
    alias ll='eza -la --group-directories-first --icons=auto'
    alias la='eza -a --group-directories-first --icons=auto'
    alias lt='eza --tree --level=2 --icons=auto'
fi

command -v rg >/dev/null 2>&1 && alias grep='rg'
command -v fd >/dev/null 2>&1 && alias find='fd'
command -v lazygit >/dev/null 2>&1 && alias lg='lazygit'

alias g='git'
alias gs='git status'
alias ga='git add'
alias gc='git commit'
alias gp='git push'
alias gl='git pull'
alias gd='git diff'
alias gco='git checkout'
alias gcb='git checkout -b'
alias glog='git log --oneline --graph --decorate'

alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias please='sudo'
alias df='df -h'
alias update='sudo apt-get update && sudo apt-get upgrade'
alias server-bootstrap-sync='cd ~/server-bootstrap && just sync'

export SESSIONIZER_DIRS="${SESSIONIZER_DIRS:-$HOME/Projects:$HOME/services}"
if command -v tmux >/dev/null 2>&1; then
    x() {
        ~/bin/tmux-sessionizer "${1:-}"
    }
    xc() {
        x "$PWD"
    }
    xa() {
        if [[ -n "${1:-}" ]]; then
            tmux attach-session -t "$1"
        else
            local session
            session="$(tmux list-sessions -F '#S' 2>/dev/null | fzf --prompt='attach: ')" &&
                tmux attach-session -t "$session"
        fi
    }
    alias xl='tmux ls'
fi

zstyle ':completion:*' menu select
zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}'

[[ -f "${HOME}/.zshrc.local" ]] && source "${HOME}/.zshrc.local"

if [[ -o interactive ]] && command -v fastfetch >/dev/null 2>&1; then
    command fastfetch
fi
