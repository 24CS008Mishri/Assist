class SarvamMic extends AudioWorkletProcessor {
  constructor() {
    super();
    this.frame = new Float32Array(320);
    this.offset = 0;
  }

  process(inputs) {
    for (const value of inputs[0]?.[0] || []) {
      this.frame[this.offset++] = value;
      if (this.offset === this.frame.length) {
        this.port.postMessage(this.frame, [this.frame.buffer]);
        this.frame = new Float32Array(320);
        this.offset = 0;
      }
    }
    return true;
  }
}

registerProcessor('sarvam-mic', SarvamMic);
