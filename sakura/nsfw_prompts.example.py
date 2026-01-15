"""NSFW prompts template for Sakura.

HOW TO USE:
1. Copy this file to nsfw_prompts.py (same directory)
2. Customize the prompts below with your preferred content
3. nsfw_prompts.py is gitignored and will stay local

The prompts use Danbooru-style tags for NoobAI XL compatibility.
"""

# Emotion-specific NSFW prompts
# Customize each emotion with your preferred explicit tags
NSFW_EMOTION_PROMPTS = {
    "happy": "your prompt here",
    "sad": "your prompt here",
    "angry": "your prompt here",
    "surprised": "your prompt here",
    "shy": "your prompt here",
    "thinking": "your prompt here",
    "excited": "your prompt here",
    "tired": "your prompt here",
    "confused": "your prompt here",
    "neutral": "your prompt here",
    "love": "your prompt here",
    "worried": "your prompt here",
    "proud": "your prompt here",
    "playful": "your prompt here",
}

# Base character prompt (prepended to all emotion prompts)
# Include quality tags and character description
NSFW_CHARACTER_PROMPT = (
    "masterpiece, best quality, newest, absurdres, highres, "
    "1girl, solo, pink hair, twintails, blue eyes, maid headdress, "
    "your tags here"
)

# Negative prompt to avoid unwanted elements
NSFW_NEGATIVE_PROMPT = (
    "worst quality, old, early, low quality, lowres, signature, username, logo, "
    "bad hands, mutated hands, bad anatomy, extra limbs, missing fingers, "
    "blurry, your negative tags here"
)
