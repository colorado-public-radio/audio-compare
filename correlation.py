#!/usr/bin/python3

# correlation.py
import subprocess
import numpy
import os
import time # Added for the delay functionality

# REMOVE: sample_time = 60 # This global variable is no longer needed

# number of points to scan cross correlation over
span = 150
# step size (in points) of cross correlation
step = 1
# minimum number of points that must overlap in cross correlation
# exception is raised if this cannot be met
min_overlap = 20
# report match when cross correlation has a peak exceeding threshold
threshold = 0.5

# calculate fingerprint
# Generate file.mp3.fpcalc by "fpcalc -raw -length 500 file.mp3"
def calculate_fingerprints(filename, sample_time_param): # Add sample_time_param as a parameter
    if os.path.exists(filename + '.fpcalc'):
        print("Found precalculated fingerprint for %s" % (filename))
        f = open(filename + '.fpcalc', "r")
        fpcalc_out = ''.join(f.readlines())
        f.close()
    else:
        print("Calculating fingerprint by fpcalc for %s (sample time: %ss)" % (filename, sample_time_param))
        # Use sample_time_param in the subprocess call
        fpcalc_out = str(subprocess.check_output(['fpcalc', '-raw', '-length', str(sample_time_param), filename])).strip().replace('\\n', '').replace("'", "")

    fingerprint_index = fpcalc_out.find('FINGERPRINT=') + 12
    # convert fingerprint to list of integers
    fingerprints = list(map(int, fpcalc_out[fingerprint_index:].split(',')))

    return fingerprints

# returns correlation between lists
def correlation(listx, listy):
    if len(listx) == 0 or len(listy) == 0:
        # Error checking in main program should prevent us from ever being
        # able to get here.
        raise Exception('Empty lists cannot be correlated.')
    if len(listx) > len(listy):
        listx = listx[:len(listy)]
    elif len(listx) < len(listy):
        listy = listy[:len(listx)]

    covariance = 0
    for i in range(len(listx)):
        covariance += 32 - bin(listx[i] ^ listy[i]).count("1")
    covariance = covariance / float(len(listx))

    return covariance/32

# return cross correlation, with listy offset from listx
def cross_correlation(listx, listy, offset):
    if offset > 0:
        listx = listx[offset:]
        listy = listy[:len(listx)]
    elif offset < 0:
        offset = -offset
        listy = listy[offset:]
        listx = listx[:len(listy)]
    if min(len(listx), len(listy)) < min_overlap:
        # Error checking in main program should prevent us from ever being
        # able to get here.
        return
    #raise Exception('Overlap too small: %i' % min(len(listx), len(listy)))
    return correlation(listx, listy)

# cross correlate listx and listy with offsets from -span to span
def compare(listx, listy, span, step):
    if span > min(len(listx), len(listy)):
        # Error checking in main program should prevent us from ever being
        # able to get here.
        raise Exception('span >= sample size: %i >= %i\n'
                        % (span, min(len(listx), len(listy)))
                        + 'Reduce span, reduce crop or increase sample_time.')
    corr_xy = []
    for offset in numpy.arange(-span, span + 1, step):
        corr_xy.append(cross_correlation(listx, listy, offset))
    return corr_xy

# return index of maximum value in list
def max_index(listx):
    max_index = 0
    max_value = listx[0]
    for i, value in enumerate(listx):
        if value > max_value:
            max_value = value
            max_index = i
    return max_index

def get_max_corr(corr, source, target):
    if not corr or not any(c is not None for c in corr): # Check if correlation list is empty or all None
        print(f"Could not calculate correlation for {source} and {target}. This might be due to small overlap or empty fingerprints.")
        return

    # Filter out None values before finding max, if any (cross_correlation can return None)
    valid_corr_values = [c for c in corr if c is not None]
    if not valid_corr_values:
        print(f"No valid correlation values found for {source} and {target}.")
        return
        
    max_val_in_valid = max(valid_corr_values)
    # Find the first index in the original 'corr' list that matches this max_val_in_valid
    # This is to ensure the offset calculation remains correct based on the original list structure.
    max_corr_index = -1
    for i, value in enumerate(corr):
        if value == max_val_in_valid:
            max_corr_index = i
            break
            
    max_corr_offset = -span + max_corr_index * step
    #print("max_corr_index = ", max_corr_index, "max_corr_offset = ", max_corr_offset)
    # report matches
    if corr[max_corr_index] is not None and corr[max_corr_index] > threshold:
        print("File A: %s" % (source))
        print("File B: %s" % (target))
        print('Match with correlation of %.2f%% at offset %i'
             % (corr[max_corr_index] * 100.0, max_corr_offset))
    elif corr[max_corr_index] is not None:
        print(f"Highest correlation for {source} and {target} is {corr[max_corr_index]*100:.2f}% at offset {max_corr_offset}, which is below the threshold of {threshold*100}%.")
    else:
        # This case should ideally be caught by earlier checks
        print(f"Could not determine maximum correlation for {source} and {target}.")


def correlate(source, target, sample_time_param, delay_seconds): # Add delay_seconds parameter
    # Pass sample_time_param to calculate_fingerprints
    fingerprint_source = calculate_fingerprints(source, sample_time_param)

    # If it's a live stream (source and target are the same) and delay is specified, wait.
    if source == target and delay_seconds > 0:
        print(f"Live stream mode: Delaying for {delay_seconds} seconds before next fingerprint capture...")
        time.sleep(delay_seconds)
        # For a true live stream, the second call to calculate_fingerprints should fetch new data.
        # If 'source' is a static file, this will just re-read the same file after a delay.
        print(f"Recalculating fingerprint for {target} after delay.")

    fingerprint_target = calculate_fingerprints(target, sample_time_param)

    # Check if fingerprints are empty, which can happen if fpcalc fails or returns no data
    if not fingerprint_source or not fingerprint_target:
        print(f"Cannot compare due to empty fingerprint(s). Source: {len(fingerprint_source)}, Target: {len(fingerprint_target)}")
        return

    try:
        corr = compare(fingerprint_source, fingerprint_target, span, step)
        get_max_corr(corr, source, target)
    except Exception as e:
        # Catch potential errors from compare (e.g., span too large for sample size)
        print(f"Error during comparison: {e}")
        print(f"Fingerprint source length: {len(fingerprint_source)}, Fingerprint target length: {len(fingerprint_target)}")
        print(f"Span: {span}, Min Overlap: {min_overlap}, Sample Time: {sample_time_param}s")
