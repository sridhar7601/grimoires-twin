#!/usr/bin/env bash
# Grimoires GPU progress — run with:  watch -n 30 bash ~/grimoires_progress.sh
R=~/Documents/grimoires-twin/results
echo "box time $(date +%T)"
echo
echo "== tonight: CCTV renders (6 cameras, fire), then the agent-plan twin run =="
tail -2 ~/cctv_queue.status 2>/dev/null; tail -1 ~/agent_queue.status 2>/dev/null
echo
printf "%-26s %10s %6s   %s\n" "run" "sim time" "of" "progress"
for spec in winner_cctv60s_fire:60 base_cctv120s_fire:120 agent_measure_fire:115; do
  n=${spec%%:*}; dur=${spec##*:}
  f=$R/ira_hospital_$n/agent_positions.jsonl
  if grep -qh "DONE  $n " ~/cctv_queue.status ~/agent_queue.status 2>/dev/null; then
    printf "%-26s %10s %5ss   [####################] done\n" "$n" "" "$dur"
  elif sudo -n test -s "$f"; then
    t=$(sudo -n tail -1 "$f" | grep -o '"t": [0-9.]*' | cut -d' ' -f2)
    pct=$(awk -v t="$t" -v d="$dur" 'BEGIN{p=100*t/d; if(p>100)p=100; printf "%3.0f%%", p}')
    bar=$(awk -v t="$t" -v d="$dur" 'BEGIN{n=int(20*t/d); if(n>20)n=20; s=""; for(i=0;i<n;i++)s=s "#"; for(;i<20;i++)s=s "."; print s}')
    printf "%-26s %9.1fs %5ss   [%s] %s\n" "$n" "$t" "$dur" "$bar" "$pct"
  elif grep -qh "START $n " ~/cctv_queue.status ~/agent_queue.status 2>/dev/null; then
    printf "%-26s %10s %5ss   %s\n" "$n" "-" "$dur" "setting up (NavMesh bake, ~7 min)"
  else
    printf "%-26s %10s %5ss   %s\n" "$n" "-" "$dur" "waiting in queue"
  fi
done
echo
if grep -q "ALL DONE" ~/agent_queue.status 2>/dev/null; then
  echo ">>> ALL DONE - tell Claude <<<"
else
  echo "still running ... (expected finish: CCTV ~00:00 box time, agent run ~00:30)"
fi
