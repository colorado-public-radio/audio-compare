#!/usr/bin/python3
# compare.py
import argparse
import sys # For sys.exit
import subprocess # To catch subprocess.CalledProcessError specifically
from correlation import correlate

def initialize():
    parser = argparse.ArgumentParser(description="Compare audio files or check a single stream for looping. Optionally outputs Nagios-compatible status.")
    
    parser.add_argument("-l", "--live-stream", help="Single audio source (file/URL) for live stream loop check. This option is mutually exclusive with -i and -o.")
    parser.add_argument("-i", "--source-file", help="Source file (required if -l is not used).")
    parser.add_argument("-o", "--target-file", help="Target file (required if -l is not used).")
    parser.add_argument("-s", "--sample-time", type=int, default=60, help="Seconds to sample audio file for (default: 60)")
    parser.add_argument("--delay", type=int, help="Delay in seconds between fingerprinting attempts in live stream mode. Defaults to 5 if --live-stream is used, otherwise 0.")
    
    # Nagios options
    parser.add_argument("-w", "--warn", type=float, help="Warning threshold for similarity percentage (e.g., 70 for 70%%). Requires -c.")
    parser.add_argument("-c", "--critical", type=float, help="Critical threshold for similarity percentage (e.g., 90 for 90%%). Requires -w.")
    
    args = parser.parse_args()

    SAMPLE_TIME = args.sample_time
    SOURCE_FILE = None
    TARGET_FILE = None
    DELAY_SECONDS = 0
    WARN_PERCENT = args.warn
    CRITICAL_PERCENT = args.critical

    # Validate Nagios thresholds
    if (WARN_PERCENT is not None and CRITICAL_PERCENT is None) or \
       (WARN_PERCENT is None and CRITICAL_PERCENT is not None):
        parser.error("Both --warn (-w) and --critical (-c) thresholds must be provided together, or neither.")
    if WARN_PERCENT is not None and CRITICAL_PERCENT is not None:
        if WARN_PERCENT >= CRITICAL_PERCENT:
            parser.error("--warn threshold must be less than --critical threshold.")

    if args.live_stream:
        if args.source_file or args.target_file:
            parser.error("Argument -l/--live-stream cannot be used with -i/--source-file or -o/--target-file.")
        SOURCE_FILE = args.live_stream
        TARGET_FILE = args.live_stream
        DELAY_SECONDS = args.delay if args.delay is not None else 5
        print(f"Live stream mode: Using '{args.live_stream}' as both source and target. Sample: {SAMPLE_TIME}s, Delay: {DELAY_SECONDS}s.")
    else:
        if not args.source_file or not args.target_file:
            parser.error("If -l/--live-stream is not used, both -i/--source-file and -o/--target-file are required.")
        SOURCE_FILE = args.source_file
        TARGET_FILE = args.target_file
        DELAY_SECONDS = args.delay if args.delay is not None else 0
        print(f"Comparison mode: Source '{args.source_file}', Target '{args.target_file}'. Sample: {SAMPLE_TIME}s, Delay: {DELAY_SECONDS}s.")
    
    return SOURCE_FILE, TARGET_FILE, SAMPLE_TIME, DELAY_SECONDS, WARN_PERCENT, CRITICAL_PERCENT

if __name__ == "__main__":
    NAGIOS_OK = 0
    NAGIOS_WARNING = 1
    NAGIOS_CRITICAL = 2
    NAGIOS_UNKNOWN = 3
    GENERAL_ERROR = 1

    exit_code = NAGIOS_OK # Default exit code

    # Catch arg parsing errors early (though argparse usually exits by itself)
    try:
        SOURCE_FILE, TARGET_FILE, SAMPLE_TIME, DELAY_SECONDS, WARN_PERCENT, CRITICAL_PERCENT = initialize()
    except SystemExit as e: # Raised by parser.error()
        sys.exit(e.code if e.code is not None else GENERAL_ERROR) # argparse uses 2 for errors
    except Exception as e:
        print(f"Error during initialization: {e}", file=sys.stderr)
        sys.exit(NAGIOS_UNKNOWN if (hasattr(args, 'warn') and args.warn is not None) else GENERAL_ERROR)


    similarity_percentage = None
    try:
        similarity_percentage = correlate(SOURCE_FILE, TARGET_FILE, SAMPLE_TIME, DELAY_SECONDS)
    except FileNotFoundError as e: # Specifically for fpcalc not being found
        # This exception should ideally be caught and handled within 'correlate'
        # or 'calculate_fingerprints' returning None, but as a fallback:
        print(f"Error: Prerequisite 'fpcalc' not found or file system issue: {e}", file=sys.stderr)
        if WARN_PERCENT is not None and CRITICAL_PERCENT is not None:
            print(f"UNKNOWN: fpcalc not found. |'similarity'=U")
            exit_code = NAGIOS_UNKNOWN
        else:
            exit_code = GENERAL_ERROR
        sys.exit(exit_code)
    except subprocess.CalledProcessError as e: # If fpcalc fails
        print(f"Error: fpcalc execution failed. CMD: {e.cmd}, RC: {e.returncode}", file=sys.stderr)
        if WARN_PERCENT is not None and CRITICAL_PERCENT is not None:
            print(f"UNKNOWN: fpcalc execution failed. |'similarity'=U")
            exit_code = NAGIOS_UNKNOWN
        else:
            exit_code = GENERAL_ERROR
        sys.exit(exit_code)
    except Exception as e:
        # Catch any other unexpected error during correlation
        print(f"An unexpected error occurred during correlation: {e}", file=sys.stderr)
        if WARN_PERCENT is not None and CRITICAL_PERCENT is not None:
            print(f"UNKNOWN: Unexpected error during correlation. |'similarity'=U")
            exit_code = NAGIOS_UNKNOWN
        else:
            exit_code = GENERAL_ERROR
        sys.exit(exit_code)


    if WARN_PERCENT is not None and CRITICAL_PERCENT is not None:
        # Nagios thresholds are active
        if similarity_percentage is None:
            # correlate function already printed specific errors
            print(f"UNKNOWN: Could not determine similarity percentage. Check previous messages. |'similarity'=U")
            exit_code = NAGIOS_UNKNOWN
        else:
            perf_data = f"|'similarity'={similarity_percentage:.2f};{WARN_PERCENT};{CRITICAL_PERCENT};0;100"
            if similarity_percentage >= CRITICAL_PERCENT:
                print(f"CRITICAL: Similarity is {similarity_percentage:.2f}% (Threshold: >={CRITICAL_PERCENT}%) {perf_data}")
                exit_code = NAGIOS_CRITICAL
            elif similarity_percentage >= WARN_PERCENT:
                print(f"WARNING: Similarity is {similarity_percentage:.2f}% (Threshold: >={WARN_PERCENT}%) {perf_data}")
                exit_code = NAGIOS_WARNING
            else:
                print(f"OK: Similarity is {similarity_percentage:.2f}% {perf_data}")
                exit_code = NAGIOS_OK
    else:
        # No Nagios thresholds, standard behavior
        if similarity_percentage is None:
            # correlate() would have printed an error. Indicate failure.
            exit_code = GENERAL_ERROR
        # else: successful run, detailed output already printed by correlation.py. exit_code remains NAGIOS_OK (0)

    sys.exit(exit_code)
