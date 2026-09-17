"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export interface UseAutoScrollOptions {
  threshold?: number; // Distance in px from bottom considered "at bottom"
  smooth?: boolean;
}

export function useAutoScroll<T extends HTMLElement = HTMLDivElement>(
  triggerValue?: any,
  options: UseAutoScrollOptions = {}
) {
  const { threshold = 80, smooth = true } = options;
  const containerRef = useRef<T | null>(null);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [isUserScrolledUp, setIsUserScrolledUp] = useState(false);

  const scrollToBottom = useCallback(
    (behavior: ScrollBehavior = smooth ? "smooth" : "auto") => {
      if (containerRef.current) {
        containerRef.current.scrollTo({
          top: containerRef.current.scrollHeight,
          behavior,
        });
        setIsAtBottom(true);
        setIsUserScrolledUp(false);
      }
    },
    [smooth]
  );

  // Monitor user scroll position
  const handleScroll = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;

    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const atBottom = distanceFromBottom <= threshold;

    setIsAtBottom(atBottom);
    setIsUserScrolledUp(!atBottom);
  }, [threshold]);

  // Auto-scroll on dependency change if already locked to bottom
  useEffect(() => {
    if (isAtBottom && !isUserScrolledUp) {
      scrollToBottom("auto");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [triggerValue, isAtBottom, isUserScrolledUp, scrollToBottom]);

  return {
    containerRef,
    isAtBottom,
    isUserScrolledUp,
    scrollToBottom,
    handleScroll,
  };
}
