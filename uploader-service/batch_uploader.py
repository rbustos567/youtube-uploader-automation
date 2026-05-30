import os
import json
import sys
import argparse
# Import both lifecycles from your unified core engine script
from upload_or_update_video import upload_single_video, update_video_metadata

def load_video_queue(json_path):
    """Loads the JSON file and returns a structured list of video dictionaries."""
    if not os.path.exists(json_path):
        print(f"Error: The queue file '{json_path}' was not found.")
        sys.exit(1)
        
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            queue_data = json.load(f)
            print(f"--> Successfully loaded queue with {len(queue_data)} items.")
            return queue_data
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON structure: {e}")
        sys.exit(1)

def save_video_queue(json_path, queue_data):
    """Overwrites the source JSON file with the updated execution status metadata."""
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(queue_data, f, indent=2, ensure_ascii=False)
        print(f"\n--> Successfully updated queue state file: '{json_path}'")
    except Exception as e:
        print(f"\n[CRITICAL ERROR] Could not write updates back to JSON file: {e}")

def process_queue(queue, file_path):
    """Iterates over the items, modifies statuses in-memory based on runtime success, and persists results."""
    total_tasks = len(queue)
    successful_runs = 0
    failed_runs = 0
    skipped_runs = 0
    
    for index, item in enumerate(queue, start=1):
        task_id = item.get("id", index)
        action = item.get("action")
        token = item.get("token")
        execution_status = item.get("executionStatus", "pending").strip().lower()
        
        # Display fallback text in logs if the title isn't part of an update payload
        log_title = item.get("title", f"[Fields modification block for ID: {item.get('videoId', 'unknown')}]")
        
        print("\n" + "="*60)
        print(f"Processing Task [{index}/{total_tasks}] - ID: {task_id} | Action: {action.upper() if action else 'NONE'}")
        print(f"Target/Log Name: {log_title}")
        print("="*60)
        
        # Rule to skip items marked manually or previously as completed
        if execution_status == "completed":
            print(f"[SKIP] Task ID {task_id} is already 'completed'. Skipping execution.")
            skipped_runs += 1
            continue
            
        if not token:
            print(f"[SKIP] Task ID {task_id} failed: '--token' field is missing in JSON item layout.")
            item["executionStatus"] = "pending"
            failed_runs += 1
            continue

        success = False

        if action == "upload":
            video_file = item.get("videoFile")
            if not video_file:
                print(f"[SKIP] Task ID {task_id} failed: 'videoFile' is strictly required for upload actions.")
                item["executionStatus"] = "pending"
                failed_runs += 1
                continue
                
            success = upload_single_video(
                token=token,
                video_file=video_file,
                title=item.get("title", "Untitled Video"),
                description=item.get("description", ""),
                tags=item.get("tags"),
                status=item.get("status", "private"),
                pubDate=item.get("pubDate"),
                location=item.get("location"),
                relatedVideo=item.get("relatedVideo"),
                thumbnail_file=item.get("thumbnailFile") # Injected mapping
            )
            
        elif action == "update":
            video_id = item.get("videoId")
            if not video_id:
                print(f"[SKIP] Task ID {task_id} failed: 'videoId' (11-chars) is strictly required for update actions.")
                item["executionStatus"] = "pending"
                failed_runs += 1
                continue
                
            # Double check if there is at least one modification parameter declared in the object layout
            has_keys = any(k in item for k in ["title", "description", "tags", "status", "pubDate", "location", "relatedVideo", "thumbnailFile"])
            if not has_keys:
                print(f"[SKIP] Task ID {task_id} failed: No fields or thumbnail assets were specified to alter.")
                item["executionStatus"] = "pending"
                failed_runs += 1
                continue

            success = update_video_metadata(
                token=token,
                video_id=video_id,
                title=item.get("title"), 
                description=item.get("description"),
                tags=item.get("tags"),
                status=item.get("status"),
                pubDate=item.get("pubDate"),
                location=item.get("location"),
                relatedVideo=item.get("relatedVideo"),
                thumbnail_file=item.get("thumbnailFile") # Injected mapping
            )
            
        else:
            print(f"[SKIP] Task ID {task_id} failed: Invalid action '{action}'. Supported values are 'upload' or 'update'.")
            item["executionStatus"] = "pending"
            failed_runs += 1
            continue

        # Post-execution evaluation and in-memory dict mutations
        if success:
            print(f"--> Task ID {task_id} finished processing successfully!")
            item["executionStatus"] = "completed"  # Mutate state to completed
            successful_runs += 1
        else:
            print(f"[ERROR] Task ID {task_id} execution failed during runtime lifecycle.")
            item["executionStatus"] = "pending"    # Enforce pending state for retries
            failed_runs += 1

    # --- END OF LOOP: STATE PERSISTENCE ---
    print("\n" + "="*60)
    print("QUEUE SUMMARY REPORT")
    print("="*60)
    print(f"Total processed elements: {total_tasks}")
    print(f"  - Successful tasks:     {successful_runs}")
    print(f"  - Failed/Pending tasks:  {failed_runs}")
    print(f"  - Skipped items:         {skipped_runs}")
    
    save_video_queue(file_path, queue)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch management pipeline supporting conditional video uploads and updates based on completion flags.")
    parser.add_argument("--file", required=True, help="Path to the target JSON batch configuration layout.")
    
    args = parser.parse_args()
    
    print("Starting Multi-Action Batch Queue Pipeline...")
    video_queue = load_video_queue(args.file)
    
    process_queue(video_queue, args.file)
    print("\nAll tasks in the queue deployment have been evaluated.")