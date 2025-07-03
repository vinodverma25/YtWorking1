
import os
import shutil
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify, session, send_file
from app import app, db
from models import VideoJob, VideoShort, UploadStatus
from video_processor import VideoProcessor
from oauth_handler import OAuthHandler
from youtube_uploader import YouTubeUploader
import logging

logger = logging.getLogger(__name__)

@app.context_processor
def inject_common_vars():
    """Inject common variables into all templates"""
    return {
        'youtube_connected': session.get('youtube_connected', False),
        'user_email': session.get('youtube_email'),
        'youtube_channel': session.get('youtube_channel')
    }

@app.route('/')
def index():
    # Get recent jobs for display
    recent_jobs = VideoJob.query.order_by(VideoJob.created_at.desc()).limit(6).all()
    
    # Check if YouTube is connected
    youtube_connected = session.get('youtube_connected', False)
    user_email = session.get('youtube_email')
    
    return render_template('index.html', 
                         recent_jobs=recent_jobs,
                         youtube_connected=youtube_connected,
                         user_email=user_email)

@app.route('/submit', methods=['POST'])
def submit_video():
    try:
        youtube_url = request.form.get('youtube_url')
        video_quality = request.form.get('video_quality', '1080p')
        aspect_ratio = request.form.get('aspect_ratio', '9:16')
        max_shorts = int(request.form.get('max_shorts', 5))
        short_duration = request.form.get('short_duration', '30-45')
        content_language = request.form.get('content_language', 'hinglish')
        
        if not youtube_url:
            flash('Please provide a YouTube URL', 'error')
            return redirect(url_for('index'))
        
        # Create new job
        job = VideoJob(
            youtube_url=youtube_url,
            video_quality=video_quality,
            aspect_ratio=aspect_ratio,
            max_shorts=max_shorts,
            short_duration=short_duration,
            content_language=content_language
        )
        db.session.add(job)
        db.session.commit()
        
        # Start processing in background thread
        import threading
        processor = VideoProcessor()
        thread = threading.Thread(target=processor.process_video, args=(job.id,))
        thread.daemon = True
        thread.start()
        
        return redirect(url_for('process', job_id=job.id))
        
    except Exception as e:
        logger.error(f"Error submitting video: {e}")
        flash('Error processing video request', 'error')
        return redirect(url_for('index'))

@app.route('/results/view/<int:job_id>')
def view_results(job_id):
    job = VideoJob.query.get_or_404(job_id)
    shorts = VideoShort.query.filter_by(job_id=job_id).all()
    
    # Pass template variables
    youtube_connected = session.get('youtube_connected', False)
    user_email = session.get('youtube_email')
    
    return render_template('results.html', 
                         job=job, 
                         shorts=shorts,
                         youtube_connected=youtube_connected,
                         user_email=user_email)

@app.route('/jobs')
def list_jobs():
    jobs = VideoJob.query.order_by(VideoJob.created_at.desc()).all()
    return render_template('jobs.html', jobs=jobs)

@app.route('/cleanup', methods=['POST'])
def cleanup_system():
    try:
        # Clean up temporary files
        temp_dir = 'temp'
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            os.makedirs(temp_dir, exist_ok=True)
        
        # Clean up uploads
        uploads_dir = 'uploads'
        if os.path.exists(uploads_dir):
            shutil.rmtree(uploads_dir)
            os.makedirs(uploads_dir, exist_ok=True)
        
        # Clean up outputs
        outputs_dir = 'outputs'
        if os.path.exists(outputs_dir):
            shutil.rmtree(outputs_dir)
            os.makedirs(outputs_dir, exist_ok=True)
        
        # Clean up .git folder if exists
        git_dir = '.git'
        if os.path.exists(git_dir):
            shutil.rmtree(git_dir)
        
        # Clean up database
        db.drop_all()
        db.create_all()
        
        # Clean up __pycache__ directories
        for root, dirs, files in os.walk('.'):
            if '__pycache__' in dirs:
                shutil.rmtree(os.path.join(root, '__pycache__'))
        
        flash('All temporary files, cache, database, and .git folder cleaned successfully!', 'success')
        
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        flash(f'Error during cleanup: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/youtube/auth')
def youtube_auth():
    oauth_handler = OAuthHandler()
    auth_url = oauth_handler.get_authorization_url()
    return redirect(auth_url)

@app.route('/youtube/callback')
def youtube_callback():
    try:
        code = request.args.get('code')
        if not code:
            flash('Authorization failed', 'error')
            return redirect(url_for('index'))
        
        oauth_handler = OAuthHandler()
        user_info = oauth_handler.exchange_code_for_tokens(code)
        
        session['youtube_connected'] = True
        session['youtube_email'] = user_info.get('email')
        session['youtube_channel'] = user_info.get('channel_title')
        
        flash('YouTube account connected successfully!', 'success')
        return redirect(url_for('index'))
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        flash('Failed to connect YouTube account', 'error')
        return redirect(url_for('index'))

@app.route('/upload_shorts/<int:job_id>')
def upload_shorts(job_id):
    try:
        if not session.get('youtube_connected'):
            flash('Please connect your YouTube account first', 'error')
            return redirect(url_for('youtube_auth'))
        
        uploader = YouTubeUploader()
        uploader.upload_shorts_for_job(job_id, session.get('youtube_email'))
        
        flash('Shorts uploaded to YouTube successfully!', 'success')
        return redirect(url_for('view_results', job_id=job_id))
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        flash('Failed to upload shorts to YouTube', 'error')
        return redirect(url_for('view_results', job_id=job_id))

@app.route('/results/<int:job_id>')
def results(job_id):
    job = VideoJob.query.get_or_404(job_id)
    shorts = VideoShort.query.filter_by(job_id=job_id).all()
    return render_template('results.html', job=job, shorts=shorts)

@app.route('/process/<int:job_id>')
def process(job_id):
    job = VideoJob.query.get_or_404(job_id)
    return render_template('process.html', job=job)

@app.route('/download_short/<int:short_id>')
def download_short(short_id):
    """Download a generated short video"""
    short = VideoShort.query.get_or_404(short_id)
    
    if not short.output_path or not os.path.exists(short.output_path):
        flash('Video file not found', 'error')
        return redirect(url_for('view_results', job_id=short.job_id))
    
    return send_file(short.output_path, as_attachment=True)

@app.route('/upload_short/<int:short_id>', methods=['POST'])
def upload_short(short_id):
    """Upload a single short to YouTube"""
    if not session.get('youtube_connected'):
        flash('Please connect to YouTube first', 'error')
        return redirect(url_for('youtube_auth'))
    
    try:
        # Reset status to pending if retrying
        short = VideoShort.query.get_or_404(short_id)
        if short.upload_status and short.upload_status.value == 'failed':
            short.upload_status = UploadStatus.PENDING
            short.upload_error = None
            db.session.commit()
            flash('Retrying upload...', 'info')
        
        uploader = YouTubeUploader()
        uploader.upload_short(short_id, session.get('youtube_email'))
        flash('Short uploaded successfully!', 'success')
    except Exception as e:
        logger.error(f"Single upload error: {e}")
        flash('Failed to upload short to YouTube', 'error')
    
    return redirect(url_for('view_results', job_id=short.job_id))

@app.route('/delete_job/<int:job_id>', methods=['POST'])
def delete_job(job_id):
    """Delete a job and all associated files"""
    job = VideoJob.query.get_or_404(job_id)
    
    try:
        # Delete all associated shorts and their files
        for short in job.shorts:
            if short.output_path and os.path.exists(short.output_path):
                os.remove(short.output_path)
            if short.thumbnail_path and os.path.exists(short.thumbnail_path):
                os.remove(short.thumbnail_path)
        
        # Delete job files
        if job.video_path and os.path.exists(job.video_path):
            os.remove(job.video_path)
        if job.audio_path and os.path.exists(job.audio_path):
            os.remove(job.audio_path)
        if job.transcript_path and os.path.exists(job.transcript_path):
            os.remove(job.transcript_path)
        
        # Delete from database
        db.session.delete(job)
        db.session.commit()
        
        flash('Job deleted successfully', 'success')
        logger.info(f"Job {job_id} deleted successfully")
        
    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {e}")
        flash('Error deleting job', 'error')
        
    return redirect(url_for('list_jobs'))

@app.route('/youtube/disconnect', methods=['POST'])
def youtube_disconnect():
    session.pop('youtube_connected', None)
    session.pop('youtube_email', None)
    session.pop('youtube_channel', None)
    flash('YouTube account disconnected successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/health')
def health_check():
    """Health check endpoint for keep-alive"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'message': 'YouTube Shorts Generator is running'
    })

@app.errorhandler(404)
def page_not_found(e):
    return render_template('base.html', 
                         error_title='Page Not Found', 
                         error_message='The page you are looking for does not exist.'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('base.html', 
                         error_title='Internal Server Error', 
                         error_message='Something went wrong on our end.'), 500
