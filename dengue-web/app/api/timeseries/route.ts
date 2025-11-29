import { NextResponse } from "next/server";
import { getTimeseries } from "@/lib/api";

export async function GET(req: Request) {
  try {
    const { searchParams } = new URL(req.url);

    const level = searchParams.get("level") ?? "city";    // REQUIRED
    const name = searchParams.get("name") ?? undefined;
    const freq = (searchParams.get("freq") as any) ?? "weekly";
    const model = (searchParams.get("model") as any) ?? "preferred";

    const data = await getTimeseries(level as "city" | "barangay", {
      name,
      freq,
      model,
    });

    return NextResponse.json(data);
  } catch (err) {
    console.error("API /timeseries error:", err);
    return NextResponse.json(
      { error: "failed to load timeseries" },
      { status: 500 },
    );
  }
}
