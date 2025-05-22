#!/usr/bin/python3
# compare.py
import argparse
from correlation import correlate

def initialize():
    parser = argparse.ArgumentParser(description="Compare audio files or check a single stream for looping.")
    
    # Option for live stream mode
    parser.add_argument("-l", "--live-stream", help="Single audio source (file/URL) for live stream loop check. This option is mutually exclusive with -i and -o.")
    
    # Options for standard comparison mode
    parser.add_argument("-i", "--source-file", help="Source file (required if -l is not used).")
    parser.add_argument("-o", "--target-file", help="Target file (required if -l is not used).")
    
    parser.add_argument("-s", "--sample-time", type=int, default=60, help="Seconds to sample audio file for (default: 60)")
    parser.add_argument("--delay", type=int, help="Delay in seconds between fingerprinting attempts in live stream mode. Defaults to 5 if --live-stream is used, otherwise 0.")
    
    args = parser.parse_args()

    SAMPLE_TIME = args.sample_time
    SOURCE_FILE = None
    TARGET_FILE = None
    DELAY_SECONDS = 0

    if args.live_stream:
        # If --live-stream is used, -i and -o should not be used
        if args.source_file or args.target_file:
            parser.error("Argument -l/--live-stream cannot be used with -i/--source-file or -o/--target-file.")
        SOURCE_FILE = args.live_stream
        TARGET_FILE = args.live_stream
        DELAY_SECONDS = args.delay if args.delay is not None else 5 # Default 5s for live stream
        print(f"Live stream mode: Using '{args.live_stream}' as both source and target. Delay: {DELAY_SECONDS}s.")
    else:
        # If --live-stream is not used, both -i and -o are required
        if not args.source_file or not args.target_file:
            parser.error("If -l/--live-stream is not used, both -i/--source-file and -o/--target-file are required.")
        SOURCE_FILE = args.source_file
        TARGET_FILE = args.target_file
        DELAY_SECONDS = args.delay if args.delay is not None else 0 # Default 0s for comparison
        print(f"Comparison mode: Source '{args.source_file}', Target '{args.target_file}'. Delay: {DELAY_SECONDS}s.")
    
    return SOURCE_FILE, TARGET_FILE, SAMPLE_TIME, DELAY_SECONDS

if __name__ == "__main__":
    SOURCE_FILE, TARGET_FILE, SAMPLE_TIME, DELAY_SECONDS = initialize()
    correlate(SOURCE_FILE, TARGET_FILE, SAMPLE_TIME, DELAY_SECONDS)
