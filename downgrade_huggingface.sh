#!/bin/bash

# This script downgrade the huggingface_hub to a version that still has cached_download

# Show the current version
echo "Current huggingface_hub version:"
pip show huggingface_hub | grep Version

# Uninstall current version
echo -e "\nUninstalling current version..."
pip uninstall -y huggingface_hub

# Install version 0.11.0 which still has cached_download
echo -e "\nInstalling huggingface_hub 0.11.0..."
pip install huggingface_hub==0.11.0

# Show the installed version
echo -e "\nNew huggingface_hub version:"
pip show huggingface_hub | grep Version

echo -e "\nDowngrade complete! Try running your bot now:"
echo "python main.py"