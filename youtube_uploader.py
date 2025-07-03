import os
import shutil
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from app import app, db
from models import VideoShort, YouTubeCredentials, UploadStatus
from oauth_handler import OAuthHandler

logger = logging.getLogger(__name__)

class YouTubeUploader:
    def __init__(self):
        self.oauth_handler = OAuthHandler()
        
    def upload_short(self, short_id, user_email):
        """Upload a video short to YouTube"""
        with app.app_context():
            short = VideoShort.query.get(short_id)
            if not short:
                logger.error(f"Short {short_id} not found")
                return
            
            try:
                logger.info(f"Starting YouTube upload for short {short_id}")
                
                # Update status
                short.upload_status = UploadStatus.UPLOADING
                db.session.commit()
                
                # Get valid credentials
                creds = self._get_valid_credentials(user_email)
                if not creds:
                    raise Exception("No valid YouTube credentials found")
                
                # Build YouTube service
                youtube = build('youtube', 'v3', credentials=creds)
                
                # Upload video
                video_id = self._upload_video(youtube, short)
                
                # Update short with YouTube video ID
                short.youtube_video_id = video_id
                short.upload_status = UploadStatus.COMPLETED
                db.session.commit()
                
                # Don't cleanup files after successful upload - keep videos as requested
                logger.info(f"Video upload completed - keeping files as requested")
                
                logger.info(f"Successfully uploaded short {short_id} to YouTube: {video_id}")
                
            except Exception as e:
                logger.error(f"Failed to upload short {short_id}: {e}")
                short.upload_status = UploadStatus.FAILED
                short.upload_error = str(e)
                db.session.commit()
    
    def _get_valid_credentials(self, user_email):
        """Get valid YouTube credentials, refreshing if necessary"""
        try:
            db_creds = YouTubeCredentials.query.filter_by(user_email=user_email).first()
            if not db_creds:
                return None
            
            # Create OAuth2 credentials object
            creds = Credentials(
                token=db_creds.access_token,
                refresh_token=db_creds.refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=self.oauth_handler.client_id,
                client_secret=self.oauth_handler.client_secret
            )
            
            # Refresh if expired
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                
                # Update database with new token
                db_creds.access_token = creds.token
                if creds.expiry:
                    db_creds.token_expires = creds.expiry
                db.session.commit()
                
                logger.info(f"Refreshed credentials for {user_email}")
            
            return creds
            
        except Exception as e:
            logger.error(f"Failed to get valid credentials: {e}")
            return None
    
    def _upload_video(self, youtube, short):
        """Upload video to YouTube"""
        try:
            if not short.output_path or not os.path.exists(short.output_path):
                raise Exception("Video file not found")
            
            # Ensure description is between 4000-4500 characters
            description = short.description or "Generated YouTube Short"
            
            # If description is too short, pad it to reach 4000 characters
            if len(description) < 4000:
                base_content = description
                
                # Add engaging content to reach 4000+ characters
                padding_content = """
                
🔥 Welcome to our YouTube Shorts! 🔥

This amazing short video was created using advanced AI technology to bring you the most engaging and entertaining content. Our AI analyzes thousands of hours of video content to identify the most captivating moments and transform them into perfect bite-sized entertainment.

✨ What makes this short special:
• Carefully selected for maximum engagement
• Optimized for viral potential
• Created with cutting-edge AI technology
• Designed to keep you entertained

📱 Don't forget to:
• LIKE this video if you enjoyed it
• SUBSCRIBE for more amazing shorts
• SHARE with your friends and family
• COMMENT your thoughts below
• TURN ON notifications for latest uploads

🎯 Why you'll love our content:
Our AI-powered system identifies the most exciting, funny, and engaging moments from longer videos and transforms them into perfect shorts. Each video is carefully crafted to maximize entertainment value while maintaining the essence of the original content.

🚀 Join our community:
We're building an amazing community of viewers who love high-quality, engaging short-form content. Every view, like, and comment helps us create even better content for you!

🌟 Behind the scenes:
This short was created using advanced machine learning algorithms that analyze viewer engagement patterns, emotional responses, and viral content characteristics. The result is content that's specifically designed to be entertaining and shareable.

💡 Fun fact:
Did you know that our AI considers over 50 different factors when selecting the perfect segments for our shorts? From emotional intensity to visual appeal, every aspect is carefully analyzed to bring you the best possible viewing experience.

🎬 More content coming soon:
We're constantly working on new and exciting shorts. Make sure to subscribe and hit the notification bell so you never miss our latest uploads!

#Shorts #Viral #Entertainment #AI #Technology #Fun #Engaging #MustWatch #Trending #Popular #YouTube #Content #Amazing #Awesome #Epic #Incredible #Fantastic #Outstanding #Brilliant #Spectacular #Phenomenal #Extraordinary #Remarkable #Impressive #Stunning #Breathtaking #Captivating #Mesmerizing #Fascinating #Intriguing #Compelling #Addictive #Binge #Watch #Subscribe #Like #Share #Comment #Follow #Community #Creator #Channel #Video #Short #Clip #Moment #Highlight #Best #Top #Quality #Premium #Exclusive #Original #Creative #Innovative #Unique #Special #Limited #Rare #Collectible #Vintage #Classic #Modern #Contemporary #Fresh #New #Latest #Updated #Current #Recent #Hot #Trending #Popular #Viral #Famous #Celebrated #Acclaimed #Recognized #Awarded #Winning #Champion #Leader #Pioneer #Expert #Professional #Master #Skilled #Talented #Gifted #Exceptional #Outstanding #Superior #Excellence #Perfection #Mastery #Expertise #Knowledge #Wisdom #Intelligence #Genius #Brilliant #Smart #Clever #Witty #Funny #Hilarious #Amusing #Entertaining #Enjoyable #Pleasant #Delightful #Wonderful #Marvelous #Fantastic #Terrific #Great #Good #Nice #Cool #Awesome #Amazing #Incredible #Unbelievable #Extraordinary #Remarkable #Impressive #Stunning #Beautiful #Gorgeous #Lovely #Attractive #Appealing #Charming #Elegant #Graceful #Stylish #Fashionable #Trendy #Modern #Contemporary #Fresh #New #Latest #Updated #Current #Recent #Hot #Trending #Popular #Viral #Famous #Celebrated #Acclaimed #Recognized #Awarded #Winning #Champion #Leader #Pioneer #Expert #Professional #Master #Skilled #Talented #Gifted #Exceptional #Outstanding #Superior #Excellence #Perfection #Mastery #Expertise #Knowledge #Wisdom #Intelligence #Genius #Brilliant #Smart #Clever #Witty #Funny #Hilarious #Amusing #Entertaining #Enjoyable #Pleasant #Delightful #Wonderful #Marvelous #Fantastic #Terrific #Great #Good #Nice #Cool #Awesome #Amazing #Incredible #Unbelievable #Extraordinary #Remarkable #Impressive #Stunning #Beautiful #Gorgeous #Lovely #Attractive #Appealing #Charming #Elegant #Graceful #Stylish #Fashionable #Trendy
                """
                
                description = base_content + padding_content
            
            # Trim to 4500 characters max if too long
            if len(description) > 4500:
                description = description[:4497] + "..."
            
            # Ensure it's at least 4000 characters
            while len(description) < 4000:
                description += " #Shorts #Viral #Entertainment #YouTube #MustWatch #Trending #Amazing #Awesome #Epic #Incredible #Fantastic #Outstanding #Brilliant #Spectacular #Phenomenal #Extraordinary #Remarkable #Impressive #Stunning #Breathtaking #Captivating #Mesmerizing #Fascinating #Intriguing #Compelling #Addictive #Subscribe #Like #Share #Comment #Follow #Community #Creator #Channel #Video #Short #Clip #Moment #Highlight #Best #Top #Quality #Premium #Exclusive #Original #Creative #Innovative #Unique #Special #Hot #Popular #Famous #Celebrated #Acclaimed #Expert #Professional #Master #Skilled #Talented #Gifted #Exceptional #Superior #Excellence #Perfection #Mastery #Expertise #Knowledge #Wisdom #Intelligence #Genius #Smart #Clever #Witty #Funny #Hilarious #Amusing #Entertaining #Enjoyable #Pleasant #Delightful #Wonderful #Marvelous #Terrific #Great #Good #Nice #Cool #Beautiful #Gorgeous #Lovely #Attractive #Appealing #Charming #Elegant #Graceful #Stylish #Fashionable #Modern #Contemporary #Fresh #New #Latest #Updated #Current #Recent"
                if len(description) > 4500:
                    description = description[:4497] + "..."
                    break
            
            logger.info(f"Video description length: {len(description)} characters")
            
            # Prepare video metadata
            body = {
                'snippet': {
                    'title': short.title or f"YouTube Short #{short.id}",
                    'description': description,
                    'tags': short.tags or ['shorts', 'viral'],
                    'categoryId': '22',  # People & Blogs
                    'defaultLanguage': 'en',
                    'defaultAudioLanguage': 'en'
                },
                'status': {
                    'privacyStatus': 'public',  # Can be 'private', 'unlisted', or 'public'
                    'madeForKids': False,
                    'selfDeclaredMadeForKids': False
                }
            }
            
            # Create media upload object
            media = MediaFileUpload(
                short.output_path,
                chunksize=-1,
                resumable=True,
                mimetype='video/mp4'
            )
            
            # Insert video
            insert_request = youtube.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            # Execute upload
            response = None
            while response is None:
                status, response = insert_request.next_chunk()
                if status:
                    logger.info(f"Upload progress {int(status.progress() * 100)}%")
            
            if 'id' not in response:
                raise Exception(f"Upload failed: {response}")
            
            video_id = response['id']
            logger.info(f"Video uploaded successfully: https://www.youtube.com/watch?v={video_id}")
            
            return video_id
            
        except Exception as e:
            raise Exception(f"Video upload failed: {e}")
    
    def _cleanup_short_files(self, short):
        """Keep files after successful upload - no cleanup"""
        try:
            logger.info(f"Keeping short video file: {short.output_path}")
            logger.info(f"Keeping thumbnail file: {short.thumbnail_path}")
            
            # Check if this was the last short for the job
            job = short.job
            remaining_shorts = VideoShort.query.filter_by(job_id=job.id).filter(
                VideoShort.upload_status != UploadStatus.COMPLETED
            ).count()
            
            if remaining_shorts == 0:
                # All shorts uploaded, but keep all files
                logger.info(f"All shorts uploaded for job {job.id} - keeping all files")
                
        except Exception as e:
            logger.error(f"Error during file status check: {e}")
    
    def _cleanup_job_files(self, job):
        """Keep all files related to a job - no cleanup"""
        try:
            logger.info(f"Keeping original video file: {job.video_path}")
            logger.info(f"Keeping audio file: {job.audio_path}")
            logger.info(f"Keeping transcript file: {job.transcript_path}")
            
            # Only clean up truly temporary files older than 24 hours
            self._cleanup_old_temp_files()
            
            logger.info(f"Files preserved for job {job.id}")
            
        except Exception as e:
            logger.error(f"Error during file preservation: {e}")
    
    def _cleanup_old_temp_files(self):
        """Remove only very old temporary files (older than 24 hours)"""
        try:
            directories_to_check = ['temp']  # Only check temp directory for truly temporary files
            
            for dir_name in directories_to_check:
                if os.path.exists(dir_name):
                    import time
                    current_time = time.time()
                    for filename in os.listdir(dir_name):
                        file_path = os.path.join(dir_name, filename)
                        if os.path.isfile(file_path):
                            file_age = current_time - os.path.getmtime(file_path)
                            # Only remove files older than 24 hours (86400 seconds)
                            if file_age > 86400:
                                os.remove(file_path)
                                logger.info(f"Removed old temporary file: {file_path}")
                        
        except Exception as e:
            logger.error(f"Error during temp file cleanup: {e}")
    
    def upload_shorts_for_job(self, job_id, user_email):
        """Upload all shorts for a job"""
        with app.app_context():
            from models import VideoJob, VideoShort
            
            job = VideoJob.query.get(job_id)
            if not job:
                logger.error(f"Job {job_id} not found")
                return False
            
            # Get all shorts for this job that haven't been uploaded yet
            shorts = VideoShort.query.filter_by(
                job_id=job_id,
                upload_status=UploadStatus.PENDING
            ).all()
            
            if not shorts:
                logger.info(f"No shorts to upload for job {job_id}")
                return True
            
            logger.info(f"Starting upload of {len(shorts)} shorts for job {job_id}")
            
            success_count = 0
            for short in shorts:
                try:
                    self.upload_short(short.id, user_email)
                    success_count += 1
                    logger.info(f"Successfully uploaded short {short.id}")
                except Exception as e:
                    logger.error(f"Failed to upload short {short.id}: {e}")
                    # Update short with error status
                    short.upload_status = UploadStatus.FAILED
                    short.upload_error = str(e)
                    db.session.commit()
            
            logger.info(f"Upload completed: {success_count}/{len(shorts)} shorts uploaded successfully")
            return success_count == len(shorts)
