import { useEffect, useId, useRef, useState } from "react";

export type AssistantExpression =
  | "neutral"
  | "happy"
  | "thinking"
  | "alert"
  | "explaining"
  | "success"
  | "error"
  | "loading";

interface AICFOAvatarProps {
  size?: number;
  expression?: AssistantExpression;
  onClick?: () => void;
  label?: string;
  compact?: boolean;
}

/** Mouth paths in a 120x120 viewBox, centred on x=60. */
const MOUTH: Record<AssistantExpression, string> = {
  neutral: "M50 80 Q60 85 70 80",
  happy: "M46 78 Q60 94 74 78",
  thinking: "M52 82 Q60 80 68 82",
  alert: "M50 86 Q60 76 70 86",
  explaining: "M48 79 Q60 90 72 79",
  success: "M44 77 Q60 98 76 77",
  error: "M50 87 Q60 77 70 87",
  loading: "M54 82 L66 82",
};

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

export function AICFOAvatar({
  size = 64,
  expression = "neutral",
  onClick,
  label = "FinSight AI assistant",
  compact = false,
}: AICFOAvatarProps) {
  const uid = useId().replace(/:/g, "");
  const hostRef = useRef<HTMLSpanElement>(null);
  const headRef = useRef<SVGGElement>(null);
  const pupilL = useRef<SVGGElement>(null);
  const pupilR = useRef<SVGGElement>(null);
  const target = useRef({ x: 0, y: 0 });
  const current = useRef({ x: 0, y: 0 });
  const [blinking, setBlinking] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [poked, setPoked] = useState(false);

  const effective: AssistantExpression = poked ? "happy" : expression;

  // Cursor tracking: only the target is stored on mouse move; a rAF loop eases
  // toward it and writes straight to the DOM, so no React re-render per move.
  useEffect(() => {
    if (prefersReducedMotion()) return;
    function onMove(event: MouseEvent) {
      const node = hostRef.current;
      if (!node) return;
      const rect = node.getBoundingClientRect();
      const dx = event.clientX - (rect.left + rect.width / 2);
      const dy = event.clientY - (rect.top + rect.height / 2);
      const dist = Math.hypot(dx, dy) || 1;
      const strength = Math.min(1, dist / 220);
      target.current = { x: (dx / dist) * strength, y: (dy / dist) * strength };
    }
    window.addEventListener("mousemove", onMove, { passive: true });

    let raf = 0;
    const tick = () => {
      const c = current.current;
      const t = target.current;
      c.x += (t.x - c.x) * 0.14;
      c.y += (t.y - c.y) * 0.14;
      const eye = `translate(${(c.x * 5.5).toFixed(2)} ${(c.y * 4.5).toFixed(2)})`;
      pupilL.current?.setAttribute("transform", eye);
      pupilR.current?.setAttribute("transform", eye);
      headRef.current?.setAttribute(
        "transform",
        `translate(${(c.x * 2).toFixed(2)} ${(c.y * 1.5).toFixed(2)}) rotate(${(c.x * 4).toFixed(2)} 60 66)`
      );
      raf = window.requestAnimationFrame(tick);
    };
    raf = window.requestAnimationFrame(tick);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.cancelAnimationFrame(raf);
    };
  }, []);

  // Natural, irregular blinking with an occasional double blink.
  useEffect(() => {
    if (prefersReducedMotion()) return;
    let timer = 0;
    let inner = 0;
    const schedule = () => {
      timer = window.setTimeout(() => {
        setBlinking(true);
        inner = window.setTimeout(() => {
          setBlinking(false);
          if (Math.random() < 0.2) {
            inner = window.setTimeout(() => {
              setBlinking(true);
              inner = window.setTimeout(() => setBlinking(false), 120);
            }, 160);
          }
        }, 130);
        schedule();
      }, 2200 + Math.random() * 3600);
    };
    schedule();
    return () => {
      window.clearTimeout(timer);
      window.clearTimeout(inner);
    };
  }, []);

  useEffect(() => {
    if (!poked) return;
    const timer = window.setTimeout(() => setPoked(false), 1100);
    return () => window.clearTimeout(timer);
  }, [poked]);

  const shut = blinking || effective === "success";
  const cls = ["finsight-avatar", `is-${effective}`, hovered ? "is-hovered" : "", poked ? "is-poked" : ""]
    .filter(Boolean)
    .join(" ");
  const cheek = effective === "happy" || effective === "success" || hovered;
  const antenna =
    effective === "error" || effective === "alert" ? "#B91C1C" : effective === "success" ? "#16845B" : "#D6B477";

  const eyes = [
    { cx: 42, clip: `${uid}-eyeL`, ref: pupilL },
    { cx: 78, clip: `${uid}-eyeR`, ref: pupilR },
  ];

  const content = (
    <svg
      className={cls}
      width={size}
      height={size}
      viewBox="0 0 120 120"
      role="img"
      aria-label={label}
      data-testid="finsight-avatar"
    >
      <defs>
        <radialGradient id={`${uid}-shell`} cx="35%" cy="25%" r="85%">
          <stop offset="0%" stopColor="#FFFFFF" />
          <stop offset="45%" stopColor="#F1EEE4" />
          <stop offset="100%" stopColor="#C9D8CE" />
        </radialGradient>
        <radialGradient id={`${uid}-ear`} cx="35%" cy="30%" r="80%">
          <stop offset="0%" stopColor="#F8F1DE" />
          <stop offset="100%" stopColor="#D6B477" />
        </radialGradient>
        <linearGradient id={`${uid}-visor`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#16845B" />
          <stop offset="100%" stopColor="#123B2A" />
        </linearGradient>
        <radialGradient id={`${uid}-iris`} cx="40%" cy="35%" r="75%">
          <stop offset="0%" stopColor="#D9C58E" />
          <stop offset="100%" stopColor="#16845B" />
        </radialGradient>
        <radialGradient id={`${uid}-glow`} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#D6B477" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#16845B" stopOpacity="0" />
        </radialGradient>
        <clipPath id={`${uid}-eyeL`}>
          <rect x="30" y="44" width="24" height="28" rx="12" />
        </clipPath>
        <clipPath id={`${uid}-eyeR`}>
          <rect x="66" y="44" width="24" height="28" rx="12" />
        </clipPath>
      </defs>

      {!compact && <circle cx="60" cy="62" r="56" fill={`url(#${uid}-glow)`} className="avatar-aura" />}
      <ellipse cx="60" cy="116" rx="26" ry="3.5" fill="#0F172A" opacity="0.14" className="avatar-shadow" />

      <g className="avatar-body">
        <g ref={headRef}>
          <rect x="58" y="10" width="4" height="14" rx="2" fill="#BFD1C5" />
          <circle cx="60" cy="9" r="5.5" className="avatar-antenna" fill={antenna} />
          <circle cx="58.3" cy="7.3" r="1.6" fill="#FFFFFF" opacity="0.85" />

          <ellipse cx="14" cy="62" rx="7" ry="12" fill={`url(#${uid}-ear)`} />
          <ellipse cx="106" cy="62" rx="7" ry="12" fill={`url(#${uid}-ear)`} />

          <rect x="16" y="22" width="88" height="80" rx="40" fill={`url(#${uid}-shell)`} stroke="#8FAE9B" strokeWidth="1.5" />
          <path d="M30 34 Q44 24 62 25" stroke="#FFFFFF" strokeWidth="5" strokeLinecap="round" fill="none" opacity="0.8" />

          <rect x="24" y="40" width="72" height="38" rx="19" fill={`url(#${uid}-visor)`} />
          <path d="M34 45 Q60 39 86 45" stroke="#FFFFFF" strokeWidth="1.6" strokeLinecap="round" fill="none" opacity="0.22" />

          {eyes.map(({ cx, clip, ref }) => (
            <g key={cx}>
              {shut ? (
                <path
                  d={
                    effective === "success"
                      ? `M${cx - 9} 61 Q${cx} 50 ${cx + 9} 61`
                      : `M${cx - 9} 59 Q${cx} 64 ${cx + 9} 59`
                  }
                  stroke="#D6B477"
                  strokeWidth="3.4"
                  strokeLinecap="round"
                  fill="none"
                />
              ) : (
                <>
                  <ellipse data-eye="white" cx={cx} cy="58" rx="12" ry="13.5" fill="#FFFFFF" />
                  <g clipPath={`url(#${clip})`}>
                    <g ref={ref}>
                      <circle cx={cx} cy="58" r="8.6" fill={`url(#${uid}-iris)`} />
                      <circle cx={cx} cy="58" r="4.4" fill="#123B2A" />
                      <circle cx={cx - 3} cy="54" r="2.6" fill="#FFFFFF" />
                      <circle cx={cx + 3.2} cy="62" r="1.2" fill="#FFFFFF" opacity="0.8" />
                    </g>
                  </g>
                </>
              )}
            </g>
          ))}

          {(effective === "alert" || effective === "error") && (
            <>
              <path d="M30 40 L52 44" stroke="#D6B477" strokeWidth="3" strokeLinecap="round" />
              <path d="M90 40 L68 44" stroke="#D6B477" strokeWidth="3" strokeLinecap="round" />
            </>
          )}
          {(effective === "thinking" || effective === "loading") && (
            <path d="M68 41 Q78 36 88 41" stroke="#D6B477" strokeWidth="3" strokeLinecap="round" fill="none" />
          )}

          <circle cx="30" cy="84" r="6" fill="#D6B477" opacity={cheek ? 0.85 : 0.45} className="avatar-cheek" />
          <circle cx="90" cy="84" r="6" fill="#D6B477" opacity={cheek ? 0.85 : 0.45} className="avatar-cheek" />
          <path d={MOUTH[effective]} stroke="#123B2A" strokeWidth="3.2" fill="none" strokeLinecap="round" className="avatar-mouth" />
        </g>

        <rect x="42" y="100" width="36" height="14" rx="9" fill="#C9D8CE" stroke="#8FAE9B" strokeWidth="1.2" />
        <circle cx="60" cy="107" r="3.2" fill="#16845B" className="avatar-chest" />
        <ellipse cx="34" cy="106" rx="6" ry="5" fill="#F8F1DE" className="avatar-hand avatar-hand-l" />
        <ellipse cx="86" cy="106" rx="6" ry="5" fill="#F8F1DE" className="avatar-hand avatar-hand-r" />
      </g>

      {(effective === "thinking" || effective === "loading") && !compact && (
        <g className="avatar-orbit">
          <circle cx="104" cy="22" r="3" fill="#D6B477" />
          <circle cx="112" cy="30" r="2" fill="#16845B" />
          <circle cx="108" cy="12" r="1.6" fill="#D6B477" />
        </g>
      )}
      {effective === "success" && (
        <g className="avatar-sparkles">
          <path d="M100 18 l2 5 5 2 -5 2 -2 5 -2 -5 -5 -2 5 -2z" fill="#FBBF24" />
          <path d="M16 24 l1.5 3.5 3.5 1.5 -3.5 1.5 -1.5 3.5 -1.5 -3.5 -3.5 -1.5 3.5 -1.5z" fill="#34D399" />
        </g>
      )}
      {(effective === "error" || effective === "alert") && (
        <g className="avatar-sweat">
          <path d="M100 30 q4 6 0 9 q-4 -3 0 -9z" fill="#16845B" />
        </g>
      )}
      {effective === "explaining" && <circle cx="104" cy="70" r="3" fill="#16845B" className="avatar-spark" />}
    </svg>
  );

  const hostHandlers = {
    onMouseEnter: () => setHovered(true),
    onMouseLeave: () => setHovered(false),
  };

  if (onClick) {
    return (
      <button
        type="button"
        className="avatar-button"
        onClick={() => {
          setPoked(true);
          onClick();
        }}
        aria-label={`Open ${label}`}
        data-testid="avatar-button"
      >
        <span ref={hostRef} className="avatar-host" {...hostHandlers}>
          {content}
        </span>
      </button>
    );
  }

  return (
    <span ref={hostRef} className="avatar-host" {...hostHandlers}>
      {content}
    </span>
  );
}
