import os
import sys
import json
import argparse
import requests

def parse_arguments():
    parser = argparse.ArgumentParser(description="SkyClouds4K - Metadata Enrichment Lifecycle")
    parser.add_argument("--input", required=True, help="Path to the minimal input JSON file")
    parser.add_argument("--output", required=True, help="Path to save the enriched output JSON file")
    parser.add_argument("--prompt-file", required=True, help="Path to the system prompt text file")
    parser.add_argument("--ollama", required=True, help="Ollama host address (e.g., ollama-service:11434)")
    parser.add_argument("--model", default="gemma2:9b", help="Ollama LLM model tag to use")
    return parser.parse_args()

def main():
    print("==================================================")
    print("Executing Pipeline Metadata Enrichment Phase...")
    print("==================================================")
    
    args = parse_arguments()

    # Verify that required source assets exist
    if not os.path.exists(args.input) or not os.path.exists(args.prompt_file):
        print("[ERROR] Required input files are missing.")
        sys.exit(1)

    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            queue_data = json.load(f)
    except Exception as e:
        print(f"[ERROR] Failed to parse input JSON queue: {e}")
        sys.exit(1)

    # Filter pending workflow tasks strictly using executionStatus
    pending_videos = [item for item in queue_data if item.get("executionStatus") not in ["completed", "enriched"]]

    if not pending_videos:
        print("[INFO] Queue Status: EMPTY. No new items to process.")
        sys.exit(99)

    with open(args.prompt_file, 'r', encoding='utf-8') as f:
        system_prompt = f.read().strip()

    ollama_url = f"http://{args.ollama}/api/generate"
    
    for item in queue_data:
        # Skip items that are already processed or successfully uploaded
        if item.get("executionStatus") in ["completed", "enriched"]:
            continue
            
        print(f"--> Checking Metadata for Task ID: {item.get('id')} - File: {item.get('videoFile')}")
        
        # IDEMPOTENCY SHIELD: If metadata exists from a failed upload attempt, reuse it and bypass Ollama
        if item.get("title") and item.get("description"):
            print(f"    [RECOVERY] Task ID {item.get('id')} already contains generated metadata. Re-using assets and skipping LLM inference.")
            item["executionStatus"] = "enriched"
            continue
        
        # Process genuinely new entries through the local LLM instance
        print(f"    --> Optimizing SEO metadata via Ollama...")
        user_prompt = f"Context: {item.get('raw_context')}. Extra tags: {item.get('tags')}."
        
        payload = {
            "model": args.model,
            "prompt": f"{system_prompt}\n\nInput Reference:\n{user_prompt}",
            "stream": False,
            "format": "json" # Force Ollama to return a clean, unescaped JSON structure
        }
        
        try:
            response = requests.post(ollama_url, json=payload, timeout=300)
            if response.status_code == 200:
                result = response.json()
                ai_output_raw = result.get("response", "").strip()
                
                # Parse the raw string response from the LLM into a dictionary
                ai_data = json.loads(ai_output_raw)
                
                # Inject values directly into the root level for the batch_uploader block
                item["title"] = ai_data.get("title", "SkyClouds4K - Video Showcase")
                item["description"] = ai_data.get("description", "")
                
                if "tags" in ai_data:
                    if isinstance(ai_data["tags"], list):
                        item["tags"] = ", ".join(ai_data["tags"])
                    else:
                        item["tags"] = ai_data["tags"]

                # Shift state to enriched so the uploader registers the asset
                item["executionStatus"] = "enriched"
                print(f"    [SUCCESS] Metadata extracted and injected into root schema successfully.")
            else:
                print(f"[ERROR] Ollama gateway returned status code {response.status_code}")
                sys.exit(1)
                
        except json.JSONDecodeError:
            print("    [WARN] AI payload response was not valid JSON. Applying raw string fallback routine.")
            item["title"] = "SkyClouds4K Timelapse Showcase"
            item["description"] = ai_output_raw
            item["executionStatus"] = "enriched"
        except Exception as e:
            print(f"[ERROR] Network connection to Ollama cluster failed: {e}")
            sys.exit(1)

    # Commit structural pipeline modifications back to disk storage
    try:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(queue_data, f, indent=4, ensure_ascii=False)
        print(f"\n[INFO] Enriched state deployment saved successfully to '{args.output}'.")
    except Exception as e:
        print(f"[ERROR] Failed to update and write output JSON payload: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()