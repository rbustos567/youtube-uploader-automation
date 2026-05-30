import os
import argparse
import sys
from datetime import datetime
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.http import MediaFileUpload
from geopy.geocoders import Nominatim

# Scope required for uploading, managing metadata, and setting thumbnails
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

def get_youtube_service(token_name):
    """Handles reading, validating, and refreshing the OAuth token dynamically."""
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


def progress_callback(percentage):
    """Prints the current upload status, overwriting the same line in the terminal."""
    print(f"Upload progress: {percentage}% completed...", end="\r", flush=True)


def run_resumable_upload(youtube, file_path, metadata, callback=None):
    """Executes the file upload using chunks and reports live progress status."""
    chunk_size = 1024 * 1024  # 1MB chunk size
    media = MediaFileUpload(file_path, chunksize=chunk_size, resumable=True)
    
    insert_request = youtube.videos().insert(
        part="snippet,status,recordingDetails",
        body=metadata,
        media_body=media
    )
    
    print(f"Starting transmission for: {file_path}")
    response = None
    while response is None:
        try:
            status, response = insert_request.next_chunk()
            if status and callback:
                current_percentage = int(status.progress() * 100)
                callback(current_percentage)
        except googleapiclient.errors.HttpError as e:
            if e.resp.status in [500, 502, 503, 504]:
                print("\n[Warning] Temporary Google server error. Retrying current chunk...")
            else:
                raise e

    print(f"\nTransmission finished successfully! Video ID: {response['id']}")
    return response


def upload_thumbnail_image(youtube, video_id, thumbnail_file):
    """Uploads a custom thumbnail image and links it strictly to the specified Video ID."""
    if not thumbnail_file or not os.path.exists(thumbnail_file):
        print(f"Error: Thumbnail file '{thumbnail_file}' does not exist. Skipping thumbnail step.")
        return False

    print(f"Uploading custom thumbnail '{thumbnail_file}' for video ID: {video_id}...")
    try:
        media = MediaFileUpload(thumbnail_file, mimetype="image/jpeg", resumable=True)
        request = youtube.thumbnails().set(videoId=video_id, media_body=media)
        request.execute()
        print("--> Custom thumbnail successfully set and matched on YouTube server!")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to upload thumbnail: {e}")
        return False


def resolve_location(location_str):
    """Helper to parse raw string into latitude and longitude coordinates."""
    if not location_str:
        return None, None
        
    lat, lon = None, None
    try:
        split_loc = location_str.split(",")
        if len(split_loc) == 2:
            lat = float(split_loc[0].strip())
            lon = float(split_loc[1].strip())
            print(f"Using direct coordinates: Lat {lat}, Lon {lon}")
            return lat, lon
    except ValueError:
        pass

    print(f"Searching coordinates for location name: '{location_str}'...")
    try:
        geolocator = Nominatim(user_agent="SBC_Youtube_Uploader_Automation")
        geo_query = geolocator.geocode(location_str)
        if geo_query:
            lat = geo_query.latitude
            lon = geo_query.longitude
            print(f"Found! Matches: '{geo_query.address}' -> Lat {lat}, Lon {lon}")
        else:
            print(f"Warning: Could not find coordinates for '{location_str}'. Skipping.")
    except Exception as e:
        print(f"Warning connecting to geocoding service: {e}. Skipping.")
        
    return lat, lon


def upload_single_video(token, video_file, title, description, tags=None, status="private", pubDate=None, location=None, relatedVideo=None, thumbnail_file=None):
    """Handles the full creation workflow for a completely new video upload."""
    if not os.path.exists(video_file):
        print(f"Error: The video file '{video_file}' does not exist.")
        return False

    tag_list = [tag.strip() for tag in tags.split(",")] if tags else []
    video_metadata = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tag_list,
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": status
        }
    }

    if pubDate:
        if status != "private":
            print("Error: To schedule a publication date, status must be strictly set to 'private'.")
            return False
        video_metadata["status"]["publishAt"] = pubDate

    lat, lon = resolve_location(location)
    if lat is not None and lon is not None:
        video_metadata["recordingDetails"] = {"location": {"latitude": lat, "longitude": lon}}

    if relatedVideo:
        video_metadata["shortVideoDetails"] = {"relatedVideoId": relatedVideo.strip()}

    try:
        youtube_service = get_youtube_service(token)
        response = run_resumable_upload(youtube_service, video_file, video_metadata, progress_callback)
        
        if response and response.get("id") and thumbnail_file:
            upload_thumbnail_image(youtube_service, response["id"], thumbnail_file)
            
        return True
    except Exception as e:
        print(f"\n[ERROR] Failed during upload process: {e}")
        return False


def update_video_metadata(token, video_id, title=None, description=None, tags=None, status=None, pubDate=None, location=None, relatedVideo=None, thumbnail_file=None):
    """Safely retrieves current metadata, updates ONLY requested fields, and pushes updates."""
    youtube = get_youtube_service(token)
    
    # Check if text/structural properties need adjustments
    metadata_changed = any([title is not None, description is not None, tags is not None, status is not None, pubDate is not None, location is not None, relatedVideo is not None])
    
    # Initialize state control flags cleanly
    text_update_success = True
    thumbnail_update_success = True

    if metadata_changed:
        print(f"Fetching current metadata for video ID: {video_id}...")
        try:
            video_response = youtube.videos().list(
                part="snippet,status,recordingDetails",
                id=video_id
            ).execute()

            if not video_response["items"]:
                print(f"Error: Video with ID '{video_id}' was not found.")
                return False

            video_data = video_response["items"][0]
            snippet = video_data["snippet"]
            video_status = video_data["status"]
            recording_details = video_data.get("recordingDetails", {})

            if title is not None:
                snippet["title"] = title
            if description is not None:
                snippet["description"] = description
            if tags is not None:
                snippet["tags"] = [tag.strip() for tag in tags.split(",")] if tags else []
            if status is not None:
                video_status["privacyStatus"] = status
            if pubDate is not None:
                if pubDate == "" or pubDate is None:
                    video_status.pop("publishAt", None)
                else:
                    current_privacy = status if status is not None else video_status["privacyStatus"]
                    if current_privacy == "private":
                        video_status["publishAt"] = pubDate
                    else:
                        print("Error: To schedule/change publication date, privacy status must be 'private'.")
                        return False

            if location is not None:
                if location == "":
                    recording_details.pop("location", None)
                else:
                    lat, lon = resolve_location(location)
                    if lat is not None and lon is not None:
                        recording_details["location"] = {"latitude": lat, "longitude": lon}

            update_body = {
                "id": video_id,
                "snippet": snippet,
                "status": video_status
            }
            if recording_details:
                update_body["recordingDetails"] = recording_details
                
            if relatedVideo is not None:
                if relatedVideo == "":
                    update_body["shortVideoDetails"] = {}
                else:
                    update_body["shortVideoDetails"] = {"relatedVideoId": relatedVideo.strip()}

            print("Pushing updated metadata to YouTube...")
            youtube.videos().update(part="snippet,status,recordingDetails", body=update_body).execute()
            print(f"--> Video '{video_id}' text metadata successfully updated!")
            text_update_success = True

        except googleapiclient.errors.HttpError as e:
            print(f"[ERROR] API error occurred during update request: {e}")
            return False

    # Process asset upload independently if requested
    if thumbnail_file:
        thumbnail_update_success = upload_thumbnail_image(youtube, video_id, thumbnail_file)

    # Return logical AND combination of both operations states
    return text_update_success and thumbnail_update_success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unified script to upload or update YouTube videos.")
    parser.add_argument("action", choices=["upload", "update"], help="Choose whether to upload a new video or update an existing one.")
    
    # Common Parameters
    parser.add_argument("--token", required=True, help="Path or filename of the target JSON token")
    parser.add_argument("--title", required=False, help="Title of the video")
    parser.add_argument("--description", required=False, help="Description of the video")
    parser.add_argument("--tags", required=False, help="Comma-separated tags")
    parser.add_argument("--status", required=False, choices=["public", "private", "unlisted"], help="Privacy status")
    parser.add_argument("--pubDate", required=False, help="Scheduled publication date in ISO 8601 format")
    parser.add_argument("--location", required=False, help="Can be a name OR coordinates")
    parser.add_argument("--relatedVideo", required=False, help="The target 11-character YouTube video ID to link")
    parser.add_argument("--thumbnailFile", required=False, help="Path to the custom cover image file")
    
    # Mode-Specific Parameters
    parser.add_argument("--videoFile", required=False, help="Full or relative path to the video file (Required for 'upload')")
    parser.add_argument("--id", required=False, help="The 11-character YouTube video ID to edit (Required for 'update')")

    args = parser.parse_args()

    if args.action == "upload":
        if not args.videoFile or not args.title or not args.description or not args.status:
            print("Error: In 'upload' mode, --videoFile, --title, --description, and --status are strictly required.")
            sys.exit(1)
            
        upload_single_video(
            token=args.token, video_file=args.videoFile, title=args.title, description=args.description,
            tags=args.tags, status=args.status, pubDate=args.pubDate, location=args.location, 
            relatedVideo=args.relatedVideo, thumbnail_file=args.thumbnailFile
        )
        
    elif args.action == "update":
        if not args.id:
            print("Error: In 'update' mode, the --id argument (YouTube Video ID) is strictly required.")
            sys.exit(1)
        if not any([args.title is not None, args.description is not None, args.tags is not None, args.status is not None, args.pubDate is not None, args.location is not None, args.relatedVideo is not None, args.thumbnailFile is not None]):
            print("Error: Provide at least one modification parameter field when executing an 'update'.")
            sys.exit(1)
            
        update_video_metadata(
            token=args.token, video_id=args.id, title=args.title, description=args.description,
            tags=args.tags, status=args.status, pubDate=args.pubDate, location=args.location, 
            relatedVideo=args.relatedVideo, thumbnail_file=args.thumbnailFile
        )