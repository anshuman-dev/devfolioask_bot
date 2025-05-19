
# Compatibility module for cached_download
from huggingface_hub import hf_hub_download

def cached_download(*args, **kwargs):
    """
    Compatibility wrapper for cached_download that forwards to hf_hub_download.
    """
    print("Using compatibility cached_download -> hf_hub_download")
    return hf_hub_download(*args, **kwargs)
