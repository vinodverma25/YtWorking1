import json
import logging
import os
from google import genai
from google.genai import types
from pydantic import BaseModel
from typing import List, Dict, Any

class SegmentAnalysis(BaseModel):
    engagement_score: float
    emotion_score: float
    viral_potential: float
    quotability: float
    emotions: List[str]
    keywords: List[str]
    reason: str

class VideoMetadata(BaseModel):
    title: str
    description: str
    tags: List[str]

class GeminiAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.client = None
        self.use_fallback_only = False
        self.api_keys = []
        self.current_key_index = 0

        # Collect all available API keys
        self._collect_api_keys()

        # Initialize Gemini client with first available key
        if self.api_keys:
            self._initialize_client()
        else:
            self.logger.warning("No Gemini API keys found in environment variables")
            self.logger.info("Will use fallback analysis methods only")
            self.use_fallback_only = True

    def _collect_api_keys(self):
        """Collect all available Gemini API keys from environment"""
        # Primary key
        primary_key = os.environ.get("GEMINI_API_KEY")
        if primary_key:
            self.api_keys.append(primary_key)

        # Backup keys
        for i in range(1, 5):  # Support up to 4 backup keys
            backup_key = os.environ.get(f"GEMINI_API_KEY_{i}")
            if backup_key:
                self.api_keys.append(backup_key)

        self.logger.info(f"Found {len(self.api_keys)} Gemini API key(s)")

    def _initialize_client(self):
        """Initialize client with current API key"""
        if self.current_key_index < len(self.api_keys):
            try:
                api_key = self.api_keys[self.current_key_index]
                self.client = genai.Client(api_key=api_key)
                self.logger.info(f"Gemini client initialized with API key #{self.current_key_index + 1}")
                return True
            except Exception as e:
                self.logger.warning(f"Failed to initialize Gemini client with key #{self.current_key_index + 1}: {e}")
                return False
        return False

    def _switch_to_next_key(self):
        """Switch to next available API key"""
        self.current_key_index += 1
        if self.current_key_index < len(self.api_keys):
            self.logger.info(f"Switching to backup API key #{self.current_key_index + 1}")
            if self._initialize_client():
                return True

        # No more keys available
        self.logger.warning("All Gemini API keys exhausted, switching to fallback mode")
        self.use_fallback_only = True
        self.client = None
        return False

    def _handle_api_error(self, error_msg: str):
        """Handle API errors and attempt key switching"""
        # Check for quota exceeded or rate limit errors
        if any(indicator in error_msg.lower() for indicator in ["429", "resource_exhausted", "quota", "rate limit"]):
            self.logger.warning(f"API quota/rate limit hit: {error_msg}")
            return self._switch_to_next_key()

        # For other errors, log but don't switch keys
        self.logger.error(f"API error: {error_msg}")
        return False

    def analyze_segment(self, text: str) -> Dict[str, Any]:
        """Analyze a text segment for engagement and viral potential using Gemini"""
        # Check if we should use fallback only
        if self.use_fallback_only or not self.client:
            self.logger.info("Using fallback analysis (no Gemini API available)")
            return self._fallback_analysis(text)

        try:
            system_prompt = """You are an expert content analyst specializing in viral social media content and YouTube Shorts.

            Analyze the given text segment for its potential to create engaging short-form video content.

            Consider these factors:
            - Engagement Score (0.0-1.0): How likely this content is to engage viewers
            - Emotion Score (0.0-1.0): Emotional impact and intensity
            - Viral Potential (0.0-1.0): Likelihood to be shared and go viral
            - Quotability (0.0-1.0): How memorable and quotable the content is
            - Emotions: List of emotions detected (humor, surprise, excitement, inspiration, etc.)
            - Keywords: Important keywords that make this content engaging
            - Reason: Brief explanation of why this segment is engaging

            Focus on content that has:
            - Strong emotional hooks
            - Surprising or unexpected elements
            - Humor or entertainment value
            - Inspirational or motivational content
            - Controversial or debate-worthy topics
            - Clear storytelling elements
            - Quotable phrases or moments"""

            # Use timeout and retry logic
            import time
            max_retries = 2
            response = None

            for attempt in range(max_retries):
                try:
                    response = self.client.models.generate_content(
                        model="gemini-2.5-pro",
                        contents=[
                            types.Content(role="user", parts=[types.Part(text=f"Analyze this content segment for YouTube Shorts potential:\n\n{text[:1000]}")])  # Limit text length
                        ],
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            response_mime_type="application/json",
                            response_schema=SegmentAnalysis,
                        ),
                    )
                    break  # Success, exit retry loop
                except Exception as retry_error:
                    if attempt == max_retries - 1:
                        raise retry_error
                    time.sleep(1)  # Wait before retry

            if response and response.text:
                result = json.loads(response.text)
                return {
                    'engagement_score': max(0.0, min(1.0, result.get('engagement_score', 0.5))),
                    'emotion_score': max(0.0, min(1.0, result.get('emotion_score', 0.5))),
                    'viral_potential': max(0.0, min(1.0, result.get('viral_potential', 0.5))),
                    'quotability': max(0.0, min(1.0, result.get('quotability', 0.5))),
                    'emotions': result.get('emotions', [])[:5],  # Limit to 5 emotions
                    'keywords': result.get('keywords', [])[:10],  # Limit to 10 keywords
                    'reason': result.get('reason', 'Content has potential for engagement')[:500]
                }
            else:
                raise Exception("Empty response from Gemini")

        except Exception as e:
            error_msg = str(e)
            self.logger.warning(f"Gemini API error: {error_msg}")

            # Try to switch to next API key if error is quota-related
            if self._handle_api_error(error_msg) and not self.use_fallback_only:
                self.logger.info("Retrying with next API key...")
                # Use fallback for now to prevent crashes
                return self._fallback_analysis(text)

            # Fallback analysis
            return self._fallback_analysis(text)

    def _fallback_analysis(self, text: str) -> Dict[str, Any]:
        """Enhanced fallback analysis when Gemini is unavailable"""
        text_lower = text.lower()
        words = text.split()

        # Enhanced keyword categories
        engagement_keywords = ['amazing', 'incredible', 'wow', 'shocking', 'unbelievable', 'funny', 'hilarious', 
                              'awesome', 'fantastic', 'mind-blowing', 'crazy', 'insane', 'epic', 'legendary']
        emotion_keywords = ['love', 'hate', 'excited', 'surprised', 'happy', 'angry', 'scared', 'thrilled',
                           'disappointed', 'frustrated', 'overwhelmed', 'passionate', 'emotional', 'heartwarming']
        viral_keywords = ['viral', 'trending', 'share', 'like', 'subscribe', 'follow', 'must-see', 'breaking',
                         'exclusive', 'revealed', 'secret', 'exposed', 'truth', 'shocking']
        quotable_keywords = ['said', 'quote', 'tells', 'explains', 'reveals', 'admits', 'confesses', 'announces']

        # Calculate scores based on keyword presence
        engagement_score = min(1.0, sum(1 for word in engagement_keywords if word in text_lower) * 0.15)
        emotion_score = min(1.0, sum(1 for word in emotion_keywords if word in text_lower) * 0.15)
        viral_score = min(1.0, sum(1 for word in viral_keywords if word in text_lower) * 0.2)
        quotability_score = min(1.0, sum(1 for word in quotable_keywords if word in text_lower) * 0.2)

        # Length-based scoring (optimal length for shorts)
        text_length = len(words)
        if 20 <= text_length <= 50:  # Optimal length for short clips
            length_bonus = 0.2
        elif 10 <= text_length <= 80:  # Good length
            length_bonus = 0.1
        else:
            length_bonus = 0.0

        # Add length bonus to all scores
        engagement_score = min(1.0, engagement_score + length_bonus)
        emotion_score = min(1.0, emotion_score + length_bonus)
        viral_score = min(1.0, viral_score + length_bonus)
        quotability_score = min(1.0, quotability_score + length_bonus)

        # Ensure minimum scores for content viability
        engagement_score = max(0.4, engagement_score)
        emotion_score = max(0.3, emotion_score)
        viral_score = max(0.3, viral_score)
        quotability_score = max(0.2, quotability_score)

        # Detect emotions based on keywords
        detected_emotions = []
        if any(word in text_lower for word in ['funny', 'hilarious', 'joke', 'laugh']):
            detected_emotions.append('humor')
        if any(word in text_lower for word in ['shocking', 'surprised', 'unexpected']):
            detected_emotions.append('surprise')
        if any(word in text_lower for word in ['love', 'heartwarming', 'beautiful']):
            detected_emotions.append('inspiration')
        if any(word in text_lower for word in ['angry', 'frustrated', 'hate']):
            detected_emotions.append('controversy')
        if not detected_emotions:
            detected_emotions = ['general']

        # Extract meaningful keywords (longer words, excluding common words)
        common_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'a', 'an'}
        keywords = [word for word in words if len(word) > 3 and word.lower() not in common_words][:8]

        return {
            'engagement_score': engagement_score,
            'emotion_score': emotion_score,
            'viral_potential': viral_score,
            'quotability': quotability_score,
            'emotions': detected_emotions[:5],
            'keywords': keywords,
            'reason': f'Fallback analysis: {len(words)} words, detected {", ".join(detected_emotions)} content'
        }

    def generate_metadata(self, segment_text: str, original_title: str, language: str = "English") -> Dict[str, Any]:
        """Generate title, description, and tags for a video short using Gemini"""
        # Check if we should use fallback only
        if self.use_fallback_only or not self.client:
            self.logger.info("Using fallback metadata generation (no Gemini API available)")
            return self._fallback_metadata(segment_text, original_title, language)

        # Enhanced retry logic with exponential backoff
        max_retries = 3
        base_delay = 2
        
        for attempt in range(max_retries):
            try:
                system_prompt = f"""You are an expert YouTube content creator specializing in viral Shorts. Generate extremely engaging and viral metadata for a YouTube Short based on the content segment and original video title in {language}.

                Guidelines:
                - Title: Create a viral, clickbait title under 100 characters with relevant emojis and at least 2 hashtags
                - Description: Write a compelling 1500+ word description with story, context, emotional hooks, call-to-actions, and strategic hashtag placement
                - Tags: Generate exactly 28 viral, trending tags for maximum discoverability (total under 500 characters)

                VIRAL TITLE REQUIREMENTS:
                - Use 2-3 relevant emojis that match the content emotion
                - Include emotional triggers (SHOCKING, INSANE, VIRAL, etc.)
                - Create curiosity gaps and cliffhangers
                - Use trending words and phrases
                - Make it clickable and shareable
                - Include at least 2 hashtags in title
                - Keep under 100 characters total

                VIRAL DESCRIPTION REQUIREMENTS:
                - Start with a hook that grabs attention immediately
                - Tell a story or provide context about the moment
                - Include emotional commentary and reactions
                - Add background information about the original video
                - Include call-to-actions (like, subscribe, comment, share)
                - Use trending hashtags strategically throughout
                - End with engagement questions
                - Must be at least 1500 words long
                - Include relevant emojis throughout the description
                - Create community engagement prompts
                - Add background context and reactions

                VIRAL TAGS REQUIREMENTS:
                - Generate exactly 28 tags
                - Mix broad trending tags with specific niche tags
                - Include emotion-based tags (funny, shocking, viral, etc.)
                - Add content category tags
                - Include current trending tags
                - Use variations of keywords
                - Keep total character count under 500 characters"""

                prompt = f"""Original video title: {original_title}

Content segment: {segment_text}

Generate VIRAL YouTube Shorts metadata with emojis, 1500+ word description, exactly 28 tags, and at least 2 hashtags in title for maximum viral potential in {language}."""

                response = self.client.models.generate_content(
                    model="gemini-2.5-pro",
                    contents=[
                        types.Content(role="user", parts=[types.Part(text=prompt)])
                    ],
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        response_schema=VideoMetadata,
                    ),
                )

                if response.text:
                    result = json.loads(response.text)
                    title = result.get('title', f"🔥 VIRAL Moment from {original_title} 😱 #Shorts #Viral")[:100]
                    description = result.get('description', self._create_long_description(segment_text, original_title))
                    tags = result.get('tags', self._get_default_viral_tags())[:28]
                    
                    # Ensure tags are under 500 characters total
                    tags_str = ', '.join(tags)
                    if len(tags_str) > 500:
                        # Truncate tags to fit under 500 characters
                        truncated_tags = []
                        current_length = 0
                        for tag in tags:
                            if current_length + len(tag) + 2 <= 500:  # +2 for comma and space
                                truncated_tags.append(tag)
                                current_length += len(tag) + 2
                            else:
                                break
                        tags = truncated_tags
                    
                    return {
                        'title': title,
                        'description': description,
                        'tags': tags
                    }
                else:
                    raise Exception("Empty response from Gemini")

            except Exception as e:
                error_msg = str(e)
                self.logger.warning(f"Gemini API error (attempt {attempt + 1}): {error_msg}")

                # Check if it's a rate limit or overload error
                if any(indicator in error_msg.lower() for indicator in ["429", "503", "resource_exhausted", "quota", "rate limit", "overloaded", "unavailable"]):
                    if attempt < max_retries - 1:
                        # Exponential backoff
                        delay = base_delay * (2 ** attempt)
                        self.logger.info(f"API overloaded/rate limited, waiting {delay} seconds before retry...")
                        import time
                        time.sleep(delay)
                        
                        # Try switching to next API key
                        if self._handle_api_error(error_msg) and not self.use_fallback_only:
                            self.logger.info("Switched to backup API key, retrying...")
                            continue
                    else:
                        self.logger.error("All retries exhausted due to API overload")
                        break
                else:
                    # For non-rate-limit errors, try switching keys
                    if self._handle_api_error(error_msg) and not self.use_fallback_only:
                        self.logger.info("Switched to backup API key due to error")
                        continue
                    else:
                        break

        # If all retries failed, use fallback
        self.logger.info("All Gemini API attempts failed, using enhanced fallback")
        return self._fallback_metadata(segment_text, original_title, language)

    def _fallback_metadata(self, segment_text: str, original_title: str, language: str = "English") -> Dict[str, Any]:
        """Enhanced fallback metadata generation for viral content"""
        words = segment_text.split()
        text_lower = segment_text.lower()

        # Extract meaningful keywords (exclude common words)
        common_words = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'a', 'an', 'this', 'that'}
        key_words = [word for word in words if len(word) > 3 and word.lower() not in common_words][:5]

        # Generate viral title with emojis and hashtags based on content type
        if any(word in text_lower for word in ['funny', 'hilarious', 'joke', 'laugh']):
            title = f"😂 HILARIOUS: {' '.join(key_words[:2])} - You Won't Stop Laughing! 🤣 #Shorts #Viral"
            emoji_theme = "humor"
        elif any(word in text_lower for word in ['shocking', 'unbelievable', 'incredible', 'insane']):
            title = f"😱 SHOCKING: {' '.join(key_words[:2])} - This Will Blow Your Mind! 🤯 #Shorts #Viral"
            emoji_theme = "shock"
        elif any(word in text_lower for word in ['amazing', 'awesome', 'fantastic', 'incredible']):
            title = f"🔥 AMAZING: {' '.join(key_words[:2])} - Absolutely Incredible! ✨ #Shorts #Viral"
            emoji_theme = "amazing"
        elif any(word in text_lower for word in ['secret', 'revealed', 'truth', 'hidden']):
            title = f"🤫 REVEALED: {' '.join(key_words[:2])} - The Truth Exposed! 😲 #Shorts #Viral"
            emoji_theme = "secret"
        elif any(word in text_lower for word in ['music', 'song', 'dance', 'singing']):
            title = f"🎵 VIRAL MUSIC: {' '.join(key_words[:2])} - This Hit Different! 🎶 #Shorts #Viral"
            emoji_theme = "music"
        else:
            title = f"🔥 VIRAL: {' '.join(key_words[:2])} - Must See This! 😍 #Shorts #Viral"
            emoji_theme = "general"

        # Limit title to 100 characters
        title = title[:100]

        # Generate long viral description (1500+ words)
        description = self._create_long_description(segment_text, original_title, emoji_theme)

        # Generate 28 viral tags
        all_tags = self._get_default_viral_tags()
        
        # Ensure tags are under 500 characters total
        tags_str = ', '.join(all_tags[:28])
        if len(tags_str) > 500:
            # Truncate tags to fit under 500 characters
            truncated_tags = []
            current_length = 0
            for tag in all_tags:
                if current_length + len(tag) + 2 <= 500:  # +2 for comma and space
                    truncated_tags.append(tag)
                    current_length += len(tag) + 2
                else:
                    break
            all_tags = truncated_tags

        return {
            'title': title,
            'description': description,
            'tags': all_tags
        }

    def _create_long_description(self, segment_text: str, original_title: str, emoji_theme: str = "general") -> str:
        """Create a long viral description with emojis and hashtags (1500+ words)"""
        text_lower = segment_text.lower()

        # Choose emojis based on theme
        emoji_sets = {
            "humor": ["😂", "🤣", "😆", "😄", "🙃", "😁", "😊"],
            "shock": ["😱", "🤯", "😲", "🫨", "😵", "🤐", "😳"],
            "amazing": ["🔥", "✨", "⭐", "💫", "🌟", "💥", "🚀"],
            "secret": ["🤫", "👀", "🕵️", "🔍", "💭", "🤔", "😏"],
            "music": ["🎵", "🎶", "🎤", "🎸", "🎹", "🥁", "🎺"],
            "general": ["🔥", "😍", "🤩", "💯", "👏", "🙌", "✨"]
        }

        emojis = emoji_sets.get(emoji_theme, emoji_sets["general"])

        description = f"""🚨 VIRAL ALERT! {emojis[0]} This moment from "{original_title}" is absolutely INSANE and you NEED to see it! {emojis[1]}

{emojis[2]} WHAT JUST HAPPENED?! {emojis[2]}
This clip is breaking the internet right now and for good reason! The moment captured here is pure gold - the kind of content that makes you stop scrolling and watch it 10 times in a row! {emojis[3]} I've been creating content for years, and moments like this remind me why I fell in love with sharing authentic experiences with the world.

💭 THE STORY BEHIND THIS VIRAL MOMENT:
This incredible segment comes from the amazing video "{original_title}" and let me tell you, when this part hit, the comments section went WILD! {emojis[4]} People are sharing this everywhere - Twitter, TikTok, Instagram, you name it! The original video has been gaining massive traction, but this particular moment? It's the crown jewel that everyone's talking about.

🎬 WHAT MAKES THIS SO SPECIAL:
"{segment_text[:300]}..." - Just reading this gives you chills, right? {emojis[5]} The way this moment unfolds is absolutely perfect. It's got everything - emotion, authenticity, and that special something that makes content go viral! You can feel the raw energy, the genuine emotion, and the perfect timing that makes this clip so incredibly shareable.

🌟 WHY EVERYONE'S TALKING ABOUT IT:
✅ Pure, unfiltered emotion that hits different
✅ The timing is absolutely perfect
✅ Relatable content that speaks to everyone
✅ That "main character energy" we all love
✅ Perfect for sharing with friends and family
✅ Authentic moments that can't be scripted
✅ The kind of content that makes you feel something real
✅ Universal appeal that crosses all boundaries

🔥 COMMUNITY REACTIONS:
The comments are going CRAZY! {emojis[6]} People are saying things like "This is why I love the internet", "I can't stop watching this", and "This made my whole day!" The way this resonates with people is incredible! We're seeing reactions from all over the world - people sharing their own similar experiences, relating to the emotions, and connecting with the authenticity of this moment.

💡 BEHIND THE SCENES:
What makes this even more special is the context. This isn't scripted or planned - it's pure, authentic content that just happened to be caught on camera. That's the magic of real moments! {emojis[0]} In a world full of manufactured content, finding genuine moments like this is like discovering treasure. The spontaneity, the real emotions, the unfiltered reactions - this is what makes content truly viral.

🎯 JOIN THE CONVERSATION:
👍 SMASH that like button if this gave you chills!
🔔 Subscribe for more viral moments like this!
💬 Comment below - what was your reaction when you first saw this?
📤 Share this with someone who needs to see it!
🔄 Save this for when you need a pick-me-up!
🎥 Tag a friend who would love this content!
💫 Let us know what other moments you'd like to see!

🏷️ TRENDING NOW:
This clip is part of a growing trend of authentic, unfiltered content that's taking over social media. We're living in the golden age of real moments being captured and shared! {emojis[1]} The algorithm is rewarding genuine content, and creators are finally understanding that authenticity beats perfection every single time.

📈 THE VIRAL FACTOR:
What makes content go viral? It's moments like these - unexpected, genuine, and emotionally resonant. This clip has all the elements: perfect timing, authentic emotion, and that indefinable quality that makes you want to share it immediately! The engagement metrics are through the roof, with views, likes, and shares climbing by the minute.

🌍 GLOBAL IMPACT:
People from all over the world are connecting with this moment. It doesn't matter what language you speak or where you're from - good content is universal! {emojis[2]} We're seeing reactions from every continent, proving that authentic human experiences transcend cultural boundaries.

🎉 MORE AMAZING CONTENT:
If you loved this clip, you're going to OBSESS over our other videos! We're constantly finding and sharing the most incredible, viral-worthy moments from across the internet. This is just the beginning! {emojis[3]} Our content library is packed with moments that will make you laugh, cry, think, and feel inspired.

💬 COMMUNITY ENGAGEMENT:
What do you think makes this moment so special? Drop your thoughts in the comments! {emojis[4]} We love hearing from our community and your perspectives always add so much value to these conversations. Some of the best insights come from you - our incredible viewers who bring unique perspectives to every piece of content we share.

🎭 THE EMOTIONAL JOURNEY:
This clip takes you on an emotional rollercoaster that's impossible to ignore. From the initial surprise to the building tension, and finally to that perfect climactic moment - it's a masterclass in storytelling without even trying to be one! {emojis[5]} The natural progression of emotions keeps you hooked from start to finish.

🌟 INSPIRATION CORNER:
Moments like this remind us why we create content in the first place. It's not just about views or likes - it's about creating connections, sharing experiences, and bringing people together through the power of storytelling. {emojis[6]} Every time we witness genuine human moments like this, it reinforces our belief in the power of authentic content.

⚡ FINAL THOUGHTS:
In a world full of content, this moment stands out. It's real, it's powerful, and it's exactly what we need more of. Thank you for being part of this incredible community that celebrates authentic human moments! {emojis[0]} Your support means everything to us, and it's what keeps us motivated to find and share these amazing moments with the world.

🙏 Don't forget to show some love - your engagement helps us find and share more amazing content like this! Every like, comment, and share makes a difference and helps us reach more people who need to see these incredible moments! {emojis[1]}

📢 CALL TO ACTION:
Ready to see more content like this? Hit that subscribe button and turn on notifications so you never miss a viral moment! Share this with your friends, family, and anyone who appreciates authentic, incredible content. Let's build a community of people who celebrate real moments and genuine human experiences! {emojis[2]}

#Shorts #Viral #Trending #MustWatch #Authentic #RealMoments #ViralVideo #ShareThis #Amazing #Incredible #SocialMedia #Funny #Emotional #Heartwarming #Inspiring #Entertainment #PopCulture #Internet #Community #Reactions #Mood #Vibes #Content #Creator #YouTube #TikTok #Instagram #Twitter #Share #Like #Subscribe #Comment #Save #Repost #Trending2024 #ViralContent #MustSee #Epic #Legendary #Unforgettable #Perfect #Timing #Genuine #Unfiltered #Raw #Authentic #Beautiful #Powerful #Moving #Touching #Hilarious #Shocking #Unbelievable #Incredible #Outstanding #Phenomenal #Extraordinary #Remarkable #Sensational #Spectacular #Breathtaking #Mindblowing #Gamechanging #Revolutionary #Engaging #Captivating #Compelling #Mesmerizing #Addictive #Shareable #Relatable #Universal #Timeless #Memorable"""

        return description

    def _get_default_viral_tags(self) -> List[str]:
        """Get 28 default viral tags"""
        return [
            'shorts', 'viral', 'trending', 'mustsee', 'amazing', 'incredible', 'shocking', 'unbelievable',
            'funny', 'hilarious', 'entertainment', 'comedy', 'emotional', 'heartwarming', 'inspiring',
            'motivation', 'lifestyle', 'relatable', 'authentic', 'genuine', 'raw', 'real', 'moments',
            'reactions', 'vibes', 'mood', 'content', 'creator'
        ]

    def analyze_video_file(self, video_path: str) -> Dict[str, Any]:
        """Analyze video file directly with Gemini vision capabilities"""
        # Check if we should use fallback only
        if self.use_fallback_only or not self.client:
            self.logger.info("Video file analysis not available (no Gemini API)")
            return {'analysis': 'Video analysis not available - using audio transcript analysis instead'}

        try:
            with open(video_path, "rb") as f:
                video_bytes = f.read()

            response = self.client.models.generate_content(
                model="gemini-2.5-pro",
                contents=[
                    types.Part.from_bytes(
                        data=video_bytes,
                        mime_type="video/mp4",
                    ),
                    "Analyze this video for engaging moments, emotional highlights, and viral potential. "
                    "Identify the most interesting segments that would work well as YouTube Shorts."
                ],
            )

            return {'analysis': response.text if response.text else 'No analysis available'}

        except Exception as e:
            self.logger.error(f"Video file analysis failed: {e}")
            return {'analysis': 'Video analysis not available'}