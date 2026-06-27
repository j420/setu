import { NextRequest, NextResponse } from "next/server";
import { compareImages } from "@/lib/faceServer";

// Server-side photo verification (Node runtime). Stateless: it accepts two
// images, returns a similarity score computed from the real pixels, and stores
// NOTHING — no DB, no file write, no searchable index. The score is advisory;
// the human handover gate still decides.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_CHARS = 8_000_000; // ~6MB per image data URL guard

export async function POST(req: NextRequest) {
  let body: { imageA?: string; imageB?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "invalid JSON body" }, { status: 400 });
  }
  const { imageA, imageB } = body;
  if (!imageA || !imageB) {
    return NextResponse.json(
      { error: "both imageA and imageB (base64 data URLs) are required" },
      { status: 400 },
    );
  }
  if (imageA.length > MAX_CHARS || imageB.length > MAX_CHARS) {
    return NextResponse.json({ error: "image too large" }, { status: 413 });
  }
  try {
    const result = compareImages(imageA, imageB);
    return NextResponse.json(result, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch (e) {
    return NextResponse.json(
      { error: `could not compare images: ${(e as Error).message}` },
      { status: 422 },
    );
  }
}
