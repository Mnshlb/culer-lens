import type { Metadata } from "next";
import { ModelIntelligence } from "@/components/model/model-intelligence";

export const metadata: Metadata = { title: "Model Intelligence" };

export default function Page() {
  return <ModelIntelligence />;
}
