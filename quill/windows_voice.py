"""Offline Windows speech fallback. Text goes over stdin, never command arguments."""
import base64,json,os,subprocess

def synthesize(text,gender):
    if os.name!='nt':raise RuntimeError('Local voice model is unavailable on this server.')
    script=r"""
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Speech
$inputData=[Console]::In.ReadToEnd() | ConvertFrom-Json
$speaker=New-Object System.Speech.Synthesis.SpeechSynthesizer
$stream=New-Object System.IO.MemoryStream
try {
    $voice=$speaker.GetInstalledVoices() | Where-Object { $_.Enabled -and $_.VoiceInfo.Gender.ToString() -eq $inputData.gender } | Select-Object -First 1
    if (-not $voice) { throw 'Requested local voice is not installed.' }
    $speaker.SelectVoice($voice.VoiceInfo.Name)
    $speaker.SetOutputToWaveStream($stream)
    $speaker.Speak([string]$inputData.text)
    $speaker.SetOutputToNull()
    [Console]::Out.Write([Convert]::ToBase64String($stream.ToArray()))
} finally { $speaker.Dispose();$stream.Dispose() }
"""
    command=base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    result=subprocess.run(['powershell.exe','-NoLogo','-NoProfile','-NonInteractive','-EncodedCommand',command],input=json.dumps({'text':str(text),'gender':'Female' if str(gender).lower()=='female' else 'Male'}),encoding='utf-8',capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:raise RuntimeError('Windows local speech could not generate audio. Text remains available.')
    try:audio=base64.b64decode(result.stdout.strip(),validate=True)
    except Exception:raise RuntimeError('Windows local speech returned invalid audio.') from None
    if not audio.startswith(b'RIFF') or len(audio)<44:raise RuntimeError('Windows local speech returned empty audio.')
    return audio
