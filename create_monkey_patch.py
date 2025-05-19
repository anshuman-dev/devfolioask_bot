#!/usr/bin/env python

"""
Create a simple monkey patch for huggingface_hub that requires minimal changes.
"""

import sys

def create_patch():
    # Create a simple patch module
    with open("huggingface_monkey_patch.py", "w") as f:
        f.write('''
# This is a simple monkey patch for huggingface_hub
print("Applying huggingface_hub monkey patch...")

# First, apply the patch before any imports
def patch_module():
    try:
        import huggingface_hub
        
        # Check if cached_download is missing but hf_hub_download exists
        if not hasattr(huggingface_hub, "cached_download") and hasattr(huggingface_hub, "hf_hub_download"):
            print("Adding cached_download alias to huggingface_hub")
            huggingface_hub.cached_download = huggingface_hub.hf_hub_download
            
            # Also patch the module at the sys.modules level
            import sys
            if "huggingface_hub" in sys.modules:
                sys.modules["huggingface_hub"].cached_download = huggingface_hub.hf_hub_download
                
            print("Monkey patch applied successfully")
            return True
        else:
            if hasattr(huggingface_hub, "cached_download"):
                print("cached_download already exists, no patch needed")
            else:
                print("hf_hub_download not found, cannot apply patch")
            return False
    except ImportError:
        print("Failed to import huggingface_hub, cannot apply patch")
        return False

# Apply the patch
patch_module()
''')
    
    # Create a runner script that uses the patch
    with open("run_with_monkey_patch.py", "w") as f:
        f.write('''
#!/usr/bin/env python

# Apply monkey patch first
import huggingface_monkey_patch

# Then run the bot
from src.bot import main

if __name__ == "__main__":
    main()
''')
    
    print("Created patch files:")
    print("1. huggingface_monkey_patch.py - The monkey patch module")
    print("2. run_with_monkey_patch.py - Script to run the bot with the patch")
    print("\nRun the bot with:")
    print("python run_with_monkey_patch.py")

if __name__ == "__main__":
    create_patch()