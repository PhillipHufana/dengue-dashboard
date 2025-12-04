import { getTimeseries } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
export function useTimeseries(selectedBarangayName: string | null) {
  const level = selectedBarangayName ? "barangay" : "city";

  return useQuery({
    queryKey: ["timeseries", level, selectedBarangayName],
    queryFn: () =>
      getTimeseries(level, {
        name: selectedBarangayName ?? undefined,
        freq: "weekly",
        model: "preferred",
      }),
  });
}
