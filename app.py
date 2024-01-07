from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pytube import YouTube
import os
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
        video = yt.streams.filter(only_audio=True).first()

        # Use /tmp directory for temporary storage
        tmp_directory = '/tmp'
        os.makedirs(tmp_directory, exist_ok=True)

        out_file = video.download(output_path=tmp_directory)
        base, ext = os.path.splitext(out_file)
        file_name = base + '.m4a'

        try:
            os.rename(os.path.join(tmp_directory, out_file), os.path.join(tmp_directory, file_name))
        except:
            os.remove(os.path.join(tmp_directory, file_name))
            os.rename(os.path.join(tmp_directory, out_file), os.path.join(tmp_directory, file_name))

        return os.path.join(tmp_directory, file_name)
    
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

    # Download youtube video and save to audio, perform transcription
    audio_filename = video_processor.save_audio(url)

    if not audio_filename:
        raise HTTPException(status_code=500, detail="An error occurred while downloading the video or audio")
    
    api_key = os.getenv('ASSEMBLYAI_API_KEY')
    if not api_key:
        raise ValueError("API Key not found. Please set the ASSEMBLYAI_API_KEY environment variable.")
    aai.settings.api_key = api_key 

    transcript_result = video_processor.transcribe(audio_filename)
    auto_chapters = video_processor.auto_chapters(audio_filename)
    summary = video_processor.summary(audio_filename)

    response_data = {
        'video_url': audio_filename,
        'transcript': transcript_result,
        'chapters': auto_chapters,
        'summary': summary
    }

    # Clean up temporary files
    video_processor.remove_temporary_files(audio_filename)

    return response_data


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)