import os
import argparse
import json
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Scope required to view video metadata and privacy statuses
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

def get_youtube_service(token_name):
    """Handles OAuth authentication using your existing setup."""
    creds = None
    if os.path.exists(token_name):
        creds = Credentials.from_authorized_user_file(token_name, SCOPES)
        
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                "client_secret.json", SCOPES
            )
            creds = flow.run_local_server(port=0, open_browser=True)
            
        with open(token_name, "w") as token:
            token.write(creds.to_json())

    return googleapiclient.discovery.build("youtube", "v3", credentials=creds)


def get_uploads_playlist_id(youtube):
    """Retrieves the unique playlist ID containing all uploads for the authenticated channel."""
    channels_response = youtube.channels().list(
        part="contentDetails",
        mine=True
    ).execute()
    
    if not channels_response.get("items"):
        print("[ERROR] Could not find channel details for the provided token.")
        return None
        
    # Extract the 'uploads' playlist ID from contentDetails
    return channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]


def fetch_all_videos(token):
    """Extracts all uploaded videos from the channel with their full set of features."""
    youtube = get_youtube_service(token)
    
    playlist_id = get_uploads_playlist_id(youtube)
    if not playlist_id:
        return []
        
    print(f"Retrieving video tracklist from uploads playlist: {playlist_id}...")
    
    video_list = []
    next_page_token = None
    task_counter = 1
    
    # 1. Loop through the playlist items (Handles pagination via nextPageToken)
    while True:
        playlist_response = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=50,  # Maximum allowed per page by YouTube API
            pageToken=next_page_token
        ).execute()
        
        # Collect all video IDs on the current page
        page_video_ids = [item["snippet"]["resourceId"]["videoId"] for item in playlist_response.get("items", [])]
        
        if not page_video_ids:
            break
            
        # 2. Fetch full advanced metadata for this batch of video IDs (Fixing the part parameter)
        videos_response = youtube.videos().list(
            part="snippet,status,recordingDetails", # <-- Quitamos shortVideoDetails de aquí
            id=",".join(page_video_ids)
        ).execute()
        
        # 3. Parse each video's features into our standard dictionary layout
        for video in videos_response.get("items", []):
            snippet = video.get("snippet", {})
            status = video.get("status", {})
            recording = video.get("recordingDetails", {})
            shorts = video.get("shortVideoDetails", {})
            
            # Reconstruct tags back to comma-separated string format
            tags_list = snippet.get("tags", [])
            tags_str = ", ".join(tags_list) if tags_list else None
            
            # Format location coordinates back to 'lat,lon' string if they exist
            location_str = None
            if recording.get("location"):
                location_str = f"{recording['location']['latitude']},{recording['location']['longitude']}"
            
            video_entry = {
                "id": task_counter,
                "youtubeVideoId": video["id"],
                "title": snippet.get("title"),
                "description": snippet.get("description"),
                "tags": tags_str,
                "status": status.get("privacyStatus"),
                "pubDate": status.get("publishAt"),
                "location": location_str,
                "relatedVideo": shorts.get("relatedVideoId")
            }
            
            video_list.append(video_entry)
            task_counter += 1
            
        # Check if there is another page of videos to fetch
        next_page_token = playlist_response.get("nextPageToken")
        if not next_page_token:
            break
            
    return video_list


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract all uploaded YouTube videos with their full metadata attributes.")
    parser.add_argument("--token", required=True, help="Path to your JSON channel token")
    parser.add_argument("--output", required=False, help="Optional filename to dump results as a JSON file (e.g., channel_backup.json)")
    
    args = parser.parse_args()
    
    extracted_videos = fetch_all_videos(args.token)
    print(f"\nSuccessfully extracted {len(extracted_videos)} videos from the channel.")
    
    # If an output file is specified, export the structure directly
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(extracted_videos, f, indent=2, ensure_ascii=False)
        print(f"--> Saved metadata catalog successfully into: '{args.output}'")
    else:
        # Fallback to print an overview in the terminal if no file is requested
        print("\nPreview of latest items:")
        print(json.dumps(extracted_videos[:3], indent=2, ensure_ascii=False))