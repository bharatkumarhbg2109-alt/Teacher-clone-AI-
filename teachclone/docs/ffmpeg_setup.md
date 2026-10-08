# FFmpeg Installation Guide

TeachClone uses FFmpeg for extracting 16kHz audio from videos and audio files for Whisper transcription.

## Operating System Installation

### Windows
Using Windows Package Manager (recommended):
```powershell
winget install Gyan.FFmpeg
```
Alternatively, download the essentials build from [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/), extract the zip, and add the `bin` folder to your Windows system `PATH`.

Verify in PowerShell or CMD:
```powershell
ffmpeg -version
```

### macOS
Using Homebrew:
```bash
brew install ffmpeg
```

Verify in terminal:
```bash
ffmpeg -version
```

### Linux (Ubuntu / Debian)
Using APT:
```bash
sudo apt update
sudo apt install -y ffmpeg
```

Verify:
```bash
ffmpeg -version
```
