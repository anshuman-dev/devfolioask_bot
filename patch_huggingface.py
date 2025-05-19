"""
Aggressive monkey patch for huggingface_hub to handle cached_download deprecation.
This must be imported before any other imports that use huggingface_hub.
"""

import sys
import os

# Add a custom importer to the meta_path
class HuggingFacePathFinder:
    def find_spec(self, fullname, path, target=None):
        # Only intercept huggingface_hub imports
        if fullname == 'huggingface_hub' or fullname.startswith('huggingface_hub.'):
            # Let Python find the actual module
            import importlib.util
            import importlib.machinery
            
            # Find the actual spec
            if path is None:
                path = sys.path
            for entry in path:
                if os.path.isdir(os.path.join(entry, 'huggingface_hub')):
                    # Found the module directory
                    filename = os.path.join(entry, 'huggingface_hub', '__init__.py')
                    if os.path.exists(filename):
                        # Create a spec for the module
                        spec = importlib.machinery.ModuleSpec(
                            name=fullname,
                            loader=importlib.machinery.SourceFileLoader(fullname, filename),
                            origin=filename
                        )
                        return spec
                        
            return None
        return None

    def get_code(self, fullname):
        return None

    def get_source(self, fullname):
        return None

# Add our finder to the beginning of the meta_path
sys.meta_path.insert(0, HuggingFacePathFinder())

# Now import and patch huggingface_hub
import importlib
huggingface_hub = importlib.import_module('huggingface_hub')

# Make sure hf_hub_download is available and add it as cached_download
if hasattr(huggingface_hub, 'hf_hub_download') and not hasattr(huggingface_hub, 'cached_download'):
    print("🔧 Patching huggingface_hub.cached_download")
    huggingface_hub.cached_download = huggingface_hub.hf_hub_download
    # Make the function accessible via the module's namespace
    sys.modules['huggingface_hub'].cached_download = huggingface_hub.hf_hub_download

print("✅ huggingface_hub patched successfully")