#!/bin/bash

# This script creates a compatible environment for the bot by fixing all dependencies

echo "Creating a compatible environment for your bot..."

# Step 1: Uninstall conflicting packages
echo -e "\nUninstalling conflicting packages..."
pip uninstall -y huggingface_hub tokenizers transformers sentence-transformers

# Step 2: Install compatible versions in the correct order
echo -e "\nInstalling compatible versions..."
pip install huggingface_hub==0.11.0
pip install tokenizers==0.12.1  # Older version compatible with huggingface_hub 0.11.0
pip install transformers==4.19.2  # Older version compatible with huggingface_hub 0.11.0
pip install sentence-transformers==2.2.2  # Version compatible with transformers 4.19.2

# Step 3: Verify the installations
echo -e "\nVerifying installations:"
pip show huggingface_hub | grep Version
pip show tokenizers | grep Version
pip show transformers | grep Version
pip show sentence-transformers | grep Version

echo -e "\nCompatible environment setup complete!"
echo "Try running your bot now:"
echo "python main.py"