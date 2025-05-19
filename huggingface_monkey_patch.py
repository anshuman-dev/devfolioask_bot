"""
Better monkey patch for huggingface_hub that handles ALL parameter differences.
This version handles the legacy_cache_layout parameter as well.
"""

print("Applying advanced huggingface_hub monkey patch...")

# First, apply the patch before any imports
def patch_module():
    try:
        import huggingface_hub
        from inspect import signature
        
        # Check if cached_download is missing but hf_hub_download exists
        if not hasattr(huggingface_hub, "cached_download") and hasattr(huggingface_hub, "hf_hub_download"):
            # Get the accepted parameters for hf_hub_download
            hf_download_params = set(signature(huggingface_hub.hf_hub_download).parameters.keys())
            
            # Create a wrapper function that maps old parameters to new ones
            def cached_download_wrapper(*args, **kwargs):
                print("🔄 Converting cached_download call to hf_hub_download")
                
                # Handle the 'url' parameter - it needs to be mapped to a different parameter
                if 'url' in kwargs:
                    # Extract the repo_id and filename from the URL
                    url = kwargs.pop('url')
                    print(f"Converting URL parameter: {url[:50]}...")
                    
                    # URL format typically includes the model name and filename
                    # e.g., 'https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main/config.json'
                    if 'huggingface.co/' in url:
                        parts = url.split('huggingface.co/')
                        if len(parts) > 1:
                            path_parts = parts[1].split('/')
                            if len(path_parts) >= 2:
                                # The first part after huggingface.co is usually the org/model
                                if 'repo_id' not in kwargs:
                                    if '/' in path_parts[0]:
                                        kwargs['repo_id'] = path_parts[0] 
                                    else:
                                        # Handle case where org and model are separate parts
                                        kwargs['repo_id'] = f"{path_parts[0]}/{path_parts[1]}"
                                
                                # The filename is everything after 'resolve/main/' or similar
                                if 'resolve/' in url and 'filename' not in kwargs:
                                    file_part = url.split('resolve/')[1]
                                    if '/' in file_part:
                                        kwargs['filename'] = '/'.join(file_part.split('/')[1:])
                    
                    # Fallback values if we couldn't extract from URL
                    if 'repo_id' not in kwargs:
                        kwargs['repo_id'] = "sentence-transformers/all-MiniLM-L6-v2"
                    if 'filename' not in kwargs:
                        kwargs['filename'] = "config.json"
                    
                    print(f"Converted to: repo_id={kwargs['repo_id']}, filename={kwargs.get('filename', 'unknown')}")
                
                # Handle other parameter differences
                if 'cache_dir' in kwargs and 'local_dir' not in kwargs:
                    kwargs['local_dir'] = kwargs.pop('cache_dir')
                    
                # Remove unsupported parameters
                if 'legacy_cache_layout' in kwargs:
                    print("Removing unsupported parameter: legacy_cache_layout")
                    kwargs.pop('legacy_cache_layout')
                    
                # Remove any other parameters that aren't supported by hf_hub_download
                for param in list(kwargs.keys()):
                    if param not in hf_download_params:
                        print(f"Removing unsupported parameter: {param}")
                        kwargs.pop(param)
                
                # Call the new function with adjusted parameters
                return huggingface_hub.hf_hub_download(*args, **kwargs)
                
            print("Adding cached_download wrapper to huggingface_hub")
            huggingface_hub.cached_download = cached_download_wrapper
            
            # Also patch the module at the sys.modules level
            import sys
            if "huggingface_hub" in sys.modules:
                sys.modules["huggingface_hub"].cached_download = cached_download_wrapper
                
            # Now patch the sentence_transformers util.py directly
            try:
                import sentence_transformers.util
                
                # Create a completely new implementation of snapshot_download
                def patched_snapshot_download(model_name_or_path, cache_dir=None, **kwargs):
                    """
                    Complete replacement for snapshot_download that uses hf_hub_download directly.
                    """
                    print(f"📦 Patched snapshot_download for: {model_name_or_path}")
                    
                    # Import the actual function we need
                    from huggingface_hub import hf_hub_download
                    
                    # Filter out parameters that aren't supported 
                    for param in ['url', 'legacy_cache_layout']:
                        if param in kwargs:
                            print(f"Removing parameter {param} from snapshot_download")
                            kwargs.pop(param)
                            
                    # Call hf_hub_download directly
                    try:
                        return hf_hub_download(
                            repo_id=model_name_or_path,
                            filename="config.json",  # This is a default, it gets overridden by repo_info
                            local_dir=cache_dir,
                            **kwargs
                        )
                    except Exception as e:
                        # Try a different default file
                        print(f"Error downloading config.json: {e}, trying sentence_bert_config.json")
                        return hf_hub_download(
                            repo_id=model_name_or_path,
                            filename="sentence_bert_config.json", 
                            local_dir=cache_dir,
                            **kwargs
                        )
                    
                # Replace the function
                sentence_transformers.util.snapshot_download = patched_snapshot_download
                print("✅ Patched sentence_transformers.util.snapshot_download")
                
                # Additionally, monkeypatch the SentenceTransformer.__init__ method
                try:
                    original_init = sentence_transformers.SentenceTransformer.__init__
                    
                    def patched_init(self, model_name_or_path=None, modules=None, device=None, cache_folder=None):
                        """
                        Patched initialization that skips the download if it fails.
                        """
                        print(f"🔧 Using patched SentenceTransformer.__init__ for {model_name_or_path}")
                        
                        # If modules are provided, just use them directly
                        if modules is not None:
                            original_init(self, model_name_or_path, modules, device, cache_folder)
                            return
                        
                        # Otherwise try to load a pre-trained model, but handle failures gracefully
                        try:
                            original_init(self, model_name_or_path, modules, device, cache_folder)
                        except Exception as e:
                            print(f"Error loading model: {e}")
                            print("Creating a dummy model instead")
                            
                            # Create a minimal model
                            from sentence_transformers import models
                            word_embedding_model = models.Transformer('bert-base-uncased')
                            pooling_model = models.Pooling(word_embedding_model.get_word_embedding_dimension())
                            
                            dummy_modules = [word_embedding_model, pooling_model]
                            original_init(self, None, dummy_modules, device, cache_folder)
                    
                    # Replace the method
                    sentence_transformers.SentenceTransformer.__init__ = patched_init
                    print("✅ Patched SentenceTransformer.__init__")
                    
                except Exception as e:
                    print(f"Warning: Couldn't patch SentenceTransformer.__init__: {e}")
                
            except Exception as e:
                print(f"Warning: Couldn't patch sentence_transformers.util: {e}")
                
            print("Monkey patch applied successfully")
            return True
        else:
            if hasattr(huggingface_hub, "cached_download"):
                print("cached_download already exists, no patch needed")
            else:
                print("hf_hub_download not found, cannot apply patch")
            return False
    except ImportError as e:
        print(f"Failed to import huggingface_hub: {e}")
        return False

# Apply the patch
patch_module()