#!/bin/sh
# Claude Code statusLine script
# Format: daily:1.6% | ctx:17% | $1.95 | Opus 4.6

input=$(cat)

# Extract fields from JSON input
model_id=$(echo "$input" | jq -r '.model.id // ""')
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
total_in=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
total_out=$(echo "$input" | jq -r '.context_window.total_output_tokens // 0')
cache_write=$(echo "$input" | jq -r '.context_window.current_usage.cache_creation_input_tokens // 0')
cache_read=$(echo "$input" | jq -r '.context_window.current_usage.cache_read_input_tokens // 0')

# --- Short model name: strip "Claude " prefix ---
model_display=$(echo "$input" | jq -r '.model.display_name // ""')
model_short=$(echo "$model_display" | sed 's/^Claude //')

# --- Daily usage percentage ---
# Approximated against a configurable daily input-token budget (default: 1,000,000).
# Set CLAUDE_DAILY_BUDGET_TOKENS in your environment to override.
DAILY_BUDGET_TOKENS="${CLAUDE_DAILY_BUDGET_TOKENS:-1000000}"
daily_pct=$(awk -v used="$total_in" -v budget="$DAILY_BUDGET_TOKENS" \
  'BEGIN { pct = used / budget * 100; if (pct > 100) pct = 100; printf "%.1f", pct }')

# --- Context usage ---
ctx_pct="${used_pct:-0}"

# --- Estimated session cost ---
# Pricing per million tokens (USD). Defaults to Sonnet 4 rates if model unrecognized.
case "$model_id" in
  *opus-4*)
    price_in="15.00"; price_out="75.00"; price_cache_write="18.75"; price_cache_read="1.50" ;;
  *sonnet-4*)
    price_in="3.00";  price_out="15.00"; price_cache_write="3.75";  price_cache_read="0.30" ;;
  *haiku-3-5*|*haiku-3.5*)
    price_in="0.80";  price_out="4.00";  price_cache_write="1.00";  price_cache_read="0.08" ;;
  *haiku*)
    price_in="0.25";  price_out="1.25";  price_cache_write="0.30";  price_cache_read="0.03" ;;
  *)
    price_in="3.00";  price_out="15.00"; price_cache_write="3.75";  price_cache_read="0.30" ;;
esac

cost=$(awk -v in_tok="$total_in" -v out_tok="$total_out" \
           -v cw_tok="$cache_write" -v cr_tok="$cache_read" \
           -v pi="$price_in" -v po="$price_out" \
           -v pcw="$price_cache_write" -v pcr="$price_cache_read" \
  'BEGIN {
    c = (in_tok/1000000*pi) + (out_tok/1000000*po) \
      + (cw_tok/1000000*pcw) + (cr_tok/1000000*pcr)
    printf "$%.2f", c
  }')

# --- Git branch and changes ---
# Uses cwd from JSON; counts added/untracked (+N) and modified (~N) via porcelain output.
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // ""')
git_segment=""
if [ -n "$cwd" ] && git -C "$cwd" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  branch=$(git -C "$cwd" --no-optional-locks symbolic-ref --short HEAD 2>/dev/null \
           || git -C "$cwd" --no-optional-locks rev-parse --short HEAD 2>/dev/null)
  porcelain=$(git -C "$cwd" --no-optional-locks status --porcelain 2>/dev/null)
  added=$(printf '%s\n' "$porcelain" | grep -c '^[ACRM?]' 2>/dev/null || echo 0)
  modified=$(printf '%s\n' "$porcelain" | grep -c '^ M\|^M \|^ T\|^T ' 2>/dev/null || echo 0)
  git_segment="$branch"
  if [ "$added" -gt 0 ] || [ "$modified" -gt 0 ]; then
    git_segment="${git_segment} +${added}~${modified}"
  fi
fi

# --- Assemble: daily:X% | ctx:Y% | $Z.ZZ | Model | branch +N~N ---
# Colors: magenta=daily, cyan=ctx, green=cost, yellow=model, grey=separators+branch, green=added, yellow=modified
MAGENTA='\033[35m'
CYAN='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
GREY='\033[90m'
RESET='\033[0m'

# Build the git portion with per-token colors if changes exist
git_colored=""
if [ -n "$git_segment" ]; then
  branch_only=$(echo "$git_segment" | awk '{print $1}')
  changes=$(echo "$git_segment" | awk '{print $2}')  # e.g. "+3~2" or ""
  if [ -n "$changes" ]; then
    added_part=$(echo "$changes" | sed 's/~.*//')   # "+3"
    mod_part=$(echo "$changes" | sed 's/+[0-9]*//')  # "~2"
    git_colored="${GREY}${branch_only}${RESET} ${GREEN}${added_part}${RESET}${YELLOW}${mod_part}${RESET}"
  else
    git_colored="${GREY}${branch_only}${RESET}"
  fi
  printf "${MAGENTA}daily:%s%%${RESET} ${GREY}|${RESET} ${CYAN}ctx:%s%%${RESET} ${GREY}|${RESET} ${GREEN}%s${RESET} ${GREY}|${RESET} ${YELLOW}%s${RESET} ${GREY}|${RESET} ${git_colored}\n" \
    "$daily_pct" "$ctx_pct" "$cost" "$model_short"
else
  printf "${MAGENTA}daily:%s%%${RESET} ${GREY}|${RESET} ${CYAN}ctx:%s%%${RESET} ${GREY}|${RESET} ${GREEN}%s${RESET} ${GREY}|${RESET} ${YELLOW}%s${RESET}\n" \
    "$daily_pct" "$ctx_pct" "$cost" "$model_short"
fi
