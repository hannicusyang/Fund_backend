"""
cat > ~/.openclaw/openclaw.json << 'EOF'
{
  "gateway": {
    "mode": "local"
  },
  "agents": {
    "defaults": {
      "model": {
        "primary": "self/claude-opus-4-5-20251101"
      },
      "models": {
        "self/claude-opus-4-5-20251101": {
          "alias": "claude"
        }
      }
    }
  },
  "models": {
    "providers": {
      "self": {
        "baseUrl": "https://cursor.scihub.edu.kg/api",
        "apiKey": "cr_9c959b7540fd1e99f4a2555073c6f411919b345a88fca17726b6df11c9435485",
        "api": "anthropic-messages",
        "models": [
          {
            "id": "claude-opus-4-5-20251101",
            "name": "Claude Opus 4.5 Custom"
          }
        ]
      }
    }
  }
}
EOF
"""