
#!/usr/bin/env python

"""
Run the bot with huggingface_hub patching enabled.
"""

# Apply the patch first - before ANYTHING else is imported
import patch_huggingface

# Now import and run the main function
from src.bot import main

if __name__ == "__main__":
    main()