
#!/usr/bin/env python

# Apply monkey patch first
import huggingface_monkey_patch

# Then run the bot
from src.bot import main

if __name__ == "__main__":
    main()
