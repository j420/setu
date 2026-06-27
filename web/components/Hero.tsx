"use client";

import React, { useState } from "react";
import { PhotoCapture } from "./PhotoCapture";

export function Hero({
  onContinueWithPhoto,
  onLogDetails,
}: {
  onContinueWithPhoto: (photo: string) => void;
  onLogDetails: () => void;
}) {
  const [photo, setPhoto] = useState<string | null>(null);

  return (
    <section className="mb-6 overflow-hidden rounded-3xl border border-line bg-panel shadow-soft">
      <div className="grid items-stretch gap-0 md:grid-cols-2">
        {/* copy */}
        <div className="flex flex-col justify-center p-8 md:p-10">
          <span className="pill mb-4 w-fit bg-accent/10 text-accent">
            Reunification intake
          </span>
          <h1 className="font-serif text-3xl font-semibold leading-tight text-head md:text-4xl">
            Found someone who is lost?
            <br />
            Start with a photo.
          </h1>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-muted">
            Add a photo of the person you&apos;ve found. It stays on this device,
            is used only to <em>aid</em> a human verifier at reunion, is never
            added to any biometric database, and is auto-purged once the family is
            reunited. No name needed.
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <button
              className="btn btn-primary px-5"
              disabled={!photo}
              onClick={() => photo && onContinueWithPhoto(photo)}
            >
              Continue to log this person →
            </button>
            <button className="btn" onClick={onLogDetails}>
              Log details without a photo
            </button>
          </div>
          <p className="mt-4 text-[11px] text-muted">
            A human always verifies the family bond before any reunion — no photo
            score can confirm a handover.
          </p>
        </div>

        {/* hero photo capture */}
        <div className="flex items-center justify-center border-t border-line bg-ink/50 p-8 md:border-l md:border-t-0">
          <div className="w-full max-w-sm">
            <div className="rounded-2xl border border-dashed border-line bg-panel p-5 shadow-soft">
              <PhotoCapture value={photo} onChange={setPhoto} label="" large />
            </div>
            {photo && (
              <p className="mt-3 text-center text-xs text-ok">
                Photo ready — continue to add a few quick details.
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
