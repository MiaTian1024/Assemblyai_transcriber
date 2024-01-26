from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pytube import YouTube
import os
import yt_dlp
from pydantic import BaseModel
import assemblyai as aai
from mangum import Mangum

class URL(BaseModel):
    url: str

app = FastAPI()
handler = Mangum(app)

origins = ["https://aistudio.contentedai.com",
           "https://news.contentedai.com"
          ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Content-Type"],
)

class VideoProcessor:
    def get_info(self, url):
        try:          
            yt = YouTube(url)  # Create a YouTube object            
            video_id = yt.video_id  # Get video ID       
            video_length = yt.length  # Get video length in seconds
            return video_id, video_length
        except Exception as e:
            print(f"An error occurred: {e}")
            return None, None

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
            return None 
        
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
    
    def save_audio_yt_dlp(self, youtube_url):
        ydl_opts = {
            'format': 'm4a/bestaudio/best',  
            'outtmpl': '%(id)s.%(ext)s',  
            'postprocessors': [{  # Extract audio using ffmpeg
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }]
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:            
            info = ydl.extract_info(youtube_url, download=False) 
            video_title = info.get('id', 'Unknown_Title')
            file_name = f"{video_title}.m4a"         
            ydl.download([youtube_url])   # Download the video
    
        tmp_directory = '/tmp'
        os.makedirs(tmp_directory, exist_ok=True)

        try:
            new_file_path = os.path.join(tmp_directory, file_name)
            if os.path.exists(new_file_path):
                os.remove(new_file_path)
            os.rename(file_name, new_file_path)
            print(f"File successfully moved to {new_file_path}")
        except Exception as e:
            print("Error during file operation:", e)
            return None 

        if os.path.exists(new_file_path):
            return new_file_path
        else:
            print(f"File not found: {new_file_path}")
            return None
        
    def save_audio_yt_dlp_local(self, youtube_url):
        ydl_opts = {
            'format': 'm4a/bestaudio/best',  
            'outtmpl': '%(id)s.%(ext)s',  
            'postprocessors': [{  # Extract audio using ffmpeg
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }]
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:            
            info = ydl.extract_info(youtube_url, download=False) 
            video_title = info.get('id', 'Unknown_Title')
            file_name = f"{video_title}.m4a"         
            ydl.download([youtube_url])   # Download the video
    
        return file_name

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
        config = aai.TranscriptionConfig(
            entity_detection=True,
            speaker_labels=True
        )
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

    # try:
    #     # Try using the first method to save audio
    #     audio_filename = video_processor.save_audio(url)
    # except Exception as e1:
    #     print(f"First method failed due to: {e1}. Trying second method.")
    #     try:
    #         # If the first method fails, use the second method
    #         audio_filename = video_processor.save_audio_yt_dlp(url)
    #     except Exception as e2:
    #         error_message = f"Failed to process video. First method error: {e1}. Second method error: {e2}"
    #         raise HTTPException(status_code=500, detail=error_message)
        
    try:
        audio_filename = video_processor.save_audio(url)
    except Exception as e:
        error_message = f"Failed to process video. error: {e}"
        raise HTTPException(status_code=500, detail=error_message)

    if not audio_filename:
        raise HTTPException(status_code=500, detail="Both methods failed, but no specific error was caught.")

    api_key = os.getenv('ASSEMBLYAI_API_KEY')
    if not api_key:
        raise ValueError("API Key not found. Please set the ASSEMBLYAI_API_KEY environment variable.")
    aai.settings.api_key = api_key 

    transcript = video_processor.entity_detection(audio_filename)
    transcript_text = transcript.text
    transcript_entity = transcript.entities
    transcript_utterance = transcript.utterances
  
    response_data = {
        'video_url': audio_filename,
        'transcript': transcript_text,
        'entity': transcript_entity,
        'utterance': transcript_utterance
    }

    # Clean up temporary files
    video_processor.remove_temporary_files(audio_filename)

    return response_data

@app.post("/test")
async def test(content: URL):
    # Process a video from a given URL
    url = content.url
    if not url:
        raise HTTPException(status_code=400, detail="Invalid URL")
    print(url)
    
    audio_filename = video_processor.save_audio_yt_dlp(url)
    if not audio_filename:
        raise HTTPException(status_code=500, detail="Failed to process video.")

    api_key = os.getenv('ASSEMBLYAI_API_KEY')
    if not api_key:
        raise ValueError("API Key not found. Please set the ASSEMBLYAI_API_KEY environment variable.")
    aai.settings.api_key = api_key 

    transcript = video_processor.transcribe(audio_filename)

    response_data = {
        'video_url': audio_filename,
        'transcript': transcript  
    }

    # Clean up temporary files
    video_processor.remove_temporary_files(audio_filename)

    return response_data

@app.post("/upload")
async def upload(content: URL):
    # Process a video from a given URL
    url = content.url
    if not url:
        raise HTTPException(status_code=400, detail="Invalid URL")
    print(url)
    
    api_key = os.getenv('ASSEMBLYAI_API_KEY')
    if not api_key:
        raise ValueError("API Key not found. Please set the ASSEMBLYAI_API_KEY environment variable.")
    aai.settings.api_key = api_key 

    transcript = video_processor.entity_detection(url)
    transcript_text = transcript.text
    transcript_entity = transcript.entities
    transcript_utterance = transcript.utterances
  
    response_data = {
        'video_url': url,
        'transcript': transcript_text,
        'entity': transcript_entity,
        'utterance': transcript_utterance
    }

    return response_data

@app.post("/info")
async def info(content: URL):
    # Process a video from a given URL
    url = content.url
    if not url:
        raise HTTPException(status_code=400, detail="Invalid URL")
    print(url)
    
    video_id, video_length = video_processor.get_info(url)
  
    response_data = {
        'video_id': video_id,
        'video_length': video_length
    }

    return response_data

@app.post("/local")
async def local(content: URL):
    # Process a video from a given URL
    url = content.url
    if not url:
        raise HTTPException(status_code=400, detail="Invalid URL")
    print(url)
    
    audio_filename = video_processor.save_audio_yt_dlp_local(url)
    if not audio_filename:
        raise HTTPException(status_code=500, detail="Failed to process video.")

    api_key = os.getenv('ASSEMBLYAI_API_KEY')
    if not api_key:
        raise ValueError("API Key not found. Please set the ASSEMBLYAI_API_KEY environment variable.")
    aai.settings.api_key = api_key 

    transcript = video_processor.transcribe(audio_filename)

    response_data = {
        'video_url': audio_filename,
        'transcript': transcript  
    }

    # Clean up temporary files
    # video_processor.remove_temporary_files(audio_filename)

    return response_data

@app.post("/detection")
async def video_detection(content: URL):
    # Process a video from a given URL
    url = content.url
    if not url:
        raise HTTPException(status_code=400, detail="Invalid URL")
    print(url)

    try:
        audio_filename = video_processor.save_audio(url)
    except Exception as e:
        error_message = f"Failed to process video. error: {e}"
        raise HTTPException(status_code=500, detail=error_message)

    if not audio_filename:
        raise HTTPException(status_code=500, detail="Both methods failed, but no specific error was caught.")

    api_key = os.getenv('ASSEMBLYAI_API_KEY')
    if not api_key:
        raise ValueError("API Key not found. Please set the ASSEMBLYAI_API_KEY environment variable.")
    aai.settings.api_key = api_key 

    transcript = video_processor.entity_detection(audio_filename)
    transcript_text = transcript.text
    transcript_entity = transcript.entities
    transcript_utterance = transcript.utterances
  
    response_data = {
        'video_url': audio_filename,
        'transcript': transcript_text,
        'entity': transcript_entity,
        'utterance': transcript_utterance
    }

    # Clean up temporary files
    video_processor.remove_temporary_files(audio_filename)

    return response_data



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
