/** ExclamationEffect: pixel exclamation mark that fades out above an agent. */

"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { SPRITES } from "@/lib/assets";

interface Props {
  x: number;
  y: number;
  onDone: () => void;
}

export default function ExclamationEffect({ x, y, onDone }: Props) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      onDone();
    }, 800);
    return () => clearTimeout(timer);
  }, [onDone]);

  if (!visible) return null;

  return (
    <div
      className="absolute z-50 pointer-events-none animate-[exclamation-fade_0.8s_ease-out_forwards]"
      style={{ left: x - 16, top: y - 48 }}
    >
      <Image
        src={SPRITES.fxExclamation}
        alt="!"
        width={32}
        height={32}
        className="pixelated"
        style={{ imageRendering: "pixelated" }}
        unoptimized
      />
    </div>
  );
}
