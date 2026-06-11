# Wake-word Deactivator
https://x.com/bryanwangxin/status/2064309590414836085
> In Apple's keynote video, whenever Siri is mentioned, the audio is cut at the 3k, 4k, 5k, and 6kHz frequency bands to prevent nearby Apple devices from activating Siri while viewers watch the video.

When Apple says “Siri” in a keynote, they deliberately remove certain frequencies from the audio so it doesn’t trigger everyone’s devices. This project does the same thing for your content.

It’s a simple CLI tool that processes podcast and video audio so wake words (“Hey Siri”, “Alexa”, “OK Google”, etc.) won’t accidentally activate nearby smart assistants.

## Usage
1. You must have a Whisper model locally available and inform wakeword-remover of the path to the model.
```
wakeword-remover setwhisperpath /path/to/whisper
```
2. Run the command with input video. Use the `--wakewords` flag and add space-separated custom words you would like to deactivate. For phrases, wrap them in quotes.
```
wakeword-remover process /path/to/audio/or/video --wakewords "customPhrase1" word1 word2 "customPhrase2" --output /path/to/desired/output/location
```

And boom! Enjoy!
