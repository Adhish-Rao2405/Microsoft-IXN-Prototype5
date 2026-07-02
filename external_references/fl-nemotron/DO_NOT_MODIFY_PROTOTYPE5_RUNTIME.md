# Do Not Modify Prototype 5 Runtime

This folder is an external reference snapshot of Lee Stott's `fl-nemotron`
project.

It is not imported by Prototype 5.
It is not part of the tested Prototype 5 runtime.
It is not part of the zero-trust validator implementation.
It is not evidence of working Prototype 5 voice control.
It is used only to inform the future Nemotron voice-extension pathway.

The current Prototype 5 voice evidence remains:

- M15A.2: Foundry Local exposed a Whisper candidate model, but tested HTTP
  transcription endpoints returned 404.
- M15B.0: a Nemotron SDK route would require SDK/dependency work and WAV/PCM
  audio handling before any controlled STT spike.

Do not import from this directory in `src/`, `scripts/`, or tests. Do not treat
these files as project dependencies.
