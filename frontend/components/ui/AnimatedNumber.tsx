"use client";

import { useEffect, useMemo, useState } from "react";

export function AnimatedNumber({ value, suffix = "" }: { value: number; suffix?: string }) {
  const [current, setCurrent] = useState(0);
  const decimals = useMemo(() => (Number.isInteger(value) ? 0 : 1), [value]);

  useEffect(() => {
    let frame = 0;
    const duration = 850;
    const start = performance.now();

    const tick = (time: number) => {
      const progress = Math.min((time - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setCurrent(value * eased);
      if (progress < 1) frame = requestAnimationFrame(tick);
    };

    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value]);

  return (
    <span>
      {current.toFixed(decimals)}
      {suffix}
    </span>
  );
}
