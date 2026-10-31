# A pass counts only when the reviewer clears every finding exactly once.

demo_approved

printf '\n== findings must each be cleared ==\n'
desktop='printf "[Desktop Entry]\n" > launcher.desktop'
case_uncleared 'unanswered' "$desktop" 'F1 not addressed' STUB_CLEAR=none
case_uncleared 'confirmed' "$desktop" 'F1 confirmed by the reviewer' STUB_CONFIRM=F1
case_uncleared 'unknown-finding' "$desktop" 'unknown finding F9' 'STUB_EXTRA=F9 CLEARED made up'
case_uncleared 'answered-twice' "$desktop" 'F1 answered more than once' 'STUB_EXTRA=F1 CLEARED again'
case_uncleared 'no-reason' "$desktop" 'F1 cleared without a reason' STUB_CLEAR=none 'STUB_EXTRA=F1 CLEARED'
case_uncleared 'partly-cleared' "$desktop && printf \"x\\n\" > other.desktop" 'F2 not addressed' STUB_CLEAR=F1
case_uncleared 'reviewer-fail' "$desktop" 'stub reviewer disliked' STUB_VERDICT=FAIL

base=$(ap)
reset_upstream "$base"
commit_upstream "$desktop" 'bulleted answer'
STUB_CLEAR=none STUB_EXTRA='- F1 CLEARED a launcher entry, nothing runs it' "$GATE" check >/dev/null 2>&1
eq 'bulleted clearance accepted' "$(ap)" "$(upstream_sha)"
has "$(vdir)cleared" 'cleared: a launcher entry' 'reviewer reason kept'
