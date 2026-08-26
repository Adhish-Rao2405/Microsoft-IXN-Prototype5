# Prototype 5 recorded Nemotron speech

## Milestone

`V1 - Recorded Nemotron transcription`

## Scope

V1 adds one real recorded-audio path to the integrated demonstrator:

```text
16 kHz mono 16-bit PCM WAV
        -> isolated Foundry Local SDK worker
        -> reviewed transcript
        -> canonical voice request
        -> H1 router
        -> A2.2 governance runner
```

The transcript is an untrusted input. Transcription does not call the planner,
does not evaluate policy, and does not issue execution authority. The operator
must review the transcript and submit it explicitly before it can reach the
same router and governance runner used by typed input.

## Qualified model

```text
Alias: nemotron-speech-streaming-en-0.6b
Resolved model ID: nemotron-speech-streaming-en-0.6b-generic-cpu:3
Task: automatic-speech-recognition
Input: audio
Output: text
Execution-provider metadata: CPUExecutionProvider
```

The V1 engineering qualification used:

```text
Python: 3.12.10
foundry-local-sdk-winml: 1.2.3
foundry-local-core-winml: 1.2.3
```

These values describe the qualified environment. They are not a claim that
all later SDK versions or hardware configurations behave identically.

## Process isolation

The FastAPI process does not import the Foundry Local SDK. It starts a bounded
speech worker using `PROTOTYPE5_SPEECH_PYTHON`. This boundary:

* keeps the platform-specific SDK outside the hash-locked web environment;
* prevents cloud credentials from entering the speech-worker environment;
* applies a hard process deadline;
* discards child stdout and stderr instead of buffering unbounded output;
* writes uploaded audio only beneath an operating-system temporary directory;
* deletes the temporary WAV and worker result when the request completes;
* unloads the model when the worker loaded it for the request.

Model acquisition is disabled by default. The interactive API never silently
downloads the model. Acquisition is available only through the explicit smoke
runner flag:

```text
--allow-model-download
```

## API

Recorded transcription:

```text
POST /api/v1/speech/recorded
Content-Type: audio/wav
X-Audio-Filename: operator.wav
```

Reviewed voice submission:

```text
POST /api/v1/governance/voice
```

A successful transcription is registered server-side for ten minutes and is
single use. The voice-governance request supplies the registration identifier
and reviewed text. Backend identity and audio SHA-256 are recovered from the
server-side record rather than trusted from browser input.

The resulting `GovernanceRecordV2` stores the original ASR text separately
from the operator-reviewed command and carries the same `transcription_id`.
This preserves the edit boundary without trusting the browser to supply audio
or model provenance.

## Transcript states

```text
READY
PARTIAL
EMPTY
BACKEND_UNAVAILABLE
FAILED
CANCELLED
```

Only `READY` is eligible for registration and later governance submission.
`PARTIAL`, `EMPTY`, unavailable, failed, and cancelled transcripts cannot call
the planner. `CANCELLED` is reserved by the shared contract for the V2
push-to-talk milestone; the V1 recorded-file endpoint does not expose a cancel
operation. A disconnected HTTP client does not make the bounded worker result
eligible and the worker remains subject to its process timeout.

The SDK live stream emits partial text chunks and a final corrected result.
V1 discards partial chunks when at least one final result is available. If no
final result arrives, the reconstructed text is retained as `PARTIAL` and is
not accepted by the governance endpoint.

## Configuration

```text
PROTOTYPE5_SPEECH_PYTHON
PROTOTYPE5_SPEECH_TIMEOUT_SECONDS
PROTOTYPE5_SPEECH_ALLOW_MODEL_DOWNLOAD
PROTOTYPE5_SPEECH_TEMP_ROOT
```

Recommended demo configuration:

```powershell
$env:PROTOTYPE5_SPEECH_PYTHON = `
    "C:\path\to\speech-sdk-env\Scripts\python.exe"

$env:PROTOTYPE5_SPEECH_TIMEOUT_SECONDS = "300"
$env:PROTOTYPE5_SPEECH_ALLOW_MODEL_DOWNLOAD = "0"
```

The speech-worker environment must contain `foundry-local-sdk-winml`. The model
should be acquired through the explicit smoke run before starting the UI.

## Explicit acquisition and smoke

The input must be a WAV file in the exact supported format. The result path
must remain outside the repository:

```powershell
python scripts/prototype5/run_nemotron_recorded_audio_smoke.py `
    --audio C:\external\controlled-command.wav `
    --speech-python C:\external\speech-env\Scripts\python.exe `
    --timeout-seconds 1200 `
    --allow-model-download `
    --output C:\external\v1-result.json
```

After acquisition, omit `--allow-model-download` for repeat qualification.

## Qualification result

One controlled, non-sensitive 4.375-second WAV was qualified outside the
repository:

```text
Audio SHA-256:
380af7ac7507cad0af47c578d3aca0f134d802f7d351d2590c8d48612fd174b5

Final transcript:
Move the blue component from input tray A to assembly fixture B

Status:
READY

Model cached before repeat qualification:
true

Model loaded before repeat qualification:
false

Model loaded for request:
true

Model unloaded after request:
true

Repeat worker transcription latency:
11925 ms

FastAPI endpoint transcription latency:
16843 ms
```

The external qualification artefact is engineering smoke evidence. It is not
part of the frozen historical dissertation evidence and must not be treated as
a recorded-audio benchmark.

## Tests

Focused tests cover:

* exact WAV format and size validation;
* invalid input rejected before process creation;
* missing SDK worker;
* process timeout;
* cloud-secret exclusion;
* temporary-audio deletion;
* exact alias and model-ID enforcement;
* no implicit download;
* explicit download, load, audio-client, and unload lifecycle;
* final versus partial stream reconstruction;
* empty transcript handling;
* explicit review before governance;
* one-time transcript registration;
* typed and voice convergence on the same router and gateway.

All subprocess and SDK unit tests use fakes. Only the explicitly invoked smoke
runner accesses the real Foundry Local runtime.

## Claim boundary

V1 proves one bounded local recorded-speech path on the qualified machine. It
does not prove microphone capture, live streaming UX, speech accuracy across
speakers, robustness to noise, safety-critical token recall, clinical use, or
physical robot control. The observed 11.9-16.8 second request latency is not a
real-time speech claim. V1 does not include PyBullet, healthcare policy,
physical execution, or regenerated dissertation benchmark evidence.
