Simple tool to compare audio files
==================================

NOTE: This tool was originally found on the internet and ported to Python 3. Several new features have been added since the original port to enhance its functionality, including support for HLS streams, live stream analysis, and Nagios compatibility.

-   Original article: <https://shivama205.medium.com/audio-signals-comparison-23e431ed2207>
-   Original scripts: <https://github.com/kdave/audio-compare>

Dependencies
------------

### Python Packages

The primary Python package required is `numpy`. The `requirements.txt` file should contain: numpy

### External Tools

For full functionality, the following command-line tools are required:

-   `fpcalc` (Chromaprint): Used for generating audio fingerprints. It must be installed and accessible in your system's PATH. More info: <https://acoustid.org/chromaprint>
-   `ffmpeg`: Used for processing HLS (HTTP Live Streaming, `.m3u8`) audio streams. It must be installed and accessible in your system's PATH if you intend to analyze HLS streams.

Command-line Options
--------------------

The script accepts the following command-line options:

Option: --source-file Alias: -i Argument Type: string Default: None Description: Source audio file for comparison. Required if --live-stream is not used.

Option: --target-file Alias: -o Argument Type: string Default: None Description: Target audio file for comparison. Required if --live-stream is not used.

Option: --live-stream Alias: -l Argument Type: string Default: None Description: Single audio source (file/URL) for live stream loop check. Mutually exclusive with -i/-o.

Option: --sample-time Alias: -s Argument Type: integer Default: 60 Description: Seconds of audio to sample from each source.

Option: --delay Alias: (none) Argument Type: integer Default: 5 (if -l), 0 (else) Description: Delay in seconds between samples in live stream mode.

Option: --warn Alias: -w Argument Type: float Default: None Description: Nagios warning threshold for similarity percentage (e.g., 70.0). Requires -c.

Option: --critical Alias: -c Argument Type: float Default: None Description: Nagios critical threshold for similarity percentage (e.g., 90.0). Requires -w.

Usage
-----

The script compares audio fingerprints to find similarities. This can be between two distinct audio files or within a single audio stream (to detect looping).

### Basic Two-File Comparison

Compares two local audio files. By default, it samples 60 seconds from each.

```bash
$ python ./compare.py -i file1.mp3 -o file2.mp3 
Comparison mode: Source 'file1.mp3', Target 'file2.mp3'. Sample: 60s, Delay: 0s.
Calculating fingerprint by fpcalc for file1.mp3 (sample time: 60s)
Calculating fingerprint by fpcalc for file2.mp3 (sample time: 60s)
--- Correlation Result ---
File A: file1.mp3 File B: file2.mp3 Match: Similarity of 63.74% at offset 55 (Internal Threshold: 50.00%)
```

### Specifying Sample Time (`-s`, `--sample-time`)

Control the duration (in seconds) of audio to be fingerprinted from each source.

```bash
$ python ./compare.py -i file1.mp3 -o file2.mp3 -s 30
Comparison mode: Source 'file1.mp3', Target 'file2.mp3'. Sample: 30s, Delay: 0s.
Calculating fingerprint by fpcalc for file1.mp3 (sample time: 30s)
Calculating fingerprint by fpcalc for file2.mp3 (sample time: 30s)
--- Correlation Result ---
File A: file1.mp3 File B: file2.mp3 Match: Similarity of [XX.XX]% at offset [YY] (Internal Threshold: 50.00%)
```

### Live Stream Loop Check (`-l`, `--live-stream`)

Analyzes a single audio source (e.g., a local file or an HLS stream URL) by comparing it against itself after a delay. This is useful for detecting looping audio.

```bash
$ python ./compare.py -l https://your-stream-url.m3u8 -s 45
Live stream mode: Using 'https://your-stream-url.m3u8' as both source and target. Sample: 45s, Delay: 5s.
HLS stream detected: https://your-stream-url.m3u8. Processing with ffmpeg for 45 seconds.
Executing ffmpeg: ffmpeg -y -i https://your-stream-url.m3u8 -t 45 -vn -acodec pcm_s16le -ar 44100 -ac 1 /tmp/tmpxxxxxxx.wav
ffmpeg successfully processed HLS stream into /tmp/tmpxxxxxxx.wav
Calculating fingerprint using fpcalc for HLS temp file (from https://your-stream-url.m3u8)
Live stream mode: Delaying for 5 seconds before next fingerprint capture...
Recalculating fingerprint for https://your-stream-url.m3u8 after delay.
HLS stream detected: https://your-stream-url.m3u8. Processing with ffmpeg for 45 seconds.
Executing ffmpeg: ffmpeg -y -i https://your-stream-url.m3u8 -t 45 -vn -acodec pcm_s16le -ar 44100 -ac 1 /tmp/tmpyyyyyyy.wav
ffmpeg successfully processed HLS stream into /tmp/tmpyyyyyyy.wav Calculating fingerprint using fpcalc for HLS temp file (from https://your-stream-url.m3u8)
--- Correlation Result ---
File A: https://your-stream-url.m3u8 File B: https://your-stream-url.m3u8 Match: Similarity of [ZZ.ZZ]% at offset [WW] (Internal Threshold: 50.00%)
``` 

### Custom Delay for Live Stream (`--delay`)

Specify a custom delay (in seconds) between samples when using the live stream mode. The default is 5 seconds.

```bash
$ python ./compare.py -l https://your-stream-url.mp3 -s 60 --delay 10
Live stream mode: Using 'https://your-stream-url.mp3' as both source and target. Sample: 60s, Delay: 10s.
Calculating fingerprint by fpcalc for https://your-stream-url.mp3 (sample time: 60s)
Live stream mode: Delaying for 10 seconds before next fingerprint capture...
Recalculating fingerprint for https://your-stream-url.mp3 after delay.
Calculating fingerprint by fpcalc for https://your-stream-url.mp3 (sample time: 60s) ...
``` 

### Nagios Compatibility (`-w`, `-c`)

For integration with monitoring systems like Nagios, you can set warning (`-w` or `--warn`) and critical (`-c` or `--critical`) thresholds for the similarity percentage. The script will then output a Nagios-compatible status line and use standard Nagios exit codes:

-   0: OK
-   1: Warning
-   2: Critical
-   3: Unknown

Both `-w` and `-c` must be specified together, and the warning threshold must be less than the critical threshold.

```bash
$ python ./compare.py -i fileA.mp3 -o fileB.mp3 -s 60 -w 75.0 -c 90.0
Comparison mode: Source 'fileA.mp3', Target 'fileB.mp3'. Sample: 60s, Delay: 0s.
Calculating fingerprint by fpcalc for fileA.mp3 (sample time: 60s)
Calculating fingerprint by fpcalc for fileB.mp3 (sample time: 60s)
--- Correlation Result ---
File A: fileA.mp3
File B: fileB.mp3
Match: Similarity of 80.00% at offset 10 (Internal Threshold: 50.00%)
WARNING: Similarity is 80.00% (Threshold: >=75.0%) |'similarity'=80.00;75.0;90.0;0;100
$ echo $?
1
``` 

Internals
---------

-   Audio fingerprints are generated using the `fpcalc` utility from the Chromaprint project. The duration of audio processed by `fpcalc` is controlled by the `-s`/`--sample-time` option, passed as `-length <seconds>` to `fpcalc`.
-   HLS streams (`.m3u8` URLs) are first processed using `ffmpeg`. A segment of `sample_time` duration is captured and converted into a temporary WAV file. This temporary file is then fingerprinted by `fpcalc`.
-   Pre-calculated fingerprints (e.g., `file.mp3.fpcalc`) can be used if they exist for local files. This is not applicable to HLS streams, which are processed dynamically.

Original Changes (from porter of the initial script)
----------------------------------------------------

-   Ported to Python 3
-   Prints the similarity as percentages
-   Prints input files on separate lines
-   Supports precalculated fingerprint in `file.mp3.fpcalc`

Added Features Since Port
-------------------------

-   Configurable Sample Time: The `-s` or `--sample-time` option allows specifying the duration (in seconds) of audio to sample and fingerprint from each source.
-   Live Stream Analysis Mode: The `-l` or `--live-stream` option enables comparing a single audio source against itself. This is useful for detecting loops in live streams or long audio files.
-   Configurable Delay for Live Stream: The `--delay` option allows customizing the time (in seconds) between the two samples taken in live stream mode (default is 5 seconds).
-   Nagios Compatibility: Added `-w` (`--warn`) and `-c` (`--critical`) options to set similarity percentage thresholds for Nagios monitoring. The script provides Nagios-compliant output and exit codes.
-   HLS Stream Support: Can now process HLS (`.m3u8`) audio streams. This requires `ffmpeg` to be installed and accessible in the system's PATH.
