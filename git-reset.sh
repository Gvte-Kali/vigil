#!/bin/bash
cd /opt/vigil
git fetch origin
git reset --hard origin/main
git log --oneline -1