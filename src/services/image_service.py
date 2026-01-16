"""
Image generation and handling service
"""
import os
import aiohttp
from typing import Optional
from datetime import datetime
from pathlib import Path

from config import settings


class ImageService:
    """Service for handling image generation and sending"""
    
    def __init__(self):
        self.upload_dir = Path("data/uploads")
        self.upload_dir.mkdir(parents=True, exist_ok=True)
    
    async def generate_image(self, prompt: str, user_id: int) -> Optional[str]:
        """
        Generate image using AI (OpenAI DALL-E)
        
        Args:
            prompt: Text prompt for image generation
            user_id: User ID for tracking
            
        Returns:
            Path to generated image file
        """
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key not configured")
        
        try:
            import openai
            client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
            
            # Generate image using DALL-E
            response = await client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            
            image_url = response.data[0].url
            
            # Download and save image
            image_path = await self.download_image(image_url, user_id)
            return image_path
            
        except Exception as e:
            raise Exception(f"Image generation error: {str(e)}")
    
    async def download_image(self, url: str, user_id: int) -> str:
        """Download image from URL and save locally"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"user_{user_id}_{timestamp}.png"
        filepath = self.upload_dir / filename
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    with open(filepath, 'wb') as f:
                        f.write(await response.read())
                    return str(filepath)
                else:
                    raise Exception(f"Failed to download image: {response.status}")
    
    def get_emotion_image(self, emotion: str) -> Optional[str]:
        """
        Get a pre-defined emotion image
        
        Args:
            emotion: Emotion type (happy, sad, love, comfort, etc.)
            
        Returns:
            Path to emotion image
        """
        # This would map to pre-existing emotion images
        emotion_images = {
            "happy": "data/emotions/happy.jpg",
            "sad": "data/emotions/comfort.jpg",
            "love": "data/emotions/love.jpg",
            "comfort": "data/emotions/hug.jpg",
            "support": "data/emotions/support.jpg",
        }
        
        image_path = emotion_images.get(emotion.lower())
        if image_path and os.path.exists(image_path):
            return image_path
        return None
    
    async def send_daily_image(self, user_mood: str = "positive") -> str:
        """
        Generate or select a daily motivational image
        
        Args:
            user_mood: User's current mood
            
        Returns:
            Path to image file
        """
        # Mood-based prompts
        mood_prompts = {
            "positive": "A beautiful sunrise over mountains, peaceful and inspiring, digital art",
            "sad": "A gentle comforting scene with warm colors, peaceful nature, digital art",
            "anxious": "A calm zen garden with cherry blossoms, tranquil atmosphere, digital art",
            "lonely": "Two hands holding together, warm and supportive, digital art",
            "default": "A heartwarming scene of friendship and support, digital art"
        }
        
        prompt = mood_prompts.get(user_mood, mood_prompts["default"])
        
        # For demo purposes, you might want to use pre-existing images
        # to avoid API costs during development
        emotion_image = self.get_emotion_image(user_mood)
        if emotion_image:
            return emotion_image
        
        # Otherwise generate new image
        # Note: This requires OpenAI API key and will incur costs
        # Uncomment for production use:
        # return await self.generate_image(prompt, user_id)
        
        return None


# Global image service instance
image_service = ImageService()
