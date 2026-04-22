@echo off
wsl -d Ubuntu-22.04 -- bash -c "cd /home/gerivdb/appflowy-mcp-server && exec python3 src/appflowy_mcp.py"
