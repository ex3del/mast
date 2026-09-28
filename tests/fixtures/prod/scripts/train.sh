#!/bin/sh
# Запуск обучения на GPU-сервере
set -e
ssh gpu01 "cd ~/mnist-train && git pull --ff-only && python train.py"
