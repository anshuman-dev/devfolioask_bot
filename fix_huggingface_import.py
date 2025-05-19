#!/usr/bin/env python

"""
This script creates a simple compatibility layer for the missing cached_download function.
"""

import importlib
import sys
import os

def create_compatibility_module():
    """Create a compatibility module that provides cached_download."""
    # Create a directory for our compatibility module
    os.makedirs("huggingface_compat", exist_ok=True)
    
    # Create __init__.py
    with open("huggingface_compat/__init__.py", "w") as f:
        f.write("# Huggingface Hub compatibility layer\n")
        
    # Create cached_download.py with the compatibility function
    with open("huggingface_compat/cached_download.py", "w") as f:
        f.write("""
# Compatibility module for cached_download
from huggingface_hub import hf_hub_download

def cached_download(*args, **kwargs):
    \"\"\"
    Compatibility wrapper for cached_download that forwards to hf_hub_download.
    \"\"\"
    print("Using compatibility cached_download -> hf_hub_download")
    return hf_hub_download(*args, **kwargs)
""")
    
    print("Created compatibility module in ./huggingface_compat/")
    
    # Add the current directory to sys.path so the module can be imported
    if "" not in sys.path:
        sys.path.insert(0, "")
    
    return True

def patch_sentence_transformers():
    """Find and patch the SentenceTransformer module."""
    try:
        # First, try to import the module to see where it is
        import sentence_transformers
        module_file = sentence_transformers.__file__
        module_dir = os.path.dirname(module_file)
        
        # Look for SentenceTransformer.py
        st_file = os.path.join(module_dir, "SentenceTransformer.py")
        
        if os.path.exists(st_file):
            print(f"Found SentenceTransformer.py at {st_file}")
            
            # Read the file
            with open(st_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Check if it needs to be patched
            if "from huggingface_hub import" in content and "cached_download" in content:
                print("File contains the problematic import. Patching...")
                
                # Replace the problematic import
                original_import = "from huggingface_hub import HfApi, HfFolder, Repository, hf_hub_url, cached_download"
                new_import = """from huggingface_hub import HfApi, HfFolder, Repository, hf_hub_url
# Patch for cached_download
try:
    from huggingface_hub import cached_download
except ImportError:
    from huggingface_compat.cached_download import cached_download"""
                
                new_content = content.replace(original_import, new_import)
                
                # Write the patched file
                with open(st_file, "w", encoding="utf-8") as f:
                    f.write(new_content)
                
                print("Successfully patched SentenceTransformer.py")
                return True
            else:
                print("File doesn't contain the expected import pattern")
        else:
            print(f"Could not find SentenceTransformer.py in {module_dir}")
    
    except Exception as e:
        print(f"Error patching sentence_transformers: {e}")
    
    return False

if __name__ == "__main__":
    print("Creating compatibility module...")
    create_compatibility_module()
    
    print("\nPatching sentence_transformers...")
    patched = patch_sentence_transformers()
    
    if patched:
        print("\n✅ Patching complete! Try running your bot now:")
        print("python main.py")
    else:
        print("\n⚠️ Could not fully patch the library. Try the downgrade approach.")