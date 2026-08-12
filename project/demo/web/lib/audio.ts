function writeAscii(view: DataView, offset: number, value: string) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}

function resampleMono(buffer: AudioBuffer, targetRate: number): Float32Array {
  const inputLength = buffer.length;
  const outputLength = Math.max(1, Math.round(inputLength * targetRate / buffer.sampleRate));
  const output = new Float32Array(outputLength);
  const channels = Array.from({ length: buffer.numberOfChannels }, (_, index) => buffer.getChannelData(index));
  const ratio = inputLength / outputLength;

  for (let outputIndex = 0; outputIndex < outputLength; outputIndex += 1) {
    const inputPosition = outputIndex * ratio;
    const left = Math.floor(inputPosition);
    const right = Math.min(inputLength - 1, left + 1);
    const mix = inputPosition - left;
    let sample = 0;
    for (const channel of channels) {
      sample += channel[left] * (1 - mix) + channel[right] * mix;
    }
    output[outputIndex] = sample / channels.length;
  }
  return output;
}

function encodePcm16Wav(samples: Float32Array, sampleRate: number): Blob {
  const dataBytes = samples.length * 2;
  const buffer = new ArrayBuffer(44 + dataBytes);
  const view = new DataView(buffer);
  writeAscii(view, 0, "RIFF");
  view.setUint32(4, 36 + dataBytes, true);
  writeAscii(view, 8, "WAVE");
  writeAscii(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(view, 36, "data");
  view.setUint32(40, dataBytes, true);
  for (let index = 0; index < samples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(44 + index * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

export async function browserRecordingToWav(recording: Blob): Promise<Blob> {
  const context = new AudioContext();
  try {
    const decoded = await context.decodeAudioData(await recording.arrayBuffer());
    return encodePcm16Wav(resampleMono(decoded, 16_000), 16_000);
  } finally {
    await context.close();
  }
}
