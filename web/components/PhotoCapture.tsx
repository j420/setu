"use client";

import React, { useRef, useState } from "react";

// Downscale any selected/captured image to a small JPEG data URL so it is cheap
// to store locally and to send for server-side comparison. No raw file leaves
// the device beyond this normalised thumbnail.
async function fileToDataUrl(file: File, maxDim = 320): Promise<string> {
  const url = URL.createObjectURL(file);
  try {
    const img = await new Promise<HTMLImageElement>((res, rej) => {
      const i = new Image();
      i.onload = () => res(i);
      i.onerror = rej;
      i.src = url;
    });
    const scale = Math.min(1, maxDim / Math.max(img.width, img.height));
    const w = Math.max(1, Math.round(img.width * scale));
    const h = Math.max(1, Math.round(img.height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(img, 0, 0, w, h);
    return canvas.toDataURL("image/jpeg", 0.7);
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function PhotoCapture({
  value,
  onChange,
  label = "Photo",
}: {
  value: string | null;
  onChange: (dataUrl: string | null) => void;
  label?: string;
}) {
  const fileRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [streaming, setStreaming] = useState(false);
  const streamRef = useRef<MediaStream | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    try {
      onChange(await fileToDataUrl(f));
    } catch {
      setErr("could not read that image");
    }
  }

  async function startCam() {
    setErr(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      streamRef.current = stream;
      setStreaming(true);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
    } catch {
      setErr("camera unavailable — use file upload instead");
    }
  }

  function stopCam() {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setStreaming(false);
  }

  function snap() {
    const v = videoRef.current;
    if (!v) return;
    const maxDim = 320;
    const scale = Math.min(1, maxDim / Math.max(v.videoWidth, v.videoHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(v.videoWidth * scale);
    canvas.height = Math.round(v.videoHeight * scale);
    canvas.getContext("2d")!.drawImage(v, 0, 0, canvas.width, canvas.height);
    onChange(canvas.toDataURL("image/jpeg", 0.7));
    stopCam();
  }

  return (
    <div>
      <label className="label">{label}</label>
      <div className="flex items-start gap-3">
        <div className="grid h-20 w-20 shrink-0 place-items-center overflow-hidden rounded-xl border border-line bg-ink/60 text-[10px] text-muted">
          {value ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={value} alt="preview" className="h-full w-full object-cover" />
          ) : streaming ? (
            <video ref={videoRef} className="h-full w-full object-cover" muted playsInline />
          ) : (
            "no photo"
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <input ref={fileRef} type="file" accept="image/*" capture="environment" className="hidden" onChange={onPick} />
          <button type="button" className="btn !py-1.5" onClick={() => fileRef.current?.click()}>
            Upload
          </button>
          {!streaming ? (
            <button type="button" className="btn !py-1.5" onClick={startCam}>
              Camera
            </button>
          ) : (
            <>
              <button type="button" className="btn btn-primary !py-1.5" onClick={snap}>
                Capture
              </button>
              <button type="button" className="btn !py-1.5" onClick={stopCam}>
                Cancel
              </button>
            </>
          )}
          {value && (
            <button type="button" className="btn !py-1.5 text-danger" onClick={() => onChange(null)}>
              Remove
            </button>
          )}
        </div>
      </div>
      {err && <p className="mt-1 text-xs text-danger">{err}</p>}
    </div>
  );
}
