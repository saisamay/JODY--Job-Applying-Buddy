import { ComponentProps } from "react";

export function Mark({ size = 28 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
    >
      <g fill="currentColor">
        {Array.from({ length: 8 }, (_, i) => (
          <path
            key={i}
            transform={`rotate(${i * 45} 16 16)`}
            d="M14.4 2.4 16 0l2.1 3.2-.8 8.6L16 16l-1.9-4.4z"
          />
        ))}
      </g>
    </svg>
  );
}
export function Brand({ href = "/", ...props }: ComponentProps<"a">) {
  return (
    <a href={href} {...props} aria-label="JODY home" className="brand">
      <Mark />
      <span>
        Jody<span className="brand-point">.</span>
      </span>
    </a>
  );
}
