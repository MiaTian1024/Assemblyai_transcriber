from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pytube import YouTube
import os
import re
import subprocess
from pydantic import BaseModel
import assemblyai as aai
from mangum import Mangum

class URL(BaseModel):
    url: str

app = FastAPI()
handler = Mangum(app)

origins = ["https://aistudio.contentedai.com"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Content-Type"],
)

class VideoProcessor:
    def save_video(self, url, video_filename):
        # Download the highest resolution video from YouTube given a URL
        youtube_object = YouTube(url)
        youtube_object = youtube_object.streams.get_highest_resolution()

        # Use /tmp directory for temporary storage
        tmp_directory = '/tmp'
        os.makedirs(tmp_directory, exist_ok=True)

        try:
            # Save the video in /tmp directory
            youtube_object.download(output_path=tmp_directory, filename=video_filename)
        except:
            return None
        return os.path.join(tmp_directory, video_filename)

    def save_audio(self, url):
        # Download the audio stream from a YouTube video and convert it to m4a
        yt = YouTube(url)
        # Select the audio stream
        try:
            video = yt.streams.filter(only_audio=True).first()
            if video is None:
                raise Exception("No audio stream found")
        except KeyError as e:
            print("KeyError encountered when selecting the stream:", e)
            # Try to select an alternative stream if possible
            video = yt.streams.filter(only_audio=True).order_by('abr').desc().first()
            if video is None:
                print("No alternative audio stream found")
                return None

        # Use /tmp directory for temporary storage
        tmp_directory = '/tmp'
        os.makedirs(tmp_directory, exist_ok=True)

        try:
            out_file = video.download(output_path=tmp_directory)
        except Exception as e:
            print("Error during download:", e)
            return None  # or handle the error as needed
        
        base, ext = os.path.splitext(out_file)
        file_name = base + '.m4a'

        try:
            new_file_path = os.path.join(tmp_directory, file_name)
            if os.path.exists(new_file_path):
                os.remove(new_file_path)
            os.rename(out_file, new_file_path)
        except Exception as e:
            print("Error during file conversion:", e)
            return None  # or handle the error as needed

        return new_file_path
    
    def download_video_and_extract_audio(self, youtube_url):
        # Define the output directory
        output_directory = os.path.join(os.getcwd(), "downloads")
        os.makedirs(output_directory, exist_ok=True)

        # Download video using youtube-dl and extract the filename
        try:
            result = subprocess.run(['youtube-dl', '-o', os.path.join(output_directory, '%(title)s.%(ext)s'), youtube_url], capture_output=True, text=True, check=True)
            output = result.stdout
        except subprocess.CalledProcessError as e:
            print(f"Error downloading video: {e.output}")
            return None

        # Extract the filename from the output
        match = re.search(r'\[download\] Destination: (.+)', output)
        if not match:
            print("Couldn't extract the video filename.")
            return None
        downloaded_video_path = match.group(1)

        # Define the output audio file path
        output_audio_file = os.path.splitext(downloaded_video_path)[0] + '.mp3'

        # Extract audio using ffmpeg
        try:
            subprocess.run(['ffmpeg', '-i', downloaded_video_path, '-vn', '-ab', '128k', '-ar', '44100', '-y', output_audio_file], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error extracting audio: {e}")
            return None

        return output_audio_file
 
    def remove_temporary_files(self, file_path):
        # Remove temporary files from the /tmp directory
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Successfully removed file: {file_path}")
        except Exception as e:
            print(f"Error removing files: {e}")

    def transcribe(self, audio_file): 
        transcript = aai.Transcriber().transcribe(audio_file)
        return transcript.text
    
    def auto_chapters(self, audio_file): 
        config = aai.TranscriptionConfig(auto_chapters=True)
        transcript = aai.Transcriber().transcribe(audio_file, config)
        return transcript.chapters
    
    def entity_detection(self, audio_file): 
        config = aai.TranscriptionConfig(entity_detection=True)
        transcript = aai.Transcriber().transcribe(audio_file, config)
        return transcript
    
    def summary(self, audio_file): 
        config = aai.TranscriptionConfig(
            summarization=True,
            summary_model=aai.SummarizationModel.informative,
            summary_type=aai.SummarizationType.bullets
        )
        transcript = aai.Transcriber().transcribe(audio_file, config)
        return transcript.summary
    

video_processor = VideoProcessor()

@app.get("/")
async def root():
    return {"message": "Welcome to YouTube Transcriber API"}

@app.post("/process")
async def process_video(content: URL):
    # Process a video from a given URL
    url = content.url
    if not url:
        raise HTTPException(status_code=400, detail="Invalid URL")
    print(url)

    # Download youtube video and save to audio, perform transcription
    audio_filename = video_processor.save_audio(url)
    # audio_filename = video_processor.download_video_and_extract_audio(url)

    if not audio_filename:
        raise HTTPException(status_code=500, detail="An error occurred while downloading the video or audio")
    
    api_key = os.getenv('ASSEMBLYAI_API_KEY')
    if not api_key:
        raise ValueError("API Key not found. Please set the ASSEMBLYAI_API_KEY environment variable.")
    aai.settings.api_key = api_key 

    transcript = video_processor.entity_detection(audio_filename)
    transcript_text = transcript.text
    transcript_entity = transcript.entities
  
    response_data = {
        'video_url': audio_filename,
        'transcript': transcript_text,
        'entity': transcript_entity
    }

    # Clean up temporary files
    video_processor.remove_temporary_files(audio_filename)

    return response_data


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)