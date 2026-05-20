"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { type RefObject, useCallback, useEffect, useState } from "react";

interface StoryboardScrollArrowsProps {
  scrollContainerRef: RefObject<HTMLDivElement | null>;
}

export function StoryboardScrollArrows({ scrollContainerRef }: StoryboardScrollArrowsProps) {
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const updateScrollState = useCallback(() => {
    const el = scrollContainerRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 2);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 2);
  }, [scrollContainerRef]);

  useEffect(() => {
    const el = scrollContainerRef.current;
    if (!el) return;

    updateScrollState();
    el.addEventListener("scroll", updateScrollState, { passive: true });

    const observer = new ResizeObserver(updateScrollState);
    observer.observe(el);

    return () => {
      el.removeEventListener("scroll", updateScrollState);
      observer.disconnect();
    };
  }, [scrollContainerRef, updateScrollState]);

  function scroll(direction: "left" | "right") {
    const el = scrollContainerRef.current;
    if (!el) return;
    const delta = direction === "left" ? -200 : 200;
    el.scrollBy({ left: delta, behavior: "smooth" });
  }

  return (
    <>
      {canScrollLeft && (
        <button
          type="button"
          onClick={() => scroll("left")}
          className="absolute left-0 top-0 bottom-0 w-8 flex items-center justify-center bg-gradient-to-r from-background to-transparent z-10"
          aria-label="Scroll left"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>
      )}
      {canScrollRight && (
        <button
          type="button"
          onClick={() => scroll("right")}
          className="absolute right-0 top-0 bottom-0 w-8 flex items-center justify-center bg-gradient-to-l from-background to-transparent z-10"
          aria-label="Scroll right"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
      )}
    </>
  );
}
