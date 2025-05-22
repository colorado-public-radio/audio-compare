#!/usr/bin/python3

# correlation.py
import subprocess
import numpy
import os
import time
import sys # For stderr

# REMOVE: sample_time = 60 # This global variable is no longer needed

# number of points to scan cross correlation over
span = 150
# step size (in points) of cross correlation
step = 1
# minimum number of points that must overlap in cross correlation
# exception is raised if this cannot be met
min_overlap = 20
# report match when cross correlation has a peak exceeding threshold
# This threshold is for the script's own definition of a "match"
# Not to be confused with Nagios thresholds.
internal_script_threshold = 0.5 

def calculate_fingerprints(filename, sample_time_param):
    # This function will raise FileNotFoundError if fpcalc is not found,
    # or subprocess.CalledProcessError if fpcalc fails on an existing file.
    # These should be caught by the caller ('correlate')
    if os.path.exists(filename + '.fpcalc'):
        print(f"Found precalculated fingerprint for {filename}")
        with open(filename + '.fpcalc', "r") as f:
            fpcalc_out = ''.join(f.readlines())
    else:
        print(f"Calculating fingerprint by fpcalc for {filename} (sample time: {sample_time_param}s)")
        # This can raise FileNotFoundError (if fpcalc not found) or CalledProcessError
        fpcalc_out = subprocess.check_output(
            ['fpcalc', '-raw', '-length', str(sample_time_param), filename],
            text=True, stderr=subprocess.PIPE # Capture stderr for better error reporting
        )
        fpcalc_out = fpcalc_out.strip().replace('\\n', '')


    fingerprint_index = fpcalc_out.find('FINGERPRINT=')
    if fingerprint_index == -1:
        print(f"Error: 'FINGERPRINT=' not found in fpcalc output for {filename}.", file=sys.stderr)
        print(f"fpcalc output was: {fpcalc_out}", file=sys.stderr)
        return [] # Return empty list indicating failure

    fingerprint_str = fpcalc_out[fingerprint_index + 12:]
    if not fingerprint_str:
        print(f"Error: Fingerprint string is empty after 'FINGERPRINT=' for {filename}.", file=sys.stderr)
        return []
        
    try:
        fingerprints = list(map(int, fingerprint_str.split(',')))
    except ValueError:
        print(f"Error: Could not convert fingerprint to list of integers for {filename}. String was: '{fingerprint_str}'", file=sys.stderr)
        return []
    return fingerprints

def correlation(listx, listy):
    if not listx or not listy:
        # This should ideally not be reached if fingerprints are checked beforehand
        print("Error: Empty lists cannot be correlated.", file=sys.stderr)
        return 0.0 # Return a neutral value, or handle as error higher up

    len_x, len_y = len(listx), len(listy)
    if len_x > len_y:
        listx = listx[:len_y]
    elif len_x < len_y:
        listy = listy[:len_x]

    # After truncation, lists are of the same length
    # If one was empty, it might still be empty here.
    if not listx: # or not listy, since they'd be same length or one was initially empty
        return 0.0

    covariance = 0
    for i in range(len(listx)):
        covariance += 32 - bin(listx[i] ^ listy[i]).count("1")
    
    return (covariance / float(len(listx))) / 32.0

def cross_correlation(listx, listy, offset):
    temp_listx = listx
    temp_listy = listy
    if offset > 0:
        temp_listx = temp_listx[offset:]
        temp_listy = temp_listy[:len(temp_listx)]
    elif offset < 0:
        offset_abs = -offset
        temp_listy = temp_listy[offset_abs:]
        temp_listx = temp_listx[:len(temp_listy)]
    
    if min(len(temp_listx), len(temp_listy)) < min_overlap:
        return None # Not enough overlap
    return correlation(temp_listx, temp_listy)

def compare_fingerprints(listx, listy, span_val, step_val): # Renamed from 'compare' to avoid conflict
    if not listx or not listy:
        print("Error: Cannot compare empty fingerprints.", file=sys.stderr)
        return []
    if span_val > min(len(listx), len(listy)):
        # This indicates an issue with parameters or very short fingerprints
        print(f"Warning: span ({span_val}) >= sample size (min_len: {min(len(listx), len(listy))}). "
              f"Reduce span or increase sample_time.", file=sys.stderr)
        # Depending on severity, could return empty or try to adjust span.
        # For now, let it proceed, cross_correlation might handle small overlaps.
        # Or, more strictly:
        # return [] # Indicate comparison cannot be meaningfully performed.
        pass # Let cross_correlation handle small overlaps if any

    corr_xy = []
    for offset_val in numpy.arange(-span_val, span_val + 1, step_val):
        corr_xy.append(cross_correlation(listx, listy, int(offset_val)))
    return corr_xy

def get_max_corr(corr_values, source, target):
    # This function now focuses on calculating and printing results,
    # and returns the percentage or None.
    # Nagios status interpretation is handled in compare.py.

    if not corr_values or not any(c is not None for c in corr_values):
        print(f"Info: No valid correlation values found between {source} and {target} (e.g., due to small overlap or empty fingerprints).")
        return None

    valid_corr_values = [c for c in corr_values if c is not None]
    if not valid_corr_values: # Should be caught by the check above, but as a safeguard
        print(f"Info: No valid correlation values after filtering Nones for {source} and {target}.")
        return None
        
    max_val_in_valid = 0.0
    try:
        max_val_in_valid = max(valid_corr_values)
    except ValueError: # Should not happen if valid_corr_values is not empty
        print(f"Info: Could not determine maximum from valid correlation values for {source} and {target}.")
        return None

    max_corr_index = -1
    for i, value in enumerate(corr_values):
        if value == max_val_in_valid: # Compare float values
            max_corr_index = i
            break
    
    if max_corr_index == -1: # Should not happen if max_val_in_valid was found from the list
        print(f"Info: Could not determine index of maximum correlation for {source} and {target}.")
        return None

    max_corr_offset = -span + max_corr_index * step
    current_similarity_percent = corr_values[max_corr_index] * 100.0

    # Standard script output:
    print(f"--- Correlation Result ---")
    print(f"File A: {source}")
    print(f"File B: {target}")
    if corr_values[max_corr_index] >= internal_script_threshold:
        print(f"Match: Similarity of {current_similarity_percent:.2f}% at offset {max_corr_offset} (Internal Threshold: {internal_script_threshold*100:.2f}%)")
    else:
        print(f"No strong match: Highest similarity is {current_similarity_percent:.2f}% at offset {max_corr_offset} (Internal Threshold: {internal_script_threshold*100:.2f}%)")
    
    return current_similarity_percent


def correlate(source, target, sample_time_param, delay_seconds):
    fingerprint_source = []
    fingerprint_target = []

    try:
        fingerprint_source = calculate_fingerprints(source, sample_time_param)
        if not fingerprint_source: # calculate_fingerprints printed the error
            return None

        if source == target and delay_seconds > 0:
            print(f"Live stream mode: Delaying for {delay_seconds} seconds before next fingerprint capture...")
            time.sleep(delay_seconds)
            print(f"Recalculating fingerprint for {target} after delay.")

        fingerprint_target = calculate_fingerprints(target, sample_time_param)
        if not fingerprint_target: # calculate_fingerprints printed the error
            return None

    except FileNotFoundError as e: # Specific to fpcalc command not found
        print(f"Error: The 'fpcalc' command was not found. Please ensure Chromaprint/fpcalc is installed and in your system's PATH. Details: {e}", file=sys.stderr)
        raise # Re-raise for compare.py to handle specific exit code
    except subprocess.CalledProcessError as e:
        print(f"Error: fpcalc failed. Command '{e.cmd}' returned non-zero exit status {e.returncode}.", file=sys.stderr)
        if e.stdout:
            print(f"fpcalc stdout:\n{e.stdout}", file=sys.stderr)
        if e.stderr:
            print(f"fpcalc stderr:\n{e.stderr}", file=sys.stderr)
        raise # Re-raise for compare.py to handle specific exit code
    except Exception as e: # Catch any other unexpected error during fingerprinting
        print(f"Error: An unexpected issue occurred during fingerprint calculation: {e}", file=sys.stderr)
        return None # General failure to get fingerprints


    if not fingerprint_source or not fingerprint_target:
        # This case should be covered if calculate_fingerprints returns [] and it's checked.
        print(f"Error: Cannot compare due to one or both fingerprints being empty. Source items: {len(fingerprint_source)}, Target items: {len(fingerprint_target)}", file=sys.stderr)
        return None

    try:
        # Renamed 'compare' to 'compare_fingerprints' to avoid conflict with a variable
        corr_values = compare_fingerprints(fingerprint_source, fingerprint_target, span, step)
        if not corr_values: # If compare_fingerprints determined it couldn't proceed (e.g. span issue leading to empty results)
            # compare_fingerprints should print its own warning/error
            return None
    except Exception as e:
        print(f"Error during fingerprint comparison process: {e}", file=sys.stderr)
        # (e.g. span vs sample size if not handled in compare_fingerprints explicitly)
        print(f"Details: Fingerprint source length: {len(fingerprint_source)}, Target length: {len(fingerprint_target)}, Span: {span}", file=sys.stderr)
        return None

    return get_max_corr(corr_values, source, target)
