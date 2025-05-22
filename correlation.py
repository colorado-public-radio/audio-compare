#!/usr/bin/python3

# correlation.py
import subprocess
import numpy
import os
import time
import sys # For stderr
import tempfile # For temporary files for HLS processing
import shutil # For shutil.which to check for ffmpeg

# Global constants from your script
span = 150
step = 1
min_overlap = 20
internal_script_threshold = 0.5

def is_hls_stream(filename_url):
    """Checks if the filename/URL likely points to an HLS stream."""
    fn_lower = filename_url.lower()
    return fn_lower.endswith('.m3u8') or "manifest.m3u8" in fn_lower

def calculate_fingerprints(filename, sample_time_param):
    original_input_path = filename # Keep original for error messages
    temp_hls_processed_file_path = None # Path to the file created by ffmpeg for HLS
    is_hls = is_hls_stream(filename)
    fpcalc_input_path = filename # Path to be fed to fpcalc

    fingerprints = []

    try:
        if is_hls:
            if not shutil.which("ffmpeg"):
                print("Error: ffmpeg command not found. ffmpeg is required to process HLS streams.", file=sys.stderr)
                raise FileNotFoundError("ffmpeg command not found, required for HLS processing.")

            print(f"HLS stream detected: {original_input_path}. Processing with ffmpeg for {sample_time_param} seconds.")
            
            # Create a temporary file for ffmpeg to write to. Suffix .wav is good for fpcalc.
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile_obj:
                temp_hls_processed_file_path = tmpfile_obj.name
            
            # ffmpeg command to capture 'sample_time_param' seconds of audio from HLS
            # and convert it to mono WAV PCM s16le, which is robust for fpcalc.
            ffmpeg_command = [
                'ffmpeg',
                '-y',  # Overwrite output file if it exists
                '-i', original_input_path,  # Input HLS URL
                '-t', str(sample_time_param),  # Duration to process
                '-vn',  # Disable video recording
                '-acodec', 'pcm_s16le',  # Audio codec: PCM signed 16-bit little-endian
                '-ar', '44100',  # Audio sample rate: 44.1kHz
                '-ac', '1',  # Audio channels: 1 (mono)
                temp_hls_processed_file_path
            ]
            
            print(f"Executing ffmpeg: {' '.join(ffmpeg_command)}")
            try:
                # Run ffmpeg. check=True will raise CalledProcessError on failure.
                result = subprocess.run(ffmpeg_command, check=True, capture_output=True, text=True)
                # ffmpeg often prints useful info to stderr, even on success.
                # if result.stderr:
                #     print(f"ffmpeg messages:\n{result.stderr.strip()}", file=sys.stderr) # Can be verbose
                print(f"ffmpeg successfully processed HLS stream into {temp_hls_processed_file_path}")
                fpcalc_input_path = temp_hls_processed_file_path # fpcalc will use this temp file
            except subprocess.CalledProcessError as e:
                print(f"Error: ffmpeg failed to process HLS stream '{original_input_path}'.", file=sys.stderr)
                print(f"ffmpeg command: {' '.join(e.cmd)}", file=sys.stderr)
                if e.stdout: print(f"ffmpeg stdout:\n{e.stdout.strip()}", file=sys.stderr)
                if e.stderr: print(f"ffmpeg stderr:\n{e.stderr.strip()}", file=sys.stderr)
                raise # Re-raise the error to be caught by the caller (correlate function)
            except FileNotFoundError: # Should be caught by shutil.which, but defense-in-depth
                print(f"Error: ffmpeg command not found during HLS processing attempt (should have been caught earlier).", file=sys.stderr)
                raise


        # Fingerprinting part (common for both HLS temp files and regular files)
        fpcalc_out = ""
        # Caching is only applicable for non-HLS, non-temporary files
        can_use_cache = not is_hls and os.path.exists(fpcalc_input_path + '.fpcalc')

        if can_use_cache:
            print(f"Found precalculated fingerprint for {fpcalc_input_path}")
            with open(fpcalc_input_path + '.fpcalc', "r") as f:
                fpcalc_out = f.read()
        else:
            if is_hls:
                print(f"Calculating fingerprint using fpcalc for HLS temp file (from {original_input_path})")
            else:
                print(f"Calculating fingerprint by fpcalc for {fpcalc_input_path} (sample time: {sample_time_param}s)")

            fpcalc_command = ['fpcalc', '-raw', '-length', str(sample_time_param), fpcalc_input_path]
            # print(f"Executing fpcalc: {' '.join(fpcalc_command)}") # Optional: for more verbosity
            
            # fpcalc execution (can also raise FileNotFoundError or CalledProcessError)
            fpcalc_result = subprocess.run(fpcalc_command, check=True, capture_output=True, text=True)
            fpcalc_out = fpcalc_result.stdout.strip().replace('\\n', '')

        fingerprint_index = fpcalc_out.find('FINGERPRINT=')
        if fingerprint_index == -1:
            print(f"Error: 'FINGERPRINT=' not found in fpcalc output for '{original_input_path}'.", file=sys.stderr)
            # print(f"fpcalc output was:\n{fpcalc_out}", file=sys.stderr) # Can be very long
            return []

        fingerprint_str = fpcalc_out[fingerprint_index + 12:]
        if not fingerprint_str:
            print(f"Error: Fingerprint string is empty after 'FINGERPRINT=' for '{original_input_path}'.", file=sys.stderr)
            return []
            
        try:
            fingerprints = list(map(int, fingerprint_str.split(',')))
        except ValueError:
            print(f"Error: Could not convert fingerprint to list of integers for '{original_input_path}'. String was: '{fingerprint_str}'", file=sys.stderr)
            return []
            
    finally:
        # Cleanup the temporary file created by ffmpeg, if any
        if temp_hls_processed_file_path and os.path.exists(temp_hls_processed_file_path):
            # print(f"Cleaning up temporary HLS file: {temp_hls_processed_file_path}") # Optional
            try:
                os.remove(temp_hls_processed_file_path)
            except OSError as e:
                print(f"Warning: Could not remove temporary file {temp_hls_processed_file_path}: {e}", file=sys.stderr)
                
    return fingerprints

# Functions correlation, cross_correlation, compare_fingerprints, get_max_corr, correlate remain the same
# but the 'correlate' function's try-except block (or the one in compare.py)
# will now also catch FileNotFoundError or CalledProcessError if ffmpeg is missing or fails.

# ... (rest of your correlation.py, including correlation, cross_correlation, 
#      compare_fingerprints, get_max_corr, and correlate functions) ...

# Ensure these functions are present from your previous version:
def correlation(listx, listy):
    if not listx or not listy:
        return 0.0
    len_x, len_y = len(listx), len(listy)
    if len_x > len_y: listx = listx[:len_y]
    elif len_x < len_y: listy = listy[:len_x]
    if not listx: return 0.0
    covariance = sum(32 - bin(x ^ y).count("1") for x, y in zip(listx, listy))
    return (covariance / float(len(listx))) / 32.0

def cross_correlation(listx, listy, offset):
    temp_listx, temp_listy = listx, listy
    if offset > 0:
        temp_listx = temp_listx[offset:]
        temp_listy = temp_listy[:len(temp_listx)]
    elif offset < 0:
        temp_listy = temp_listy[abs(offset):]
        temp_listx = temp_listx[:len(temp_listy)]
    if min(len(temp_listx), len(temp_listy)) < min_overlap: return None
    return correlation(temp_listx, temp_listy)

def compare_fingerprints(listx, listy, span_val, step_val):
    if not listx or not listy: return []
    corr_xy = []
    for offset_val in numpy.arange(-span_val, span_val + 1, step_val):
        corr_xy.append(cross_correlation(listx, listy, int(offset_val)))
    return corr_xy

def get_max_corr(corr_values, source, target):
    if not corr_values or not any(c is not None for c in corr_values):
        print(f"Info: No valid correlation values found between {source} and {target}.")
        return None
    valid_corr_values = [c for c in corr_values if c is not None]
    if not valid_corr_values:
        print(f"Info: No valid correlation values after filtering Nones for {source} and {target}.")
        return None
    max_val_in_valid = max(valid_corr_values)
    max_corr_index = next(i for i, v in enumerate(corr_values) if v == max_val_in_valid)
    max_corr_offset = -span + max_corr_index * step
    current_similarity_percent = corr_values[max_corr_index] * 100.0
    print(f"--- Correlation Result ---")
    print(f"File A: {source}")
    print(f"File B: {target}")
    match_type = "Match" if corr_values[max_corr_index] >= internal_script_threshold else "No strong match"
    print(f"{match_type}: Similarity of {current_similarity_percent:.2f}% at offset {max_corr_offset} (Internal Threshold: {internal_script_threshold*100:.2f}%)")
    return current_similarity_percent

def correlate(source, target, sample_time_param, delay_seconds):
    fingerprint_source, fingerprint_target = [], []
    try:
        fingerprint_source = calculate_fingerprints(source, sample_time_param)
        if not fingerprint_source: return None
        if source == target and delay_seconds > 0:
            print(f"Live stream mode: Delaying for {delay_seconds} seconds...")
            time.sleep(delay_seconds)
            print(f"Recalculating fingerprint for {target} after delay.")
        fingerprint_target = calculate_fingerprints(target, sample_time_param)
        if not fingerprint_target: return None
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        # These are re-raised by calculate_fingerprints if ffmpeg/fpcalc setup is problematic
        # or if they exit with an error.
        # compare.py's main try-except will catch this.
        print(f"Error during fingerprint calculation phase: {e}", file=sys.stderr)
        raise # Re-raise to be handled by the top-level error handler in compare.py
    except Exception as e:
        print(f"Unexpected error during fingerprint calculation: {e}", file=sys.stderr)
        return None # For other unexpected issues within this scope

    if not fingerprint_source or not fingerprint_target:
        print(f"Error: One or both fingerprints are empty. Source: {len(fingerprint_source)}, Target: {len(fingerprint_target)}", file=sys.stderr)
        return None
    try:
        corr_values = compare_fingerprints(fingerprint_source, fingerprint_target, span, step)
        if not corr_values: return None
    except Exception as e:
        print(f"Error during fingerprint comparison: {e}", file=sys.stderr)
        return None
    return get_max_corr(corr_values, source, target)
