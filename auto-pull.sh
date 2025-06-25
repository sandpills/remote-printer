#!/bin/bash

echo "🔄 Starting auto-pull daemon..."
echo "Press Ctrl+C to stop"

while true; do
  # Check if there are remote changes
  git fetch
  
  LOCAL=$(git rev-parse HEAD)
  REMOTE=$(git rev-parse @{u})
  
  if [ "$LOCAL" != "$REMOTE" ]; then
    echo "📡 New changes found, pulling..."
    git pull
    echo "✅ Pull completed at $(date)"
  else
    echo "✨ Up to date ($(date))"
  fi
  
  sleep 30
done 