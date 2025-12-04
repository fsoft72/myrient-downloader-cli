# Changelog

All notable changes to this project will be documented in this file.

## [0.4.0] - 2025-12-04

### Added
- **Network Reliability**:
    - Added 30-second timeout to all network requests (get, head) to prevent hanging.
    - Implemented a retry loop (3 attempts) for file downloads to handle interruptions.
    - Added robust resume logic to handle cases where servers ignore Range headers.
- **Packaging**: Added `publish.sh` to create PyPI package and setup scripts.
- **UI/UX**:
    - Added type-ahead functionality to match file names in the list.
    - Added progress bar when loading directories.
    - Added version number display.

### Changed
- Renamed `myrient_dl.py` script to `myrient.py`.
- Improved error reporting and recovery within the worker.

### Removed
- Removed `settings.json` from the folder and added it to `.gitignore`.
