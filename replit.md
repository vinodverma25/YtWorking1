# YouTube Shorts Generator

## Overview

This is a Flask-based web application that automatically generates YouTube Shorts from longer YouTube videos using AI analysis. The application downloads videos, analyzes content with Gemini AI, creates vertical short clips, and can automatically upload them to YouTube.

## System Architecture

### Backend Framework
- **Flask** - Main web framework with SQLAlchemy ORM
- **SQLite/PostgreSQL** - Database for storing jobs, video metadata, and user credentials
- **Background Processing** - Threading for video processing pipeline
- **OAuth 2.0** - YouTube API integration for uploads

### AI Integration
- **Gemini AI** - Content analysis and segment identification
- **Audio Processing** - Transcription and speech analysis
- **Fallback Analysis** - Non-AI methods when API unavailable

### Video Processing Pipeline
- **yt-dlp** - YouTube video downloading
- **MoviePy** - Video editing and format conversion
- **FFmpeg** - Audio extraction and processing

## Key Components

### Core Models
- **VideoJob** - Tracks processing status and metadata
- **VideoShort** - Generated short clips with metadata
- **YouTubeCredentials** - OAuth tokens for YouTube uploads
- **TranscriptSegment** - Video transcription data

### Processing Pipeline
1. **Video Download** - Extract video from YouTube URL
2. **Transcription** - Generate transcript from audio
3. **AI Analysis** - Identify engaging segments with Gemini
4. **Video Editing** - Create vertical shorts from segments
5. **Upload** - Automatically upload to YouTube (optional)

### Web Interface
- **Bootstrap 5** - Dark theme UI framework
- **Real-time Progress** - AJAX updates during processing
- **File Management** - Download and preview generated shorts
- **Job Management** - View all processing jobs and status

## Data Flow

1. User submits YouTube URL through web interface
2. System creates VideoJob record with PENDING status
3. Background thread processes video:
   - Downloads video using yt-dlp
   - Extracts audio and generates transcript
   - Analyzes content with Gemini AI
   - Creates vertical short clips
   - Generates metadata and thumbnails
4. User can preview/download shorts or auto-upload to YouTube
5. Cleanup service removes old files periodically

## External Dependencies

### Required APIs
- **Gemini AI API** - Content analysis and segment identification
- **YouTube Data API v3** - Video uploads and metadata
- **OAuth 2.0** - YouTube authentication

### Third-party Libraries
- **yt-dlp** - YouTube video downloading
- **MoviePy** - Video processing and editing
- **FFmpeg** - Audio/video manipulation
- **Google Client Libraries** - YouTube API integration

### Environment Variables
- `GEMINI_API_KEY` - Primary Gemini AI API key
- `YOUTUBE_CLIENT_ID` - YouTube OAuth client ID
- `YOUTUBE_CLIENT_SECRET` - YouTube OAuth client secret
- `DATABASE_URL` - Database connection string
- `SESSION_SECRET` - Flask session encryption key

## Deployment Strategy

### Platform Support
- **Replit** - Primary deployment platform (recommended)
- **Railway** - Alternative with PostgreSQL
- **Render** - Alternative with built-in database

### Database Migration
- Development: SQLite for local testing
- Production: PostgreSQL for scalability
- Auto-migration: SQLAlchemy handles schema changes

### File Storage
- Local filesystem for temporary files
- Automatic cleanup of old files
- Upload/output directories created on startup

### Background Processing
- Threading for non-blocking video processing
- Status updates stored in database
- Progress tracking for real-time UI updates

## Changelog
- July 03, 2025: Initial setup
- July 03, 2025: Configured 5 Gemini API keys with rotating fallback system
- July 03, 2025: Set up YouTube OAuth with callback URL for Replit domain
- July 03, 2025: Fixed database schema issues and application is fully functional

## User Preferences

Preferred communication style: Simple, everyday language.